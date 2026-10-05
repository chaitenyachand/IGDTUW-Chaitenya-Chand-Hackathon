"""GDELT 2.0 Global Knowledge Graph (GKG) connector. Updated by GDELT every 15 minutes.

GKG rows carry the page title (in Extras), themes, organizations and a tone vector.
We keep English records whose themes are finance/risk relevant.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import datetime, timezone
from typing import Optional

import httpx

from .. import store
from .base import Document, PollingConnector, normalize_text

log = logging.getLogger(__name__)

LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# Theme prefixes that matter for financial risk.
FINANCE_PREFIXES = (
    "ECON_", "EPU_", "SANCTION", "ARMEDCONFLICT", "CYBER_ATTACK", "NATURAL_DISASTER",
    "STRIKE", "BLOCKADE", "TERROR", "WB_1104_MACROECONOMIC", "WB_332_BANKING", "WB_1920_FINANCIAL_SECTOR",
)
_TITLE = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)


def _strip_offsets(field: str) -> list:
    """'THEME,123;THEME2,456' or 'Org,123;...' -> ['THEME','THEME2']"""
    return [p.split(",")[0] for p in field.split(";") if p]


def parse_gkg_line(cols: list) -> Optional[Document]:
    if len(cols) < 16:
        return None
    rec_id, date, source, url = cols[0], cols[1], cols[3], cols[4]
    themes = _strip_offsets(cols[8]) if len(cols) > 8 else []
    orgs = _strip_offsets(cols[14]) if len(cols) > 14 else []
    tone = cols[15].split(",") if cols[15] else []
    translation = cols[25] if len(cols) > 25 else ""
    extras = cols[26] if len(cols) > 26 else ""

    if translation.strip():            # translated from another language: skip
        return None
    m = _TITLE.search(extras)
    title = normalize_text(m.group(1)) if m else ""
    if not title:
        return None
    matched = sorted({t for t in themes if t.startswith(FINANCE_PREFIXES)})
    if not matched:
        return None
    try:
        published = datetime.strptime(date, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    def f(i):
        try:
            return float(tone[i])
        except (IndexError, ValueError):
            return None

    meta = {
        "gkg_id": rec_id, "domain": source, "themes": matched[:25],
        "organizations": orgs[:15],
        "tone": f(0), "positive": f(1), "negative": f(2), "polarity": f(3),
        "word_count": f(6),
    }
    return Document("news", "gdelt", rec_id, url, published, title, title, author=source, meta=meta)


def parse_gkg_zip(data: bytes, max_records: int = 2000) -> list:
    docs = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            for raw in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
                d = parse_gkg_line(raw.rstrip("\n").split("\t"))
                if d:
                    docs.append(d)
                    if len(docs) >= max_records:
                        break
    return docs


class GdeltGKG(PollingConnector):
    name = "gdelt"

    def __init__(self, pool, client: httpx.AsyncClient, poll_seconds: int, max_records: int = 2000):
        self.pool, self.client = pool, client
        self.poll_seconds, self.max_records = poll_seconds, max_records

    async def fetch(self) -> list:
        r = await self.client.get(LASTUPDATE_URL, follow_redirects=True)
        r.raise_for_status()
        url = next((ln.split()[-1] for ln in r.text.splitlines() if ln.strip().endswith("gkg.csv.zip")), None)
        if not url:
            raise RuntimeError("GKG file not listed in lastupdate.txt")
        if await store.get_config(self.pool, "gdelt:last_gkg") == url:
            return []
        z = await self.client.get(url, follow_redirects=True, timeout=60)
        z.raise_for_status()
        docs = parse_gkg_zip(z.content, self.max_records)
        await store.set_config(self.pool, "gdelt:last_gkg", url)
        log.info("gdelt: %s -> %d relevant records", url.rsplit("/", 1)[-1], len(docs))
        return docs
