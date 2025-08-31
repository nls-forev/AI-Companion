from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Deque, Optional, Callable
from collections import deque

import numpy as np
from faster_whisper import WhisperModel


@dataclass
class AudioRingBuffer:
    sample_rate: int = 16000
    max_seconds: float = 5.0
    _buffer: Deque[np.ndarray] = field(default_factory=deque)
    _num_samples: int = 0

    def push_pcm16(self, pcm_bytes: bytes) -> None:
        arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self._buffer.append(arr)
        self._num_samples += arr.shape[0]
        self._trim()

    def _trim(self) -> None:
        max_samples = int(self.sample_rate * self.max_seconds)
        while self._num_samples > max_samples and self._buffer:
            front = self._buffer.popleft()
            self._num_samples -= front.shape[0]

    def read_concat(self) -> np.ndarray:
        if not self._buffer:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(list(self._buffer), axis=0)


def _collapse_repeats(text: str) -> str:
    # Collapse very long repeated short words: "so so so ..." -> up to 3 repeats
    words = text.split()
    out = []
    repeat_count = 0
    last_word = None
    for w in words:
        lw = w.lower()
        if lw == last_word and len(lw) <= 3:
            repeat_count += 1
            if repeat_count <= 2:
                out.append(w)
        else:
            repeat_count = 0
            out.append(w)
        last_word = lw
    return " ".join(out)


class STTStream:
    def __init__(self, model_size: str = "small.en", device: str = "auto") -> None:
        self.model = WhisperModel(model_size, device=device, compute_type="int8_float16")
        self.buffer = AudioRingBuffer(sample_rate=16000, max_seconds=5.0)
        self._task: Optional[asyncio.Task] = None
        self._last_emit_text: str = ""
        self._last_emit_ts: float = 0.0
        self._last_final_text: str = ""

    def push_audio(self, pcm_bytes: bytes) -> None:
        self.buffer.push_pcm16(pcm_bytes)

    async def start(self, on_partial: Callable[[str], asyncio.Future], on_final: Callable[[str], asyncio.Future]):
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(on_partial, on_final))

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self, on_partial, on_final):
        while True:
            await asyncio.sleep(0.2)
            audio = self.buffer.read_concat()
            if audio.shape[0] < int(0.4 * self.buffer.sample_rate):
                # also check for finalization timeout when there is no new text
                if self._last_emit_text and self._last_emit_text != self._last_final_text:
                    if (time.time() - self._last_emit_ts) > 1.0:
                        self._last_final_text = self._last_emit_text
                        await on_final(self._last_final_text)
                continue
            try:
                segments, _ = self.model.transcribe(
                    audio,
                    language="en",
                    temperature=0.0,
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 150},
                    no_speech_threshold=0.6,
                    condition_on_previous_text=False,
                    suppress_blank=True,
                )
                last_text = ""
                for seg in segments:
                    last_text = seg.text.strip()

                if not last_text:
                    # possible finalization if stalled
                    if self._last_emit_text and self._last_emit_text != self._last_final_text:
                        if (time.time() - self._last_emit_ts) > 1.0:
                            self._last_final_text = self._last_emit_text
                            await on_final(self._last_final_text)
                    continue

                cleaned = _collapse_repeats(last_text)
                now = time.time()
                grew_enough = len(cleaned) >= len(self._last_emit_text) + 3
                cooldown_ok = (now - self._last_emit_ts) >= 0.25

                if cleaned != self._last_emit_text and (grew_enough or cooldown_ok):
                    self._last_emit_text = cleaned
                    self._last_emit_ts = now
                    await on_partial(cleaned)

                # if stable for >1.0s, finalize
                if self._last_emit_text and self._last_emit_text != self._last_final_text:
                    if (now - self._last_emit_ts) > 1.0:
                        self._last_final_text = self._last_emit_text
                        await on_final(self._last_final_text)
            except Exception:
                pass 