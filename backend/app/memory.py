from __future__ import annotations

import json
import os
from typing import Dict, List
import redis
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "companion_memory")

class Memory:
    def __init__(self) -> None:
        self.r = redis.from_url(REDIS_URL, decode_responses=True)
        self.key_dialog = "companion:dialogue"
        self.max_len = 50
        self.embed = None
        self.qdrant: QdrantClient | None = None
        # Try to init Qdrant + embeddings, but allow backend if unavailable
        try:
            self.embed = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            self.qdrant = QdrantClient(url=QDRANT_URL)
            self._ensure_collection()
        except Exception:
            self.qdrant = None
            self.embed = None

    def _ensure_collection(self) -> None:
        if not self.qdrant:
            return
        try:
            self.qdrant.get_collection(COLLECTION)
        except Exception:
            self.qdrant.recreate_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )

    def append(self, role: str, content: str, affect: Dict[str, float] | None = None, salience: float = 0.0) -> None:
        item = {"role": role, "content": content}
        if affect:
            item["affect"] = affect
        self.r.lpush(self.key_dialog, json.dumps(item))
        self.r.ltrim(self.key_dialog, 0, self.max_len - 1)
        # promote salient items
        if salience >= 0.6 and self.qdrant and self.embed:
            try:
                vec = self.embed.encode(content).tolist()
                payload = {"role": role, "content": content, "salience": salience}
                if affect:
                    payload["affect"] = affect
                self.qdrant.upsert(collection_name=COLLECTION, points=[PointStruct(id=None, vector=vec, payload=payload)])
            except Exception:
                pass

    def recent(self, n: int = 12) -> List[Dict[str, str]]:
        vals = self.r.lrange(self.key_dialog, 0, n - 1)
        out = []
        for v in reversed(vals):
            try:
                out.append(json.loads(v))
            except Exception:
                continue
        return out

    def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, str]]:
        if not (self.qdrant and self.embed):
            return []
        try:
            vec = self.embed.encode(query).tolist()
            res = self.qdrant.search(collection_name=COLLECTION, query_vector=vec, limit=top_k)
            out: List[Dict[str, str]] = []
            for p in res:
                out.append({"role": p.payload.get("role", "assistant"), "content": p.payload.get("content", "")})
            return out
        except Exception:
            return [] 

    def clear(self) -> None:
        # Clear short-term
        try:
            self.r.delete(self.key_dialog)
        except Exception:
            pass
        # Clear long-term
        if self.qdrant:
            try:
                self.qdrant.delete_collection(COLLECTION)
                self._ensure_collection()
            except Exception:
                pass 