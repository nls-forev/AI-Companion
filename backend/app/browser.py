from __future__ import annotations

import aiohttp
import asyncio
import re
import time
from typing import List, Dict, Any
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

SearchResult = Dict[str, str]

DUCK_HTML = "https://duckduckgo.com/html/?q={query}"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

class WebBrowser:
    def __init__(self, timeout: int = 12, cache_ttl_sec: int = 3600) -> None:
        self.timeout = timeout
        self.cache_ttl_sec = cache_ttl_sec
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def _get(self, url: str) -> str:
        headers = {"User-Agent": USER_AGENT}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=self.timeout) as resp:
                resp.raise_for_status()
                return await resp.text(errors="ignore")

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        html = await self._get(DUCK_HTML.format(query=quote_plus(query)))
        soup = BeautifulSoup(html, "html.parser")
        results: List[SearchResult] = []
        for res in soup.select(".result__body"):
            a = res.select_one("a.result__a")
            if not a:
                continue
            url = a.get("href") or ""
            title = a.get_text(" ").strip()
            snippet_el = res.select_one(".result__snippet")
            snippet = (snippet_el.get_text(" ") if snippet_el else "").strip()
            if url and title:
                results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break
        return results

    async def fetch_clean_text(self, url: str, max_chars: int = 4000) -> str:
        try:
            html = await self._get(url)
        except Exception:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        # remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]

    async def gather_sources(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        q = query.strip().lower()
        now = time.time()
        cached = self._cache.get(q)
        if cached and now - cached.get("t", 0) < self.cache_ttl_sec:
            return cached.get("sources", [])
        hits = await self.search(query, max_results=k)
        tasks = [self.fetch_clean_text(h["url"]) for h in hits]
        contents = await asyncio.gather(*tasks, return_exceptions=True)
        sources: List[Dict[str, Any]] = []
        for h, c in zip(hits, contents):
            if isinstance(c, Exception):
                text = ""
            else:
                text = c
            sources.append({"title": h["title"], "url": h["url"], "snippet": h.get("snippet", ""), "text": text})
        self._cache[q] = {"t": now, "sources": sources}
        return sources 