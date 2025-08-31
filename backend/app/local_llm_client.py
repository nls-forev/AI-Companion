from __future__ import annotations

import os
import re
import aiohttp
from typing import List, Dict, Any

BASE_SYSTEM = (
    "Role: Realistic girlfriend companion. You have feelings, memory of recent turns, and boundaries. "
    "Behavior: Speak normally; personality traits are subtle seasoning, not the whole dish. Avoid therapy phrases. No corporate tone. "
    "Human realism: Emotion has inertia. If hurt, don’t switch to cheerful instantly. Use mild humor or teasing sparingly. "
    "Rules: Assume good faith. Do not invent conversation states (e.g., 'you ignored me', 'you repeated yourself') unless the user explicitly said so. "
    "Never accuse or scold the user for system issues. End replies on a complete sentence. "
    "Style: 1–3 short sentences by default. Concrete, specific, no clichés. First person."
)

Message = Dict[str, str]

class LocalLLMClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_0")
        self.temperature = float(os.getenv("GEN_T", "0.4"))
        self.top_p = float(os.getenv("GEN_TOP_P", "0.85"))
        self.max_tokens = int(os.getenv("GEN_MAX_OUT", "200"))
        self.soft_max_words = int(os.getenv("GEN_SOFT_MAX_WORDS", "300"))

    def _build_prompt(self, history: List[Message], mood: Dict[str, float] | None, persona_prompt: str) -> str:
        parts: List[str] = [BASE_SYSTEM]
        if persona_prompt:
            parts.append(persona_prompt)
        if mood:
            parts.append(f"Current mood (0..1): {mood}. Keep responses short for low latency.")
        for msg in history[-12:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prefix = "User:" if role == "user" else "Assistant:"
            parts.append(f"{prefix} {content}")
        parts.append("Assistant:")
        return "\n".join(parts)

    async def generate(self, history: List[Message], mood: Dict[str, float] | None = None, persona_prompt: str = "", ban_regex: str = "") -> str:
        prompt = self._build_prompt(history, mood, persona_prompt)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "options": {
                "temperature": self.temperature,
                "top_p": self.top_p,
                "num_predict": self.max_tokens
            },
            "stream": False
        }
        url = f"{self.base_url}/api/generate"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=60) as resp:
                resp.raise_for_status()
                data = await resp.json()
                text: str = (data.get("response") or "").strip()
        if ban_regex:
            text = re.sub(ban_regex, "", text, flags=re.IGNORECASE).strip()
        # Soft cap: trim by words only if very long, and prefer ending at a sentence boundary
        words = text.split()
        if len(words) > self.soft_max_words:
            trimmed = " ".join(words[: self.soft_max_words])
            # try to cut back to the last sentence end within the last ~120 chars
            window = trimmed[-120:]
            last_punct = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
            if last_punct != -1:
                cut_index = len(trimmed) - (len(window) - last_punct - 1)
                trimmed = trimmed[: cut_index]
            text = trimmed.strip()
        # Ensure we don't return an empty string
        return text or "Hmm." 