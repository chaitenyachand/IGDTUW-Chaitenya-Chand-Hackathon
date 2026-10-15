from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ...risk import index as risk_index
from .. import shape
from ..common import source_param, ok, ttl

router = APIRouter()


@router.get("/api/risk-index")
async def risk(request: Request, source: str = "live", hours: int = Query(72, ge=1, le=24 * 90)):
    source_param(source)
    pool = request.app.state.pool
    cur = await ttl.get(("risk", source), 10, lambda: risk_index.current(pool, source))
    return ok(shape.risk_index(cur, await risk_index.history(pool, source, hours)), source=source)
