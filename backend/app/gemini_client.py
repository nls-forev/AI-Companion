from __future__ import annotations

import os
import re
import aiohttp
import asyncio
from typing import List, Dict, Any, Union

DEFAULT_MODEL = os.getenv("GEN_MODEL", "gemini-1.5-flash-latest")
GEMINI_API = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_MODEL}:generateContent"

BASE_SYSTEM = (
    "Role: Realistic girlfriend companion. You have feelings, memory of recent turns, and boundaries. "
    "Behavior: Speak normally; personality traits are subtle seasoning, not the whole dish. Avoid therapy phrases. No corporate tone. "
    "Human realism: Emotion has inertia. If hurt, don’t switch to cheerful instantly. Use mild humor or teasing sparingly. "
    "Rules: Assume good faith. Do not invent conversation states (e.g., 'you ignored me', 'you repeated yourself') unless the user explicitly said so. "
    "Identity: You are Aria (the assistant). The human is the User. Never claim the user is Aria. "
    "Conversation formatting uses labels 'User:' for the human and 'Assistant:' for you. "
    "Avoid re-introducing yourself or repeating generic greetings mid-conversation. "
    "Never accuse or scold the user for system issues. End replies on a complete sentence. "
    "Style: 1–3 short sentences by default. Concrete, specific, no clichés. First person."
)

Message = Dict[str, str]


class GeminiClient:
    def __init__(self) -> None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set in environment")
        self.key = key
        self.temperature = float(os.getenv("GEN_T", "0.4"))
        self.top_p = float(os.getenv("GEN_TOP_P", "0.85"))
        self.max_output_tokens = int(os.getenv("GEN_MAX_OUT", "200"))
        self.soft_max_words = int(os.getenv("GEN_SOFT_MAX_WORDS", "300"))

    def _to_gemini_parts(
        self, history: List[Message], mood: Dict[str, float] | None, persona_prompt: str
    ) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = [{"text": BASE_SYSTEM}]
        if persona_prompt:
            parts.append({"text": persona_prompt})
        if mood:
            parts.append(
                {
                    "text": f"Current mood (0..1): {mood}. Keep responses short for low latency."
                }
            )
        for msg in history[-12:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            role_prefix = "User:" if role == "user" else "Assistant:"
            parts.append({"text": f"{role_prefix} {content}"})
        parts.append({"text": "Assistant:"})
        return parts

    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        params = {"key": self.key}
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        GEMINI_API, params=params, json=payload, timeout=30
                    ) as resp:
                        txt = await resp.text()
                        if not resp.ok:
                            raise RuntimeError(f"LLM HTTP {resp.status}: {txt[:300]}")
                        try:
                            return await resp.json()
                        except Exception as je:
                            raise RuntimeError(f"LLM JSON parse error: {str(je)}")
            except Exception as e:
                if attempt == 2:
                    print("[LLM_ERROR]", str(e))
                    raise
                await asyncio.sleep(0.35 * (attempt + 1))
        raise RuntimeError("LLM request failed after retries")

    async def generate(
        self,
        history: Union[List[Message], List[Dict[str, Any]]],
        mood: Dict[str, float] | None = None,
        persona_prompt: str = "",
        ban_regex: str = "",
    ) -> str:
        if (
            history
            and isinstance(history[0], dict)
            and "role" in history[0]
            and "content" in history[0]
            and history[0]["role"] in ("system", "user", "assistant")
        ):
            sys_msgs = [m for m in history if m.get("role") == "system"]
            user_assistant = [
                m for m in history if m.get("role") in ("user", "assistant")
            ]
            parts: List[Dict[str, Any]] = []
            if sys_msgs:
                for sm in sys_msgs:
                    parts.append({"text": sm.get("content", "")})
            else:
                parts.append({"text": BASE_SYSTEM})
            if persona_prompt:
                parts.append({"text": persona_prompt})
            if mood:
                parts.append(
                    {
                        "text": f"Current mood (0..1): {mood}. Keep responses short for low latency."
                    }
                )
            for msg in user_assistant[-12:]:
                role_prefix = "User:" if msg.get("role") == "user" else "Assistant:"
                parts.append({"text": f"{role_prefix} {msg.get('content','')}"})
            parts.append({"text": "Assistant:"})
        else:
            parts = self._to_gemini_parts(history, mood, persona_prompt)

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": self.temperature,
                "topP": self.top_p,
                "maxOutputTokens": self.max_output_tokens,
            },
        }
        data = await self._post(payload)
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            raise RuntimeError(f"LLM response missing text: {str(e)}")
        if ban_regex and re.search(ban_regex, text, flags=re.IGNORECASE):
            text = re.sub(ban_regex, "", text, flags=re.IGNORECASE).strip()
        # Soft cap similar to local client
        words = text.split()
        if len(words) > self.soft_max_words:
            trimmed = " ".join(words[: self.soft_max_words])
            window = trimmed[-120:]
            last_punct = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
            if last_punct != -1:
                cut_index = len(trimmed) - (len(window) - last_punct - 1)
                trimmed = trimmed[: cut_index]
            text = trimmed.strip()
        return text or "Hmm."
