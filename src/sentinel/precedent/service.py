"""Glue between stored signals and the PRECEDENT engine.

Point-in-time: analogs must predate the signal and the volatility regime is the VIX as of the signal, so a replayed or
backfilled signal never sees its own future (design principle 4)."""
from __future__ import annotations

import numpy as np

from ..taxonomy import EVENT_TYPES
from .engine import DEFAULT_MIN_SIM, Library, build_result


async def vix_asof(pool, ts=None):
    """Last VIX close on or before `ts` (latest when ts is None)."""
    v = await pool.fetchval(
        "SELECT COALESCE(adj_close, close) FROM prices WHERE symbol = '^VIX' AND ($1::timestamptz IS NULL OR ts <= $1) "
        "ORDER BY ts DESC LIMIT 1", ts)
    return float(v) if v is not None else None


async def latest_vix(pool):
    return await vix_asof(pool, None)


async def precedent_for_signal(pool, lib: Library, signal_id: str, min_sim: float = DEFAULT_MIN_SIM, k: int = 10):
    """(PrecedentResult, analogs). Raises KeyError for an unknown signal."""
    r = await pool.fetchrow("SELECT embedding, event_type, ts FROM signals WHERE id = $1", signal_id)
    if r is None:
        raise KeyError(signal_id)
    if not r["embedding"] or len(lib) == 0:
        return build_result(signal_id, []), []
    vix = await vix_asof(pool, r["ts"])
    et = r["event_type"] if r["event_type"] in EVENT_TYPES else None
    analogs = lib.match(np.asarray(r["embedding"], dtype=float), et, vix, min_sim, k, before=r["ts"].date())
    return build_result(signal_id, analogs), analogs
