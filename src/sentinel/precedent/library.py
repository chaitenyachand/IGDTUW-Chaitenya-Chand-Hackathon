"""Build the PRECEDENT library: embed each event and compute its real forward market reaction from stored prices."""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

from ..market.series import forward_path, level_path, load_macro, load_prices, path_stats
from ..universe import PROXY_SYMBOLS
from .events import library_rows

HORIZON = 30
FACTOR_KEYS = {"dgs10_bps": ("DGS10", 100.0), "dgs2_bps": ("DGS2", 100.0)}


async def build_library(pool, embed_fn, horizon: int = HORIZON) -> dict:
    rows = library_rows()
    emb = embed_fn([f"{r['title']}. {r['event_type']} event in {r['region']}." for r in rows])
    prices = await load_prices(pool, list(PROXY_SYMBOLS.values()), "1999-01-01")
    macro = await load_macro(pool, ["DGS10", "DGS2", "VIXCLS"], "1999-01-01")
    if prices.empty:
        raise RuntimeError("no prices in the database: run `make prices` first")
    report = {"events": len(rows), "with_paths": 0, "assets": {}}
    async with pool.acquire() as con:
        async with con.transaction():
            for r, e in zip(rows, emb):
                react = pd.Timestamp(r["reaction_date"])
                vix = None
                if "VIXCLS" in macro:
                    s = macro["VIXCLS"].dropna()
                    pos = int(s.index.searchsorted(react))
                    vix = float(s.iloc[pos - 1]) if 1 <= pos <= len(s) else None
                await con.execute(
                    """INSERT INTO event_library (id, title, summary, event_date, reaction_date, event_type, region, vix_level, embedding)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                       ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, summary=EXCLUDED.summary, event_type=EXCLUDED.event_type,
                         region=EXCLUDED.region, vix_level=EXCLUDED.vix_level, embedding=EXCLUDED.embedding""",
                    r["id"], r["title"], r["summary"], date.fromisoformat(r["event_date"]), date.fromisoformat(r["reaction_date"]),
                    r["event_type"], r["region"], vix, [round(float(x), 5) for x in e])
                await con.execute("DELETE FROM event_outcomes WHERE event_id = $1", r["id"])
                got = 0
                for key, sym in PROXY_SYMBOLS.items():
                    if sym not in prices:
                        continue
                    p = forward_path(prices[sym], react, horizon)
                    if p is None:
                        continue
                    mdd, rec = path_stats(p)
                    await con.execute("INSERT INTO event_outcomes (event_id, asset_key, path, max_drawdown, recovery_days) VALUES ($1,$2,$3::jsonb,$4,$5)",
                                      r["id"], key, json.dumps(p), mdd, rec)
                    report["assets"][key] = report["assets"].get(key, 0) + 1
                    got += 1
                for key, (sid, scale) in FACTOR_KEYS.items():
                    if sid in macro:
                        p = level_path(macro[sid], react, horizon, scale)
                        if p:
                            await con.execute("INSERT INTO event_outcomes (event_id, asset_key, path, max_drawdown, recovery_days) VALUES ($1,$2,$3::jsonb,NULL,NULL)",
                                              r["id"], key, json.dumps(p))
                if "VIXCLS" in macro:
                    p = level_path(macro["VIXCLS"], react, horizon, 1.0)
                    if p:
                        await con.execute("INSERT INTO event_outcomes (event_id, asset_key, path, max_drawdown, recovery_days) VALUES ($1,'vix_pts',$2::jsonb,NULL,NULL)",
                                          r["id"], json.dumps(p))
                report["with_paths"] += int(got > 0)
    return report
