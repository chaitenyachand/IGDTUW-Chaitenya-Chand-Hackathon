"""Headline cleaning: strip site names and boilerplate that publishers append to titles."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..ingest.base import normalize_text

_DELIM = re.compile(r"\s+[|\u2013\u2014]\s+|\s+-\s+")
_STOP = {"the", "of", "and", "a", "an", "in", "for"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _is_site_segment(seg: str, hostkey: str) -> bool:
    seg = seg.strip().strip("\u2026.").strip()
    words = [w for w in seg.split() if _norm(w) and _norm(w) not in _STOP]
    if not seg or len(seg.split()) > 6 or not words or not hostkey:
        return False
    return all(_norm(w) in hostkey for w in words)


def _is_boilerplate(seg: str) -> bool:
    s = seg.strip().lower()
    return len(s.split()) <= 4 and (s.endswith("news") or s in {"home", "official site", "live updates"})


def clean_title(title: str, url: str | None = None) -> str:
    t = normalize_text(title)
    hostkey = _norm(urlsplit(url).netloc) if url else ""
    # trailing site names / boilerplate
    while True:
        ms = list(_DELIM.finditer(t))
        if not ms:
            break
        m = ms[-1]
        seg = t[m.end():]
        if _is_boilerplate(seg) or _is_site_segment(seg, hostkey):
            t = t[:m.start()].rstrip()
        else:
            break
    # leading site name ('West Seattle Blog... | HEADLINE')
    m = _DELIM.search(t)
    if m and _is_site_segment(t[:m.start()], hostkey) and len(t[m.end():].split()) >= 3:
        t = t[m.end():]
    return t.strip()
