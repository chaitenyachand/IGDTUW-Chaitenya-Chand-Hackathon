"""Bluesky Jetstream connector: public, free WebSocket firehose of posts, filtered in-process.

A post is kept only if it is clearly finance related: a cashtag, a universe company name together
with a finance word, or a macro/risk term. Spam-like posts (many cashtags) are dropped.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Callable, Optional

import websockets

from ..universe import UNIVERSE
from .base import Document, StreamingConnector, normalize_text

log = logging.getLogger(__name__)

FINANCE_WORDS = ("stock", "stocks", "shares", "earnings", "revenue", "guidance", "downgrade", "upgrade",
                 "acquisition", "merger", "lawsuit", "layoffs", "bankruptcy", "dividend", "buyback",
                 "ipo", "valuation", "investors", "market cap", "short seller", "sec filing")
MACRO_TERMS = ("federal reserve", "the fed", "rate cut", "rate hike", "interest rates", "inflation",
               "recession", "sanctions", "default", "bankruptcy", "tariff", "tariffs", "opec",
               "oil prices", "bank run", "credit rating", "yield curve", "debt ceiling",
               "stock market", "s&p 500", "nasdaq", "dow jones", "treasury yields")


def build_matcher() -> Callable[[str], Optional[dict]]:
    names = sorted({a for s in UNIVERSE for a in s.aliases}, key=len, reverse=True)
    name_re = re.compile(r"\b(" + "|".join(map(re.escape, names)) + r")\b", re.I)
    fin_re = re.compile(r"\b(" + "|".join(map(re.escape, FINANCE_WORDS)) + r")\b", re.I)
    macro_re = re.compile(r"\b(" + "|".join(map(re.escape, MACRO_TERMS)) + r")\b", re.I)
    cashtag = re.compile(r"(?<![\w$])\$([A-Za-z]{1,5})\b")

    def match(text: str) -> Optional[dict]:
        tags = {m.upper() for m in cashtag.findall(text)}
        if len(tags) > 5:
            return None  # cashtag spam
        if tags:
            return {"reason": "cashtag", "tickers": sorted(tags)}
        hits = {n.lower() for n in name_re.findall(text)}
        if hits and fin_re.search(text):
            return {"reason": "name+finance", "names": sorted(hits)}
        if macro_re.search(text):
            return {"reason": "macro"}
        return None

    return match


def parse_commit(msg: dict, matcher: Callable) -> Optional[Document]:
    if msg.get("kind") != "commit":
        return None
    c = msg.get("commit") or {}
    if c.get("operation") != "create" or c.get("collection") != "app.bsky.feed.post":
        return None
    rec = c.get("record") or {}
    text = normalize_text(rec.get("text"))
    if len(text) < 20:
        return None
    langs = rec.get("langs") or []
    if langs and "en" not in langs:
        return None
    m = matcher(text)
    if not m:
        return None
    did, rkey = msg.get("did"), c.get("rkey")
    if not did or not rkey:
        return None
    # Observation time is authoritative: the author-supplied createdAt can be arbitrary.
    observed = datetime.fromtimestamp(msg["time_us"] / 1e6, tz=timezone.utc)
    return Document(
        "social", "bluesky", f"{did}/{rkey}",
        f"https://bsky.app/profile/{did}/post/{rkey}", observed,
        text[:140], text, author=did, language="en",
        meta={"match": m, "createdAt": rec.get("createdAt")},
    )


class BlueskyJetstream(StreamingConnector):
    name = "bluesky"

    def __init__(self, url: str):
        self.url = url
        self.matcher = build_matcher()

    async def stream(self):
        backoff, cursor = 1, None
        while True:
            params = "wantedCollections=app.bsky.feed.post" + (f"&cursor={cursor}" if cursor else "")
            try:
                async with websockets.connect(f"{self.url}?{params}", max_size=2**20, ping_interval=20) as ws:
                    backoff = 1
                    log.info("bluesky: connected")
                    async for raw in ws:
                        msg = json.loads(raw)
                        cursor = msg.get("time_us", cursor)
                        doc = parse_commit(msg, self.matcher)
                        if doc:
                            yield doc
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("bluesky disconnected (%s); retry in %ss", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                if cursor:
                    cursor = int(cursor) - 5_000_000  # resume 5 seconds earlier to avoid gaps
