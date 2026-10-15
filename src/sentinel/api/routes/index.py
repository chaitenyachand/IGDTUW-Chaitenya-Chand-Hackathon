from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict

from ...index import backtest, service
from .. import shape
from ..common import ApiError, etag_ok, limiter, ok, require_token, source_param, ttl, write_limit

router = APIRouter()


class ConfigPatch(BaseModel):
    """Accepts both the terminal's names (maxTurnover, sentimentThreshold, decay) and the engine's (turnoverCap, ...)."""
    model_config = ConfigDict(extra="forbid")
    mode: str | None = None
    kappa: float | None = None
    minWeight: float | None = None
    maxWeight: float | None = None
    deadband: float | None = None
    turnoverCap: float | None = None
    maxTurnover: float | None = None
    sentimentThreshold: float | None = None
    decay: bool | None = None
    integrityThreshold: float | None = None
    requireCorroboration: bool | None = None
    defaultHalfLifeDays: float | None = None
    normalizer: float | None = None
    zFloor: float | None = None
    costBps: float | None = None
    lookbackDays: float | None = None


def _dt(v: str | None):
    try:
        return datetime.fromisoformat(v) if v else None
    except ValueError:
        raise ApiError(422, "bad_date", f"invalid timestamp '{v}'")


@router.get("/api/index/constituents")
async def constituents(request: Request, source: str = "live"):
    source_param(source)
    pool = request.app.state.pool
    rows = await service.constituents(pool, source)
    return ok(shape.constituents(rows), source=source, benchmarkBasis=rows[0]["benchmarkBasis"] if rows else None)


@router.get("/api/index/weights")
async def weights(request: Request, source: str = "live", frm: str | None = Query(None, alias="from"),
                  to: str | None = None, limit: int = Query(2000, ge=1, le=10000)):
    """Weights over time: {tickers, points:[{ts, weights}]}. `from` / `to` are ISO timestamps."""
    source_param(source)
    pts = await service.weights_history(request.app.state.pool, source, _dt(frm), _dt(to), limit)
    return ok(shape.weights(pts, service.TICKERS), source=source)


@router.get("/api/index/rebalances")
async def rebalances(request: Request, source: str = "live", status: str | None = None, limit: int = Query(50, ge=1, le=500)):
    source_param(source)
    if status not in (None, "applied", "pending", "rejected"):
        raise ApiError(422, "bad_status", "status must be applied, pending or rejected")
    return ok([shape.rebalance(r) for r in await service.list_rebalances(request.app.state.pool, source, status, limit)], source=source)


@router.post("/api/index/rebalances/{rebalance_id}/approve", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def approve(request: Request, rebalance_id: str):
    return await _decide(request, rebalance_id, True)


@router.post("/api/index/rebalances/{rebalance_id}/reject", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def reject(request: Request, rebalance_id: str):
    return await _decide(request, rebalance_id, False)


async def _decide(request, rebalance_id, approve_: bool):
    try:
        ev = await service.decide(request.app.state.pool, request.app.state.redis, rebalance_id, approve_)
    except KeyError:
        raise ApiError(404, "not_found", "rebalance not found")
    except service.IndexError_ as e:
        raise ApiError(409, "conflict", str(e))
    return ok(shape.rebalance(ev), source=ev["source"])


@router.get("/api/index/performance")
async def performance(request: Request, days: int = Query(250, ge=30, le=2000), source: str = "live"):
    source_param(source)
    pool = request.app.state.pool
    res = await ttl.get(("perf", days, source), 60, lambda: backtest.run_backtest(pool, days, source))
    return etag_ok(request, shape.performance(res), source="backfill")


@router.get("/api/index/config")
async def get_config(request: Request):
    return ok(shape.index_config(await service.get_config(request.app.state.pool)))


@router.put("/api/index/config", dependencies=[Depends(require_token)])
@router.post("/api/index/config", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def put_config(request: Request, patch: ConfigPatch):
    """Save (partial) configuration. PUT and POST are the same call: the terminal posts, API clients may put."""
    try:
        new = await service.set_config(request.app.state.pool, request.app.state.redis,
                                       shape.index_config_patch(patch.model_dump(exclude_none=True)))
    except ValueError as e:
        raise ApiError(422, "invalid_config", str(e))
    ttl.clear()
    return ok(shape.index_config(new))


@router.post("/api/index/recompute", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def recompute(request: Request):
    ev = await service.recompute(request.app.state.pool, request.app.state.redis, actor="api")
    return ok({"rebalance": shape.rebalance(ev) if ev else None, "changed": ev is not None})
