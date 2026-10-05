"""Common document model, text normalization and connector interfaces."""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_TRACKING = {"fbclid", "gclid", "ref", "cmpid", "ocid", "mod", "taid", "guccounter"}


def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", s))).strip()


def canonical_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    p = urlsplit(url.strip())
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not (k.lower().startswith("utm_") or k.lower() in _TRACKING)
    ]
    path = p.path.rstrip("/") or "/"
    return urlunsplit(((p.scheme or "https").lower(), host, path, urlencode(query), ""))


# ---- SimHash (64-bit) for near-duplicate detection ----
_TOKEN = re.compile(r"[a-z0-9$&']+")


def _h64(tok: str) -> int:
    return int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")


def simhash(text: str, bits: int = 64) -> int:
    toks = _TOKEN.findall(text.lower())
    if not toks:
        return 0
    feats = toks + [a + " " + b for a, b in zip(toks, toks[1:])]
    v = [0] * bits
    for f in feats:
        h = _h64(f)
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(bits):
        if v[i] > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def to_signed(x: int) -> int:
    return x - (1 << 64) if x >= (1 << 63) else x


def to_unsigned(x: int) -> int:
    return x + (1 << 64) if x < 0 else x


@dataclass
class Document:
    source_type: str          # 'news' | 'social'
    source_name: str          # e.g. 'gdelt', 'sec_edgar', 'rss:cnbc_top', 'bluesky', 'reddit'
    key: str                  # unique within the source
    url: Optional[str]
    published_at: datetime
    title: str
    text: str
    author: Optional[str] = None
    language: Optional[str] = "en"
    meta: dict = field(default_factory=dict)
    mode: str = "live"

    def __post_init__(self):
        if self.published_at.tzinfo is None:
            self.published_at = self.published_at.replace(tzinfo=timezone.utc)

    @property
    def id(self) -> str:
        return hashlib.sha1(f"{self.source_name}:{self.key}".encode()).hexdigest()

    @property
    def raw_hash(self) -> str:
        return hashlib.sha256(f"{self.title}\n{self.text}".encode()).hexdigest()

    @property
    def canonical_url(self) -> Optional[str]:
        return canonical_url(self.url) if self.source_type == "news" else None


class PollingConnector:
    name: str = ""
    poll_seconds: int = 300

    async def fetch(self) -> list:
        raise NotImplementedError


class StreamingConnector:
    name: str = ""

    def stream(self) -> AsyncIterator[Document]:
        raise NotImplementedError
