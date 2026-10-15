from __future__ import annotations

from fastapi import APIRouter, Request

from ...model import metrics
from .. import shape
from ..common import etag_ok, ttl

router = APIRouter()


@router.get("/api/model/metrics")
async def model_metrics(request: Request):
    data = await ttl.get("model", 30, lambda: metrics.collect(request.app.state.pool))
    data = {k: v for k, v in data.items() if k != "asOf"}       # asOf would defeat the ETag
    return etag_ok(request, shape.model_metrics(data))
