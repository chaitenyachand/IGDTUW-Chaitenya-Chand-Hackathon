from __future__ import annotations

from fastapi import APIRouter, Request

from ...portfolio import pricing
from ...portfolio import store as pstore
from ...stress import engine as se
from .. import shape
from ..common import etag_ok

router = APIRouter()


@router.get("/api/portfolio")
async def portfolio(request: Request):
    data = await pstore.holdings_api(request.app.state.pool)
    return etag_ok(request, data["holdings"], source="synthetic", asOf=shape.iso_day(data["asof"]),
                   totalMarketValue=data["totalMarketValue"], totalNotional=data["totalNotional"])


@router.get("/api/portfolio/exposure")
async def exposure(request: Request):
    """Exposure by country and sector with the loss each would take under one fixed reference shock
    (equity -10%, +100 bp rates, +100 bp IG credit spreads) so the columns are comparable."""
    ctx = (await request.app.state.stress.get()).ctx
    shocked = pricing.apply_shocks(ctx.state, se.expand_ui_shocks(shape.REFERENCE_SHOCK, ctx))
    loss = lambda h: pricing.value(h, ctx.state) - pricing.value(h, shocked)
    return etag_ok(request, shape.exposure(ctx, loss), source="synthetic")
