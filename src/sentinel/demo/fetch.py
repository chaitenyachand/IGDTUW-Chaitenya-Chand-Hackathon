"""Download the real archived articles of a replay episode from the public GDELT 2.0 GKG archive.

GKG files are published every 15 minutes since February 2015 at data.gdeltproject.org/gdeltv2/<YYYYMMDDHHMMSS>.gkg.csv.zip.
We sample the episode window (default one file per hour), keep English records whose themes are finance-relevant (the live
connector's own filter and parser) and whose title contains an episode keyword, and write them as JSONL.
Items keep GDELT's processing time as `publishedAt` (the closest public record of when the story was first seen).
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone

import httpx

from ..ingest.gdelt import parse_gkg_line
from .episodes import episode_path, get_episode

log = logging.getLogger(__name__)
GKG_URL = "http://data.gdeltproject.org/gdeltv2/{stamp}.gkg.csv.zip"


def gkg_stamps(start: datetime, end: datetime, step_minutes: int = 60) -> list:
    """GKG file stamps (15-minute grid) from `start` to `end`, one every `step_minutes`."""
    step = max(15, (step_minutes // 15) * 15)
    t = start.astimezone(timezone.utc).replace(minute=(start.minute // 15) * 15, second=0, microsecond=0)
    out = []
    while t < end:
        out.append(t.strftime("%Y%m%d%H%M%S"))
        t += timedelta(minutes=step)
    return out


def matches(title: str, keywords: list) -> bool:
    t = title.lower()
    return any(k.lower() in t for k in keywords)


def records_from_zip(data: bytes, keywords: list, start: datetime, end: datetime, episode_id: str, max_records: int = 400) -> list:
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        with z.open(z.namelist()[0]) as fh:
            for raw in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
                d = parse_gkg_line(raw.rstrip("\n").split("\t"))
                if d is None or not (start <= d.published_at < end) or not matches(d.title, keywords):
                    continue
                out.append({"episode": episode_id, "key": d.key, "source": d.source_name, "sourceType": d.source_type,
                            "url": d.url, "publishedAt": d.published_at.isoformat(), "title": d.title, "text": d.text,
                            "author": d.author, "language": d.language, "meta": d.meta})
                if len(out) >= max_records:
                    break
    return out


async def fetch_episode(episode_id: str, step_minutes: int = 60, max_per_file: int = 400, directory=None,
                        client: httpx.AsyncClient | None = None, pause: float = 0.3) -> dict:
    ep = get_episode(episode_id, directory)
    own = client is None
    client = client or httpx.AsyncClient(timeout=90, follow_redirects=True)
    stamps = gkg_stamps(ep["start"], ep["end"], step_minutes)
    seen, records, missing = set(), [], 0
    try:
        for stamp in stamps:
            try:
                r = await client.get(GKG_URL.format(stamp=stamp))
                r.raise_for_status()
            except httpx.HTTPError as e:
                missing += 1
                log.warning("gkg %s unavailable: %r", stamp, e)
                continue
            for rec in records_from_zip(r.content, ep["keywords"], ep["start"], ep["end"], episode_id, max_per_file):
                if rec["url"] in seen:
                    continue
                seen.add(rec["url"])
                records.append(rec)
            await asyncio.sleep(pause)
    finally:
        if own:
            await client.aclose()
    records.sort(key=lambda r: (r["publishedAt"], r["key"]))
    path = episode_path(episode_id, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"episode": episode_id, "files": len(stamps), "filesMissing": missing, "documents": len(records), "path": str(path)}
