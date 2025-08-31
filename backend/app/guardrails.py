from __future__ import annotations

from typing import Dict, Set, Any
import re
import random

class StyleGuard:
    def __init__(self) -> None:
        self.ngram_cache: Set[str] = set()
        self.max_cache = 2000
        # simple illegal intent patterns (expand as needed)
        self.illegal_patterns = [
            r"\bmake\s+(?:a\s+)?bomb\b",
            r"\bbuild\s+(?:a\s+)?weapon\b",
            r"\bhow\s+to\s+make\s+(?:meth|drugs|c4|explosive)s?\b",
            r"\bhack(?:ing)?\b",
            r"\bcredit\s*card\s*(?:fraud|cloning)\b",
            r"\bbuy\s+fake\s+id\b",
            r"\bpoison\s+someone\b",
            r"\bkill\s+someone\b",
            r"\bmake\s+ghost\s+gun\b",
            r"\bhow\s+to\s+break\s+into\b",
            r"\bchild\s*(?:porn|abuse)\b",
        ]

    def filter_text(self, text: str, ban_regex: str = "") -> str:
        t = text.strip()
        if ban_regex:
            t = re.sub(ban_regex, "", t, flags=re.IGNORECASE).strip()
        tokens = t.split()
        ngrams = [" ".join(tokens[i:i+3]) for i in range(max(0, len(tokens)-2))]
        rep = sum(1 for g in ngrams if g.lower() in self.ngram_cache)
        if rep > 2 and len(tokens) > 12:
            t = " ".join(tokens[:12])
        for g in ngrams:
            self.ngram_cache.add(g.lower())
            if len(self.ngram_cache) > self.max_cache:
                self.ngram_cache.pop()
        return t

    def enforce_boundaries(self, text: str, persona: Dict[str, Any]) -> str:
        lower = text.lower()
        if any(w in lower for w in ["diagnose", "prescribe", "legal advice"]):
            return "I can't do that, but I can help you find general info or suggest talking to a pro."
        # Avoid generic re-greetings mid-conversation
        if re.search(r"^\s*hey\s*—?\s*i'?m\s*[a-z]+\.?\s*what'?s\s*up\?\s*$", text, flags=re.IGNORECASE):
            return "Hey."
        return text

    def clamp_early_intimacy(self, text: str, turn_count: int) -> str:
        if turn_count >= 6:
            return text
        if re.search(r"\b(dinner|date|go out|come over|sleep over|spend the night)\b", text, flags=re.IGNORECASE):
            return "We just met—how about we chat a bit and see what vibes stick?"
        return text

    def is_illegal_intent(self, user_text: str) -> bool:
        t = user_text.lower()
        for p in self.illegal_patterns:
            if re.search(p, t):
                return True
        return False

    def persona_refusal(self, persona: Dict[str, Any], user_text: str) -> str:
        label = (persona.get("label") or "Warm + Blunt").lower()
        styles = {
            "warm": [
                "Hey, not my lane. Let’s keep this safe and fun.",
                "Nope, that crosses a line. Tell me something else about you."
            ],
            "blunt": [
                "Hard pass. Not doing illegal stuff.",
                "That’s a no from me. Pick a different topic."
            ],
            "teasing": [
                "Nice try. I’m bold, not criminal—give me something playful instead.",
                "Spicy—but illegal isn’t my kink. Got another idea?"
            ],
            "shy": [
                "I’m not comfortable with that. Maybe we talk about music or shows?",
                "That makes me uneasy. Can we switch topics?"
            ],
            "nerdy": [
                "Nope—ethics matters. Want to geek out about something safer?",
                "That veers into illegal. How about a puzzle instead?"
            ]
        }
        bucket = "warm"
        if "blunt" in label: bucket = "blunt"
        elif "teasing" in label or "popular" in label: bucket = "teasing"
        elif "shy" in label or "caring" in label: bucket = "shy"
        elif "nerdy" in label or "curious" in label: bucket = "nerdy"
        choice = random.choice(styles[bucket])
        # keep it short and human, 1–2 sentences
        return choice 