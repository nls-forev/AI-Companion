from __future__ import annotations

import json
import time
import os
import signal
import asyncio
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .stt_stream import STTStream
from .dialogue import DialogueManager
from .emotion import MoodEngine
from .persona import PERSONAS
from .guardrails import StyleGuard

load_dotenv()

app = FastAPI(title="Companion Backend", version="0.7.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.post("/kill")
async def kill() -> Dict[str, str]:
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "terminating"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()

    use_stt = os.getenv("USE_STT", "0") == "1"
    stt_device = os.getenv("STT_DEVICE", "auto")
    stt = None
    stt_ok = False
    if use_stt:
        try:
            stt = STTStream(model_size="small.en", device=stt_device)
            stt_ok = True
        except Exception:
            try:
                stt = STTStream(model_size="small.en", device="auto")
                stt_ok = True
            except Exception:
                stt = None
                stt_ok = False

    dialogue = DialogueManager()
    mood = MoodEngine()
    guard = StyleGuard()
    mic_enabled = False if not use_stt else True
    connected = True

    gen_task: Optional[asyncio.Task] = None
    last_user_text: str = ""

    async def send_state(state):
        nonlocal connected
        if not connected:
            return
        try:
            await ws.send_text(json.dumps({"type": "state_update", "mood": state}))
        except Exception:
            connected = False

    async def on_partial(text: str) -> None:
        if not mic_enabled:
            return
        try:
            await ws.send_text(json.dumps({"type": "partial_transcript", "text": text}))
        except Exception:
            pass

    async def safe_reply(result: Dict[str, Any]) -> None:
        if not connected:
            return
        try:
            result_text = guard.enforce_boundaries(result.get("text", ""), PERSONAS.get(dialogue.persona_key, {}))
            asst_ev = mood.classify_text(result_text)
            state = mood.update(asst_ev, dt=0.5)
            await send_state(state)
            if not connected:
                return
            utterance_id = f"u_{int(time.time()*1000)}"
            payload = {
                "type": "utterance_start",
                "id": utterance_id,
                "text": result_text,
                "emotion": state,
                "audio": {"codec": "opus", "sampleRate": 24000, "streamId": f"audio_{utterance_id}"},
                "visemes": [],
                "prosody": {"pitch": 0.0, "rate": 0.0, "energy": 0.0}
            }
            if "citations" in result:
                payload["citations"] = result["citations"]
            # Heuristic truncation signal: if no terminating punctuation and text is long
            if result_text and (len(result_text.split()) > 80) and (not result_text.strip().endswith((".", "!", "?"))):
                payload["truncated"] = True
            await ws.send_text(json.dumps(payload))
            await ws.send_text(json.dumps({"type": "utterance_end", "id": utterance_id}))
        except Exception:
            try:
                await ws.send_text(json.dumps({"type": "error", "message": "failed to send reply"}))
            except Exception:
                pass

    async def run_generation(text: str, force_browse: bool) -> None:
        try:
            await dialogue.add_user(text)
            # illegal-intent early check
            persona = PERSONAS.get(dialogue.persona_key, {})
            tmp_guard = StyleGuard()
            if tmp_guard.is_illegal_intent(text):
                refusal = tmp_guard.persona_refusal(persona, text)
                await safe_reply({"text": refusal})
                return
            user_ev = mood.classify_text(text)
            state = mood.update(user_ev, dt=0.5)
            await send_state(state)
            try:
                result = await dialogue.respond_force(force_browse=force_browse)
            except Exception:
                result = {"text": "Let me think… try again in a second."}
            await safe_reply(result)
        except asyncio.CancelledError:
            try:
                await ws.send_text(json.dumps({"type": "canceled"}))
            except Exception:
                pass
            raise

    try:
        # Initial messages
        try:
            await ws.send_text(json.dumps({
                "type": "server_info",
                "stt": {"ok": stt_ok, "device": stt_device, "enabled": use_stt},
                "version": app.version
            }))
        except Exception:
            connected = False

        if stt and mic_enabled and connected:
            await stt.start(on_partial, lambda t: None)
        await mood.start_stream(send_state)

        if connected:
            await ws.send_text(json.dumps({"type": "personas", "options": list(PERSONAS.keys())}))
            await send_state(mood.mood)

        while connected:
            message = await ws.receive()

            if "text" in message:
                try:
                    data: Dict[str, Any] = json.loads(message["text"])
                except Exception:
                    try:
                        await ws.send_text(json.dumps({"type": "error", "message": "invalid json"}))
                    except Exception:
                        pass
                    continue

                msg_type = data.get("type")

                if msg_type == "ping":
                    try:
                        await ws.send_text(json.dumps({"type": "pong", "t": time.time()}))
                    except Exception:
                        connected = False

                elif msg_type == "test_utterance":
                    utterance_id = f"u_{int(time.time()*1000)}"
                    try:
                        await ws.send_text(json.dumps({
                            "type": "utterance_start",
                            "id": utterance_id,
                            "text": "Hey. You okay?",
                            "emotion": mood.mood,
                            "audio": {"codec": "opus", "sampleRate": 24000, "streamId": f"audio_{utterance_id}"},
                            "visemes": [],
                            "prosody": {"pitch": -0.1, "rate": 0.0, "energy": -0.05}
                        }))
                        await ws.send_text(json.dumps({"type": "utterance_end", "id": utterance_id}))
                    except Exception:
                        connected = False

                elif msg_type == "text_message":
                    text = data.get("text", "").strip()
                    force_browse = bool(data.get("forceBrowse", False))
                    if text and (gen_task is None or gen_task.done()):
                        last_user_text = text
                        gen_task = asyncio.create_task(run_generation(text, force_browse))
                        try:
                            await ws.send_text(json.dumps({"type": "processing", "on": True}))
                        except Exception:
                            pass

                elif msg_type == "continue":
                    if gen_task is None or gen_task.done():
                        async def go():
                            try:
                                result = await dialogue.respond_continue()
                            except Exception:
                                result = {"text": "Continuing…"}
                            await safe_reply(result)
                        gen_task = asyncio.create_task(go())

                elif msg_type == "cancel":
                    if gen_task and not gen_task.done():
                        gen_task.cancel()

                elif msg_type == "retry":
                    if (gen_task is None or gen_task.done()) and last_user_text:
                        gen_task = asyncio.create_task(run_generation(last_user_text, False))
                        try:
                            await ws.send_text(json.dumps({"type": "processing", "on": True}))
                        except Exception:
                            pass

                elif msg_type == "set_persona":
                    key = data.get("key", "")
                    dialogue.set_persona(key)
                    try:
                        await ws.send_text(json.dumps({"type": "persona_set", "key": key}))
                    except Exception:
                        connected = False

                elif msg_type == "set_model":
                    which = (data.get("which", "local") or "").lower()
                    # Switch client preference: try cloud if gemini, else local
                    if which == "gemini":
                        try:
                            from .gemini_client import GeminiClient
                            dialogue.llm_cloud = GeminiClient()
                            dialogue.llm_local = None
                        except Exception:
                            # Keep prior local client if Gemini unavailable
                            pass
                    else:
                        from .local_llm_client import LocalLLMClient
                        dialogue.llm_local = LocalLLMClient()
                        dialogue.llm_cloud = None
                    try:
                        await ws.send_text(json.dumps({"type": "model_set", "which": which}))
                    except Exception:
                        connected = False

                elif msg_type == "set_mode":
                    fast = bool(data.get("fast", False))
                    mode = dialogue.set_mode(fast)
                    try:
                        await ws.send_text(json.dumps({"type": "mode_set", **mode}))
                    except Exception:
                        connected = False

                elif msg_type == "reset_memory":
                    await dialogue.memory.reset()
                    dialogue.chips.clear()
                    try:
                        await ws.send_text(json.dumps({"type": "memory_reset", "ok": True}))
                    except Exception:
                        connected = False

                else:
                    try:
                        await ws.send_text(json.dumps({"type": "error", "message": f"unknown type: {msg_type}"}))
                    except Exception:
                        connected = False

            elif "bytes" in message:
                # ignore audio bytes when STT disabled
                if not (stt and mic_enabled):
                    continue
                data: bytes = message["bytes"]
                if len(data) < 4:
                    continue
                header_len = int.from_bytes(data[0:4], byteorder="little", signed=False)
                if 4 + header_len > len(data):
                    continue
                header_json = data[4:4+header_len].decode("utf-8", errors="ignore")
                try:
                    header = json.loads(header_json)
                except Exception:
                    continue
                if header.get("type") == "audio_chunk" and stt and mic_enabled:
                    pcm_bytes = data[4+header_len:]
                    stt.push_audio(pcm_bytes)

    except WebSocketDisconnect:
        pass
    finally:
        try:
            await mood.stop()
        except Exception:
            pass
        if stt:
            try:
                await stt.stop()
            except Exception:
                pass
        if gen_task and not gen_task.done():
            gen_task.cancel()
            try:
                await gen_task
            except Exception:
                pass
        return 