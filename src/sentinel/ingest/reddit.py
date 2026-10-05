"""Reddit connector (official OAuth API, app-only token). Requires REDDIT_CLIENT_ID / SECRET.

Reddit may require approval for new API apps. If credentials are missing or rejected, this
connector is marked 'disabled' in source_health and the rest of the pipeline keeps running.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from .base import Document, PollingConnector, normalize_text

log = logging.getLogger(__name__)

SUBREDDITS = ["stocks", "investing", "wallstreetbets", "economy", "SecurityAnalysis"]


def parse_listing(data: dict, subreddit: str) -> list:
    docs = []
    for child in (data.get("data") or {}).get("children", []):
        d = child.get("data") or {}
        if d.get("stickied") or not d.get("title"):
            continue
        title = normalize_text(d["title"])
        body = normalize_text(d.get("selftext"))[:2000]
        text = f"{title}. {body}" if body else title
        docs.append(Document(
            "social", "reddit", d["name"], "https://www.reddit.com" + d.get("permalink", ""),
            datetime.fromtimestamp(d["created_utc"], tz=timezone.utc), title, text,
            author=d.get("author"),
            meta={"subreddit": subreddit, "score": d.get("score"), "num_comments": d.get("num_comments")},
        ))
    return docs


class RedditPosts(PollingConnector):
    name = "reddit"

    def __init__(self, client: httpx.AsyncClient, client_id: str, secret: str, user_agent: str, poll_seconds: int):
        self.client, self.cid, self.secret = client, client_id, secret
        self.ua, self.poll_seconds = user_agent, poll_seconds
        self._token, self._expires = None, 0.0

    async def _auth(self):
        if self._token and time.time() < self._expires - 60:
            return
        r = await self.client.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"}, auth=(self.cid, self.secret),
            headers={"User-Agent": self.ua},
        )
        r.raise_for_status()
        j = r.json()
        self._token, self._expires = j["access_token"], time.time() + j.get("expires_in", 3600)

    async def fetch(self) -> list:
        await self._auth()
        headers = {"Authorization": f"bearer {self._token}", "User-Agent": self.ua}
        docs = []
        for sub in SUBREDDITS:
            r = await self.client.get(f"https://oauth.reddit.com/r/{sub}/new",
                                      params={"limit": 100, "raw_json": 1}, headers=headers)
            if r.status_code == 429:
                log.warning("reddit rate limited")
                break
            r.raise_for_status()
            docs += parse_listing(r.json(), sub)
        return docs
