from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ...precedent.engine import FACTOR_ASSETS, HORIZON_IDX
from ...precedent.service import precedent_for_signal
from ..common import ApiError, etag_ok

router = APIRouter()
LOW_N, SHRINK_K = 10, 5.0


def annotate_shocks(result: dict, lib, event_type: str | None) -> dict:
    """Low-sample warning and shrinkage (design 6.4): where n < 10 the shock is also given shrunk toward the prior, the median
    move of ALL library events of the same type (or of all events when the type is unknown). w = n / (n + 5)."""
    for s in result.get("shocks", []):
        pool_ = [ev for ev in lib.events if s["assetClass"] in ev.paths and (event_type is None or ev.type == event_type)]
        if len(pool_) < 3:
            pool_ = [ev for ev in lib.events if s["assetClass"] in ev.paths]
        vals = sorted(ev.paths[s["assetClass"]][HORIZON_IDX][1] for ev in pool_)
        prior = vals[len(vals) // 2] if vals else None
        s["lowSample"] = s["n"] < LOW_N
        s["priorMedian"] = prior
        if s["lowSample"] and prior is not None:
            w = s["n"] / (s["n"] + SHRINK_K)
            s["shrunkMedian"] = w * s["median"] + (1 - w) * prior
        else:
            s["shrunkMedian"] = s["median"]
    return result


@router.get("/api/precedent/{signal_id}")
async def precedent(request: Request, signal_id: str, minSimilarity: float = Query(0.40, ge=0, le=1), k: int = Query(10, ge=1, le=30)):
    pool = request.app.state.pool
    lib = await request.app.state.library.get()
    try:
        res, _ = await precedent_for_signal(pool, lib, signal_id, minSimilarity, k)
    except KeyError:
        raise ApiError(404, "not_found", "signal not found")
    r = await pool.fetchrow("SELECT event_type, mode FROM signals WHERE id = $1", signal_id)
    res = annotate_shocks(res, lib, r["event_type"] if r["event_type"] in {e.type for e in lib.events} else None)
    res["minSimilarity"], res["libraryEvents"] = minSimilarity, len(lib)
    return etag_ok(request, res, source=r["mode"])
