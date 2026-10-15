"""Deterministic TEST-ONLY market data: a correlated factor world (market, sectors, rates, spreads, FX, oil, VIX) with
shocks injected on the PRECEDENT library event dates. It is never shipped as data: production reads Yahoo and FRED."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from sentinel.precedent.events import EVENTS
from sentinel.universe import FRED_SERIES, PROXY_SYMBOLS, UNIVERSE

NEGATIVE = {"Geopolitical", "Credit Event", "Macroeconomic", "Cyber", "Natural Disaster", "Supply Chain", "Regulatory"}
BETAS = {"equity_index": 1.0, "energy": 1.1, "financials": 1.2, "technology": 1.15, "health_care": 0.7, "industrials": 1.05,
         "utilities": 0.5, "staples": 0.55, "discretionary": 1.1, "communication": 1.0, "banks": 1.4, "high_yield": 0.45,
         "inv_grade": 0.12, "gold": -0.05, "oil": 0.6, "dollar": -0.1}


def business_days(start="2005-06-01", end="2026-10-09"):
    return pd.bdate_range(start, end)


def make_world(start="2005-06-01", end="2026-10-09", seed=1) -> dict:
    rng = np.random.default_rng(seed)
    idx = business_days(start, end)
    n = len(idx)
    stress = np.zeros(n)
    shock = np.zeros(n)
    for _, react, typ, _, _ in EVENTS:
        pos = int(idx.searchsorted(pd.Timestamp(react)))
        if 0 < pos < n - 40:
            mag = (0.012 + 0.03 * rng.random()) * (-1 if typ in NEGATIVE else 1)
            shock[pos] += mag
            stress[pos:pos + 25] += np.exp(-np.arange(min(25, n - pos)) / 8.0)
    sig = 0.007 + 0.006 * np.clip(stress, 0, 3)
    m = rng.normal(0.0003, 1, n) * sig + shock * (0.6 + 0.4 * np.exp(-np.arange(n) * 0))
    # decaying aftershocks: day 2..4 partially follow day 1
    for k, f in ((1, 0.35), (2, 0.2), (3, 0.1)):
        m[k:] += f * shock[:-k]
    w = {"market": m}
    prices = {"SPY": 100 * np.exp(np.cumsum(m))}
    for key, sym in PROXY_SYMBOLS.items():
        if sym in ("SPY", "^VIX"):
            continue
        b = BETAS.get(key, 0.3)
        r = b * m + rng.normal(0, 0.004, n) + (0.0 if key != "oil" else rng.normal(0, 0.012, n))
        prices[sym] = 50 * np.exp(np.cumsum(r))
    for s in UNIVERSE:
        beta = float(rng.uniform(0.6, 1.5))
        prices[s.ticker] = 80 * np.exp(np.cumsum(beta * m + rng.normal(0, 0.011, n)))
    vix = np.clip(14 + 400 * np.abs(m) * 0.8 + 35 * np.clip(stress, 0, 3) + rng.normal(0, 1, n), 9, 80)
    prices["^VIX"] = vix
    rate_chg = 0.01 * rng.normal(0, 1, n) - 0.8 * m * 0.5
    y10 = np.clip(3.0 + np.cumsum(rate_chg), 0.5, 6.5)
    macro = {"DGS10": y10, "DGS2": np.clip(y10 - 0.5 + 0.1 * np.sin(np.arange(n) / 300), 0.2, 6.5),
             "DGS5": np.clip(y10 - 0.2, 0.3, 6.5), "DGS30": y10 + 0.3, "DGS3MO": np.clip(y10 - 1.0, 0.05, 6.0),
             "T10Y2Y": np.full(n, 0.5), "DFF": np.clip(y10 - 1.2, 0.05, 6.0), "VIXCLS": vix,
             "BAMLC0A0CM": np.clip(1.2 - 6 * m + 0.01 * rng.normal(0, 1, n), 0.5, 6).cumsum() * 0 + np.clip(1.2 + np.cumsum(-0.5 * m + 0.002 * rng.normal(0, 1, n)), 0.6, 5),
             "BAMLH0A0HYM2": np.clip(4.0 + np.cumsum(-2.0 * m + 0.006 * rng.normal(0, 1, n)), 2.0, 15),
             "DTWEXBGS": 120 * np.exp(np.cumsum(-0.1 * m + 0.002 * rng.normal(0, 1, n))),
             "DCOILWTICO": 70 * np.exp(np.cumsum(0.5 * m + 0.012 * rng.normal(0, 1, n))),
             "DEXUSEU": 1.08 * np.exp(np.cumsum(0.004 * rng.normal(0, 1, n) + 0.3 * m * 0.2)),
             "DEXUSUK": 1.26 * np.exp(np.cumsum(0.005 * rng.normal(0, 1, n) + 0.3 * m * 0.2))}
    assert set(macro) >= set(FRED_SERIES), set(FRED_SERIES) - set(macro)
    return {"idx": idx, "prices": prices, "macro": macro, "market": m}


async def seed_market(pool, start="2005-06-01", end="2026-10-09", seed=1) -> dict:
    w = make_world(start, end, seed)
    idx = w["idx"]
    ts = [datetime(d.year, d.month, d.day, tzinfo=timezone.utc) for d in idx]
    await pool.execute("TRUNCATE prices, macro_series")
    rows = []
    for sym, arr in w["prices"].items():
        rows += [(sym, t, float(v), float(v), float(v), float(v), float(v), 1_000_000) for t, v in zip(ts, arr)]
    async with pool.acquire() as con:
        await con.copy_records_to_table("prices", records=rows,
                                        columns=["symbol", "ts", "open", "high", "low", "close", "adj_close", "volume"])
        mrows = [(sid, t, float(v)) for sid, arr in w["macro"].items() for t, v in zip(ts, arr)]
        await con.copy_records_to_table("macro_series", records=mrows, columns=["series_id", "ts", "value"])
    await pool.executemany(
        "INSERT INTO entities (ticker, name, sector, aliases) VALUES ($1,$2,$3,$4) ON CONFLICT (ticker) DO NOTHING",
        [(s.ticker, s.name, s.sector, list(s.aliases)) for s in UNIVERSE])
    return w
