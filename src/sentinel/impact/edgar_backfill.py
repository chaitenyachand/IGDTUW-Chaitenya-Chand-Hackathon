"""Backfill the full SEC 8-K history of the index stocks, then label every filing with its real abnormal return."""
from __future__ import annotations

import asyncio
import logging

import httpx

from ..market.series import load_macro, load_prices
from ..universe import UNIVERSE
from .event_study import event_study, parse_filings, reaction_day

log = logging.getLogger(__name__)
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE = "https://data.sec.gov/submissions/{name}"


async def fetch_history(client: httpx.AsyncClient, cik: int, ticker: str) -> list:
    r = await client.get(SUBMISSIONS.format(cik=cik))
    r.raise_for_status()
    js = r.json()
    blocks = [(js.get("filings") or {}).get("recent") or {}]
    for f in (js.get("filings") or {}).get("files", []):          # older filings live in archive files
        await asyncio.sleep(0.2)
        rr = await client.get(ARCHIVE.format(name=f["name"]))
        rr.raise_for_status()
        blocks.append(rr.json())
    rows = []
    for b in blocks:
        rows += parse_filings(b, ticker)
    return rows


async def backfill_edgar(pool, user_agent: str) -> dict:
    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": user_agent}) as client:
        r = await client.get(TICKERS_URL)
        r.raise_for_status()
        by_ticker = {v["ticker"].upper(): int(v["cik_str"]) for v in r.json().values()}
        report = {}
        for s in UNIVERSE:
            cik = by_ticker.get(s.ticker)
            if not cik:
                report[s.ticker] = "no CIK"
                continue
            rows = await fetch_history(client, cik, s.ticker)
            async with pool.acquire() as con:
                await con.executemany(
                    "INSERT INTO corporate_events (id, ticker, filed_at, form, items, event_type) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
                    [(x["id"], x["ticker"], x["filed_at"], x["form"], x["items"], x["event_type"]) for x in rows])
            report[s.ticker] = len(rows)
            log.info("edgar history %s: %d 8-K filings", s.ticker, len(rows))
            await asyncio.sleep(0.3)
    return report


async def label_events(pool) -> dict:
    """Fill car3 / volatility / VIX for every filing that has none yet (needs `make prices` first)."""
    rows = await pool.fetch("SELECT id, ticker, filed_at FROM corporate_events WHERE car3 IS NULL AND labeled_at IS NULL")
    if not rows:
        return {"labelled": 0, "skipped": 0}
    tickers = sorted({r["ticker"] for r in rows})
    px = await load_prices(pool, tickers + ["SPY"], "1999-01-01")
    macro = await load_macro(pool, ["VIXCLS"], "1999-01-01")
    vix = macro["VIXCLS"].dropna() if "VIXCLS" in macro else None
    done = skipped = 0
    for r in rows:
        t0 = reaction_day(r["filed_at"])
        res = event_study(px[r["ticker"]].dropna(), px["SPY"].dropna(), t0) if r["ticker"] in px else None
        if not res:
            skipped += 1
            await pool.execute("UPDATE corporate_events SET labeled_at = now() WHERE id = $1", r["id"])
            continue
        v = None
        if vix is not None:
            pos = int(vix.index.searchsorted(t0))
            v = float(vix.iloc[pos - 1]) if 1 <= pos <= len(vix) else None
        await pool.execute(
            """UPDATE corporate_events SET t0=$2, car3=$3, abs_car3=$4, ar1=$5, beta=$6, vol60=$7, prior_abs=$8, vix_prev=$9, labeled_at=now()
               WHERE id=$1""", r["id"], t0.date(), res["car3"], abs(res["car3"]), res["ar1"], res["beta"], res["vol60"],
            res["prior_abs"], v)
        done += 1
    return {"labelled": done, "skipped": skipped}
