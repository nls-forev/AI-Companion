from __future__ import annotations

import os
import asyncio
import re
from typing import Dict, List, Any
from .gemini_client import GeminiClient
from .local_llm_client import LocalLLMClient
from .persona import PERSONAS
from .memory import Memory
from .guardrails import StyleGuard
from .browser import WebBrowser
from .memory_chips import MemoryChips

class DialogueManager:
    def __init__(self) -> None:
        self.history: List[Dict[str, str]] = []
        use_local = os.getenv("USE_LOCAL_LLM", "0") == "1"
        self.llm_cloud = None
        self.llm_local = None
        if use_local:
            self.llm_local = LocalLLMClient()
        else:
            try:
                self.llm_cloud = GeminiClient()
            except Exception:
                self.llm_local = LocalLLMClient()
        self.mood = {"joy": 0.3, "sadness": 0.2, "anger": 0.1, "fear": 0.1, "surprise": 0.1, "disgust": 0.0}
        self.persona_key = "girlfriend_warm_blunt"
        self.memory = Memory()
        self.guard = StyleGuard()
        self.next_identity_prefix: bool = False
        self.browser = WebBrowser()
        self.chips = MemoryChips()
        self.consistency_n: int = int(os.getenv("SELF_CONSISTENCY_N", "1"))
        self.auto_browsing: bool = os.getenv("AUTO_BROWSING", "1") != "0"
        self.self_knowledge: Dict[str, Any] = {
            "likes": {"anime": ["Jujutsu Kaisen", "Mob Psycho 100"], "food": ["ramen", "mango mochi"], "clothes": ["oversized tees", "platform sneakers"]},
            "dislikes": {"food": ["raisin cookies"]},
        }
        self.one_word_mode: bool = False

    def _llm(self):
        return self.llm_cloud or self.llm_local or GeminiClient()

    def _distill_cues(self, recent: List[Dict[str, str]], retrieved: List[Dict[str, str]], last_user: str) -> List[str]:
        cues: List[str] = []
        # prefer retrieved then salient recent
        for m in (retrieved + recent):
            txt = (m.get("content") or "").strip()
            if not txt:
                continue
            # skip very long lines
            if len(txt) > 180:
                txt = txt[:180]
            if txt.lower() in (c.lower() for c in cues):
                continue
            cues.append(txt)
            if len(cues) >= 3:
                break
        # add last user hint if empty
        if not cues and last_user:
            cues.append(last_user[:120])
        return cues

    def _make_plan(self, last_user: str, cues: List[str], turn_count: int) -> str:
        implicit = "implicit" if not any(w in last_user.lower() for w in ["explain", "why", "how", "details"]) else "explicit"
        beats = 1 if turn_count < 4 else 2
        tone = "casual" if turn_count < 8 else "warm"
        return (
            "Internal guidance (do not reveal): "
            f"tone={tone}; explicitness={implicit}; beats={beats}; 1–3 sentences. "
            f"Use cues sparingly: {'; '.join(cues[:3])}. "
            "Do not mention any planning, system notes, or that you're figuring things out."
        )

    def _enforce_identity(self, text: str) -> str:
        # Replace other names with persona name
        name = PERSONAS.get(self.persona_key, {}).get("name", "Aria")
        patterns = [
            r"\bI\s*am\s+[A-Z][a-zA-Z]+\b",
            r"\bI'm\s+[A-Z][a-zA-Z]+\b",
            r"\bMy\s+name\s+is\s+[A-Z][a-zA-Z]+\b",
        ]
        out = text
        for p in patterns:
            out = re.sub(p, f"I'm {name}", out)
        # Correct accidental attribution that the user is Aria
        out = re.sub(r"\b(?:you(?:'re| are)\s+Aria)\b", "I'm Aria", out, flags=re.IGNORECASE)
        return out

    def set_persona(self, key: str) -> None:
        if key in PERSONAS:
            self.persona_key = key

    def set_mode(self, fast: bool) -> Dict[str, Any]:
        if fast:
            self.consistency_n = 1
            self.auto_browsing = False
        else:
            self.consistency_n = int(os.getenv("SELF_CONSISTENCY_N", "1"))
            self.auto_browsing = os.getenv("AUTO_BROWSING", "1") != "0"
        return {"consistency_n": self.consistency_n, "auto_browsing": self.auto_browsing}

    async def add_user(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})
        lt = text.lower()
        if any(k in lt for k in ["who are you", "who r u", "what are you", "your name", "who is she", "who is this"]):
            self.next_identity_prefix = True
        # toggle one-word mode
        if re.search(r"\b(one|single)\s+word\b", lt):
            self.one_word_mode = True
        if re.search(r"\b(normal|full(\s+sentences)?|talk\s+normally)\b", lt):
            self.one_word_mode = False
        sal = 0.6 if any(k in lt for k in ["sorry", "promise", "left me", "hate you", "love you", "cheated"]) else 0.2
        self.memory.append("user", text, salience=sal)

    def _needs_browsing(self, text: str) -> bool:
        t = text.lower()
        triggers = ["today", "latest", "news", "release", "near me", "schedule", "update", "now", "this week", "2025", "price", "tickets"]
        return any(w in t for w in triggers)

    async def _browse_and_summarize(self, query: str) -> Dict[str, Any]:
        sources = await self.browser.gather_sources(query, k=3)
        context_chunks = []
        for s in sources:
            chunk = f"Title: {s['title']}\nURL: {s['url']}\nSnippet: {s.get('snippet','')}\nText: {s.get('text','')[:800]}"
            context_chunks.append(chunk)
        prompt = (
            "You may cite sources. Given the user query and sources, write a concise answer (1-2 sentences). "
            "Include bracketed citations like [1], [2] referencing the numbered sources."
        )
        msgs: List[Dict[str, str]] = [{"role": "system", "content": prompt}, {"role": "user", "content": f"Query: {query}\n\n" + "\n\n".join([f"[{i+1}]\n{c}" for i, c in enumerate(context_chunks)])}]
        text = await self._llm().generate(msgs, self.mood, persona_prompt="", ban_regex="")
        citations = []
        for i, s in enumerate(sources):
            citations.append({"index": i + 1, "title": s["title"], "url": s["url"]})
        return {"text": text, "citations": citations}

    def _build_context(self) -> List[Dict[str, str]]:
        recent = self.memory.recent(12)
        retrieved = self.memory.retrieve(" ".join([h.get("content", "") for h in self.history[-3:]]), top_k=3)
        # memory chips injection by triggers
        last_user = next((h.get("content", "") for h in reversed(self.history) if h.get("role") == "user"), "")
        chip_texts = self.chips.match_for_text(last_user)
        temp_history: List[Dict[str, str]] = []
        for chip in chip_texts:
            temp_history.append({"role": "system", "content": f"[MemoryChip] {chip}"})
        for m in (retrieved + recent):
            temp_history.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        temp_history.extend(self.history[-6:])
        # inject one-word mode guidance if enabled
        if self.one_word_mode:
            temp_history.append({"role": "system", "content": "User requested single-word replies. Respond with exactly one lowercase word unless safety requires otherwise."})
        return temp_history

    def _to_one_word(self, text: str, fallback: str = "okay") -> str:
        t = (text or "").strip()
        if not t:
            return fallback
        # pick first alphanumeric token
        m = re.search(r"[A-Za-z][A-Za-z\-']*", t)
        return (m.group(0) if m else fallback)

    async def _self_consistency_vote(self, history: List[Dict[str, str]], persona_prompt: str, ban_regex: str, n: int) -> str:
        llm = self._llm()
        if n <= 1:
            raw = await llm.generate(history, self.mood, persona_prompt=persona_prompt, ban_regex=ban_regex)
            return self.guard.filter_text(raw, ban_regex=ban_regex)
        tasks = [llm.generate(history, self.mood, persona_prompt=persona_prompt, ban_regex=ban_regex) for _ in range(n)]
        outs = await asyncio.gather(*tasks, return_exceptions=True)
        candidates = [self.guard.filter_text(o if isinstance(o, str) else "", ban_regex=ban_regex) for o in outs]
        candidates = [c for c in candidates if c]
        return (min(candidates, key=len) if candidates else "Hmm.")

    async def respond(self) -> Dict[str, object]:
        persona = PERSONAS.get(self.persona_key, PERSONAS["girlfriend_warm_blunt"])
        context = self._build_context()
        last_user = next((h.get("content", "") for h in reversed(self.history) if h.get("role") == "user"), "")

        # special-case human framing prompts
        lu = last_user.lower()
        if self.one_word_mode and re.search(r"\bwho\s+are\s+you\b|\bwho\s*r\s*u\b", lu):
            text = self._to_one_word(persona.get("name", "Aria"), fallback="aria").capitalize()
            self.history.append({"role": "assistant", "content": text})
            self.memory.append("assistant", text, salience=0.2)
            return {"text": text}
        if re.search(r"\bwho\s+made\s+(you|u)\b", lu):
            # keep human framing
            if self.one_word_mode:
                text = "Parents"
            else:
                text = "My parents, long story."
            self.history.append({"role": "assistant", "content": text})
            self.memory.append("assistant", text, salience=0.1)
            return {"text": text}

        citations: List[Dict[str, Any]] = []
        try:
            # lightweight planning + gating
            recent = self.memory.recent(12)
            retrieved = self.memory.retrieve(" ".join([h.get("content", "") for h in self.history[-3:]]), top_k=3)
            cues = self._distill_cues(recent, retrieved, last_user)
            turn_count = sum(1 for h in self.history if h.get("role") == "user")
            # simple greeting for cold open
            if turn_count <= 1 and re.search(r"\b(hi+|hey+|hello|yo|sup)\b", lu):
                text = "Hey — I'm Aria. What’s up?"
                self.history.append({"role": "assistant", "content": text})
                self.memory.append("assistant", text, salience=0.15)
                return {"text": text}
            plan = self._make_plan(last_user, cues, turn_count)
            if self.one_word_mode:
                context.append({"role": "system", "content": "One-word mode active. Return exactly one word."})
            if turn_count < 6:
                context.append({"role": "system", "content": "Early interaction: no pet names, no flirting, no sexual content. Treat user as a stranger; keep boundaries. Natural, brief."})
            context.append({"role": "system", "content": plan})

            if self.auto_browsing and last_user and self._needs_browsing(last_user):
                browsed = await self._browse_and_summarize(last_user)
                raw = browsed["text"]
                citations = browsed.get("citations", [])
            else:
                raw = await self._self_consistency_vote(context, persona_prompt=persona["prompt"], ban_regex=persona["ban_phrases"], n=self.consistency_n)
        except Exception as e:
            raw = f"(LLM error: {str(e)})"

        text = self.guard.filter_text(raw, ban_regex=persona["ban_phrases"])
        turn_count = sum(1 for h in self.history if h.get("role") == "user")
        text = self.guard.clamp_early_intimacy(text, turn_count)
        if self.next_identity_prefix:
            identity = persona.get("identity")
            if identity:
                text = f"{identity} {text}".strip()
            self.next_identity_prefix = False
        if self.one_word_mode:
            text = self._to_one_word(text, fallback="okay")
            # capitalize for names, keep simple
            if text.lower() == "aria":
                text = "Aria"
        else:
            text = self._enforce_identity(text)
            if text.strip().lower() in ("wait.", "wait", "thinking.", "thinking"):
                text = "Hey — I'm Aria. What's up?"
            # Avoid repeating the cold-open greeting after the first turn
            if turn_count > 1:
                text = re.sub(
                    r"^\s*hey\s*—?\s*i'?m\s*aria\.?\s*what'?s\s*up\?\s*",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
                if not text.strip():
                    text = "Okay."
        self.history.append({"role": "assistant", "content": text})
        self.memory.append("assistant", text, salience=0.2)
        payload: Dict[str, Any] = {"text": text}
        if citations:
            payload["citations"] = citations
        return payload

    async def respond_force(self, force_browse: bool = False) -> Dict[str, object]:
        if not force_browse:
            return await self.respond()
        last_user = next((h.get("content", "") for h in reversed(self.history) if h.get("role") == "user"), "")
        if not last_user:
            return await self.respond()
        try:
            return await self._browse_and_summarize(last_user)
        except Exception:
            return await self.respond()

    async def respond_continue(self) -> Dict[str, object]:
        persona = PERSONAS.get(self.persona_key, PERSONAS["girlfriend_warm_blunt"])
        # Add a light system nudge to continue succinctly
        context = self._build_context()
        last_user = next((h.get("content", "") for h in reversed(self.history) if h.get("role") == "user"), "")
        recent = self.memory.recent(12)
        retrieved = self.memory.retrieve(" ".join([h.get("content", "") for h in self.history[-3:]]), top_k=3)
        cues = self._distill_cues(recent, retrieved, last_user)
        turn_count = sum(1 for h in self.history if h.get("role") == "user")
        plan = self._make_plan(last_user, cues, turn_count)
        context.append({"role": "system", "content": "Continue your last assistant message smoothly without repeating earlier text. 1–2 sentences."})
        context.append({"role": "system", "content": plan})
        if self.one_word_mode:
            context.append({"role": "system", "content": "One-word mode active. Return exactly one word."})
        try:
            raw = await self._self_consistency_vote(context, persona_prompt=persona["prompt"], ban_regex=persona["ban_phrases"], n=1)
        except Exception as e:
            raw = f"(LLM error: {str(e)})"
        text = self.guard.filter_text(raw, ban_regex=persona["ban_phrases"])
        if self.one_word_mode:
            text = self._to_one_word(text)
        else:
            text = self._enforce_identity(text)
        self.history.append({"role": "assistant", "content": text})
        self.memory.append("assistant", text, salience=0.15)
        return {"text": text} 