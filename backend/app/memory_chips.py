from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

CHIPS_PATH = os.getenv("MEMORY_CHIPS_PATH", os.path.join(os.path.dirname(__file__), "memory_chips.json"))

@dataclass
class MemoryChip:
    name: str
    content: str
    keywords: List[str]

class MemoryChips:
    def __init__(self, path: str = CHIPS_PATH) -> None:
        self.path = path
        self._chips: List[MemoryChip] = []
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._chips = [MemoryChip(**c) for c in data]
        except Exception:
            self._chips = []

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump([asdict(c) for c in self._chips], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def list(self) -> List[Dict[str, Any]]:
        return [asdict(c) for c in self._chips]

    def add(self, name: str, content: str, keywords: List[str]) -> None:
        # upsert by name
        filtered = [c for c in self._chips if c.name != name]
        filtered.append(MemoryChip(name=name, content=content, keywords=keywords[:5]))
        self._chips = filtered
        self._save()

    def remove(self, name: str) -> bool:
        before = len(self._chips)
        self._chips = [c for c in self._chips if c.name != name]
        self._save()
        return len(self._chips) < before

    def clear(self) -> None:
        self._chips = []
        self._save()

    def match_for_text(self, text: str) -> List[str]:
        t = text
        out: List[str] = []
        for c in self._chips:
            if any(k in t for k in c.keywords):
                out.append(c.content)
        return out 