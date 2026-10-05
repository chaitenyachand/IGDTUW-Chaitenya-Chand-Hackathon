"""Daily price history from Yahoo Finance (via yfinance), cached in Postgres.

yfinance is an unofficial scraper: we download once, upsert, and serve everything from our own DB.
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

UPSERT = """
INSERT INTO prices (symbol, ts, open, high, low, close, adj_close, volume)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
ON CONFLICT (symbol, ts) DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
  close=EXCLUDED.close, adj_close=EXCLUDED.adj_close, volume=EXCLUDED.volume
"""


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _download(symbol: str, start: str) -> list:
    import yfinance as yf  # imported lazily so tests and the API do not need it

    df = yf.Ticker(symbol).history(start=start, auto_adjust=False, actions=False)
    rows = []
    for ts, r in df.iterrows():
        close = float(r["Close"])
        if not _ok(close):
            continue
        d = ts.date()
        adj = float(r["Adj Close"]) if "Adj Close" in df.columns and _ok(float(r["Adj Close"])) else close
        rows.append((symbol, datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
                     float(r["Open"]), float(r["High"]), float(r["Low"]), close, adj,
                     int(r["Volume"]) if _ok(float(r["Volume"])) else 0))
    return rows


async def sync_prices(pool, symbols: list, start: str = "2000-01-01") -> dict:
    report = {}
    for sym in symbols:
        last = await pool.fetchval("SELECT max(ts) FROM prices WHERE symbol = $1", sym)
        begin = (last - timedelta(days=7)).strftime("%Y-%m-%d") if last else start
        try:
            rows = await asyncio.to_thread(_download, sym, begin)
            if rows:
                async with pool.acquire() as con:
                    await con.executemany(UPSERT, rows)
            report[sym] = len(rows)
            log.info("prices %s: %d rows from %s", sym, len(rows), begin)
        except Exception as e:
            report[sym] = f"ERROR {e!r}"
            log.warning("prices %s failed: %s", sym, e)
        await asyncio.sleep(0.5)
    return report
