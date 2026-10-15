"""Persist and load the synthetic wholesale banking book."""
from __future__ import annotations

import json

import numpy as np

from ..market.series import load_prices
from .generator import SECTOR_BETA_DEFAULT, generate_book, holding_api, write_csv
from .pricing import MarketDataMissing

CSV_PATH = "data/portfolio/portfolio.csv"


def parse_holding(r) -> dict:
    d = dict(r)
    d["terms"] = json.loads(d["terms"]) if isinstance(d["terms"], str) else d["terms"]
    return d


async def load_book(pool) -> list:
    rows = await pool.fetch("SELECT * FROM portfolio_holdings ORDER BY id")
    return [parse_holding(r) for r in rows]


async def sector_betas(pool) -> dict:
    """Beta of each sector ETF to SPY over the stored history (falls back to 1.0 where an ETF has no history)."""
    from ..stress.engine import SECTOR_ETF
    px = await load_prices(pool, ["SPY"] + list(SECTOR_ETF.values()), "2021-01-01")
    out = {}
    for sector, etf in SECTOR_ETF.items():
        if etf in px and "SPY" in px:
            j = px[[etf, "SPY"]].pct_change().dropna()
            out[sector] = float(np.polyfit(j["SPY"], j[etf], 1)[0]) if len(j) > 120 else SECTOR_BETA_DEFAULT
    return out


async def build_portfolio(pool, seed: int = 2026, csv_path: str | None = CSV_PATH) -> dict:
    """Generate the seeded book against today's real market levels and replace the stored one."""
    from ..stress.engine import load_state
    state = await load_state(pool)
    book = generate_book(state, await sector_betas(pool), seed)
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute("DELETE FROM portfolio_holdings")
            await con.executemany(
                "INSERT INTO portfolio_holdings (id, asset_type, counterparty, ticker, sector, country, notional, rating, maturity, terms) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)",
                [(h["id"], h["asset_type"], h["counterparty"], h["ticker"], h["sector"], h["country"], h["notional"],
                  h["rating"], h["maturity"], json.dumps(h["terms"])) for h in book])
    if csv_path:
        write_csv(book, state, csv_path)
    by_type = {}
    for h in book:
        by_type[h["asset_type"]] = by_type.get(h["asset_type"], 0) + 1
    return {"holdings": len(book), "byType": by_type, "seed": seed, "asof": state.asof.isoformat(), "csv": csv_path}


async def holdings_api(pool) -> dict:
    from ..stress.engine import load_state
    book = await load_book(pool)
    if not book:
        raise MarketDataMissing("no portfolio: run `make portfolio` first")
    st = await load_state(pool)
    rows = [holding_api(h, st) for h in book]
    return {"asof": st.asof.isoformat(), "holdings": rows,
            "totalMarketValue": float(sum(r["marketValue"] for r in rows)),
            "totalNotional": float(sum(abs(r["notional"]) for r in rows))}
