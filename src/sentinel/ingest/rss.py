"""RSS connector with conditional GET (ETag / Last-Modified) and per-feed error isolation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import httpx
import yaml

from .base import Document, PollingConnector, normalize_text

log = logging.getLogger(__name__)


def parse_feed(feed_name: str, content: bytes) -> list:
    parsed = feedparser.parse(content)
    docs = []
    for e in parsed.entries:
        title = normalize_text(e.get("title"))
        if not title:
            continue
        summary = normalize_text(e.get("summary") or e.get("description"))
        link = e.get("link")
        key = e.get("id") or link or title
        ts = e.get("published_parsed") or e.get("updated_parsed")
        published = datetime(*ts[:6], tzinfo=timezone.utc) if ts else datetime.now(timezone.utc)
        text = f"{title}. {summary}" if summary and summary != title else title
        docs.append(Document("news", f"rss:{feed_name}", key, link, published, title, text,
                             meta={"feed": feed_name}))
    return docs


class RssFeeds(PollingConnector):
    name = "rss"

    def __init__(self, client: httpx.AsyncClient, poll_seconds: int, feeds_path: str = "config/feeds.yaml"):
        self.client, self.poll_seconds = client, poll_seconds
        self.feeds = yaml.safe_load(Path(feeds_path).read_text())["feeds"]
        self._cache = {}  # url -> {"etag":..., "modified":...}

    async def _one(self, feed: dict) -> list:
        headers = {}
        c = self._cache.get(feed["url"], {})
        if c.get("etag"):
            headers["If-None-Match"] = c["etag"]
        if c.get("modified"):
            headers["If-Modified-Since"] = c["modified"]
        try:
            r = await self.client.get(feed["url"], headers=headers, follow_redirects=True, timeout=20)
            if r.status_code == 304:
                return []
            r.raise_for_status()
            self._cache[feed["url"]] = {"etag": r.headers.get("etag"), "modified": r.headers.get("last-modified")}
            return parse_feed(feed["name"], r.content)
        except Exception as e:  # isolate failures per feed
            log.warning("rss feed %s failed: %s", feed["name"], e)
            return []

    async def fetch(self) -> list:
        results = await asyncio.gather(*(self._one(f) for f in self.feeds))
        return [d for docs in results for d in docs]
