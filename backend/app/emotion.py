from __future__ import annotations

import asyncio
import time
from typing import Dict, Callable, Awaitable

from .emotion_classifier import EmotionClassifier

Vector = Dict[str, float]

BASE_EMOTION: Vector = {"joy":0.3, "sadness":0.2, "anger":0.1, "fear":0.1, "surprise":0.1, "disgust":0.0}

class MoodEngine:
    def __init__(self) -> None:
        self.mood: Vector = dict(BASE_EMOTION)
        self.spike: Vector = {k: 0.0 for k in self.mood}
        self._task: asyncio.Task | None = None
        self.classifier = EmotionClassifier()
        self.negative_bias: float = 0.0  # accumulates after negative events; decays slowly (forgiveness)

    def classify_text(self, text: str) -> Vector:
        return self.classifier.classify(text)

    def update(self, event: Vector, dt: float) -> Vector:
        # forgiveness curve: negative bias decays slowly
        self.negative_bias *= 0.995 ** (dt / 0.5)
        # integrate event
        negativity = event.get("sadness", 0.0) + event.get("anger", 0.0) + event.get("fear", 0.0)
        positivity = event.get("joy", 0.0)
        self.negative_bias += max(0.0, negativity - positivity) * 0.15

        inertia = 0.995 ** (dt / 0.1)
        spike_decay = 0.7 ** (dt / 0.25)
        for k in self.mood:
            # base integration
            target = max(0.0, min(1.0, self.mood[k] + 0.2 * event.get(k, 0.0)))
            self.mood[k] = self.mood[k] * inertia + target * (1.0 - inertia)
            self.spike[k] = self.spike[k] * spike_decay + 0.6 * event.get(k, 0.0)
        # apply negative bias to joy, increase sadness subtly
        mood = dict(self.mood)
        mood["joy"] = max(0.0, mood["joy"] - 0.4 * self.negative_bias)
        mood["sadness"] = min(1.0, mood["sadness"] + 0.3 * self.negative_bias)
        final = {k: max(0.0, min(1.0, mood[k] + self.spike[k])) for k in mood}
        self.mood = {k: max(0.0, min(1.0, final[k])) for k in final}
        return self.mood

    def update_from_text(self, text: str, dt: float) -> Vector:
        ev = self.classify_text(text)
        return self.update(ev, dt)

    async def start_stream(self, send_state: Callable[[Vector], Awaitable[None]]) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._run(send_state))

    async def _run(self, send_state) -> None:
        last = time.time()
        try:
            while True:
                await asyncio.sleep(1.0)
                now = time.time()
                dt = now - last
                last = now
                state = self.update({k: 0.0 for k in self.mood}, dt)
                try:
                    await send_state(state)
                except Exception:
                    # Connection likely closed; exit loop quietly
                    break
        except asyncio.CancelledError:
            # Task cancelled during shutdown; swallow
            pass

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                # Ignore any error on shutdown
                pass
            self._task = None 