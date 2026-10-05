"""Macro and rates series from FRED (free API key)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)
URL = "https://api.stlouisfed.org/fred/series/observations"
UPSERT = """INSERT INTO macro_series (series_id, ts, value) VALUES ($1,$2,$3)
            ON CONFLICT (series_id, ts) DO UPDATE SET value = EXCLUDED.value"""


def parse_observations(series_id: str, payload: dict) -> list:
    rows = []
    for o in payload.get("observations", []):
        v = o.get("value")
        if v in (None, "", "."):
            continue
        d = datetime.strptime(o["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        rows.append((series_id, d, float(v)))
    return rows


async def sync_fred(pool, api_key: str, series: dict, start: str = "2000-01-01") -> dict:
    if not api_key:
        raise RuntimeError("FRED_API_KEY is not set")
    report = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for sid in series:
            try:
                r = await client.get(URL, params={"series_id": sid, "api_key": api_key,
                                                  "file_type": "json", "observation_start": start})
                r.raise_for_status()
                rows = parse_observations(sid, r.json())
                if rows:
                    async with pool.acquire() as con:
                        await con.executemany(UPSERT, rows)
                report[sid] = f"{len(rows)} rows, {rows[0][1].date()} to {rows[-1][1].date()}" if rows else "0 rows"
            except Exception as e:
                report[sid] = f"ERROR {e!r}"
            log.info("fred %s: %s", sid, report[sid])
    return report
