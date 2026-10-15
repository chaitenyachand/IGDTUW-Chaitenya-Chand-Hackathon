from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ...stress import brief
from ...stress import engine as se
from ...stress import service as ss
from .. import shape
from ..common import ApiError, etag_ok, limiter, ok, require_token, source_param, write_limit

router = APIRouter()
# "pct" factors are fractions (-0.15 = -15%); rates and credit_spread are basis points
UI_RANGES = {"equity": (-0.9, 1.0), "rates": (-500, 1000), "credit_spread": (-300, 2000), "fx": (-0.5, 0.5),
             "commodities": (-0.9, 3.0), "volatility": (-0.5, 2.0)}


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class RunBody(Camel):
    mode: str | None = Field(None, pattern="^(calibrated|manual)$")
    scenario_id: str | None = None
    signal_id: str | None = None
    shocks: list[dict] | dict | None = None


class RuleBody(Camel):
    id: str | None = Field(None, pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    last_fired: str | None = None                                  # echoed back by the terminal; ignored
    event_type: str
    min_impact: float
    min_integrity: float | None = None
    scenario_id: str | None = None
    enabled: bool = True
    cooldown_minutes: int = 60


class WatchBody(Camel):
    event_types: list[str]


class WatchToggle(Camel):
    event_type: str
    on_watchlist: bool


def _check_shocks(shocks):
    for k, v in ss._shock_dict(shocks).items():
        if k not in UI_RANGES:
            raise ApiError(422, "bad_shock", f"unknown factor '{k}'; use {sorted(UI_RANGES)}")
        lo, hi = UI_RANGES[k]
        if not lo <= v <= hi:
            raise ApiError(422, "bad_shock", f"{k} must be between {lo} and {hi}")


async def _rt(request):
    return await request.app.state.stress.get()


@router.get("/api/stress/scenarios")
async def scenarios(request: Request):
    rt = await _rt(request)
    armed = {r["scenarioId"] for r in await ss.list_rules(request.app.state.pool) if r["enabled"]}
    return etag_ok(request, se.build_scenarios(rt.lib, rt.ctx, armed), source="synthetic")


@router.post("/api/stress/run", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def run(request: Request, body: RunBody):
    if body.shocks:
        _check_shocks(body.shocks)
    rt = await _rt(request)
    req = {"mode": body.mode, "scenarioId": body.scenario_id, "signalId": body.signal_id, "shocks": body.shocks}
    try:
        res = await ss.execute(request.app.state.pool, request.app.state.redis, rt, req, actor="api")
    except ss.StressError as e:
        raise ApiError(422, "stress_error", str(e))
    return ok(res, source="synthetic")


@router.get("/api/stress/runs")
async def runs(request: Request, source: str = "live", limit: int = Query(30, ge=1, le=200)):
    source_param(source)
    return ok(await ss.list_runs(request.app.state.pool, source, limit), source="synthetic")


@router.get("/api/stress/runs/{run_id}")
async def get_run(request: Request, run_id: str):
    try:
        return ok(await ss.get_run(request.app.state.pool, run_id), source="synthetic")
    except KeyError:
        raise ApiError(404, "not_found", "stress run not found")


@router.get("/api/stress/runs/{run_id}/brief")
async def run_brief(request: Request, run_id: str, format: str = Query("html", pattern="^(html|pdf)$")):
    try:
        run_ = await ss.get_run(request.app.state.pool, run_id)
    except KeyError:
        raise ApiError(404, "not_found", "stress run not found")
    html = brief.render_html(run_)
    if format == "html":
        return Response(html, media_type="text/html")
    try:
        pdf = await asyncio.to_thread(brief.render_pdf, html)
    except brief.PdfUnavailable as e:
        raise ApiError(501, "pdf_unavailable", str(e))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{run_id}.pdf"'})


@router.get("/api/stress/rules")
async def rules(request: Request):
    return ok(await ss.list_rules(request.app.state.pool))


async def _save(request, body: RuleBody, rule_id=None, upsert=False):
    lib = await request.app.state.library.get()
    try:
        return ok(await ss.save_rule(request.app.state.pool, {"eventType": body.event_type, "minImpact": body.min_impact,
                                                              "minIntegrity": body.min_integrity, "scenarioId": body.scenario_id,
                                                              "enabled": body.enabled, "cooldownMinutes": body.cooldown_minutes},
                                     lib, rule_id, upsert=upsert))
    except ss.StressError as e:
        raise ApiError(422, "invalid_rule", str(e))
    except KeyError:
        raise ApiError(404, "not_found", "rule not found")


@router.post("/api/stress/rules", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def create_rule(request: Request, body: RuleBody):
    """Upsert: with an `id` the rule is updated (or created under that id); without one a new id is assigned."""
    return await _save(request, body, body.id, upsert=True)


@router.put("/api/stress/rules/{rule_id}", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def update_rule(request: Request, rule_id: str, body: RuleBody):
    return await _save(request, body, rule_id)


@router.delete("/api/stress/rules/{rule_id}", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def delete_rule(request: Request, rule_id: str):
    try:
        await ss.delete_rule(request.app.state.pool, rule_id)
    except KeyError:
        raise ApiError(404, "not_found", "rule not found")
    return ok({"deleted": rule_id})


@router.get("/api/stress/watchlist")
async def watchlist(request: Request):
    return ok(await ss.get_watchlist(request.app.state.pool))


@router.post("/api/stress/watchlist", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def toggle_watchlist(request: Request, body: WatchToggle):
    """Add or remove one event type: {eventType, onWatchlist}. Returns the new watchlist."""
    pool = request.app.state.pool
    cur = set(await ss.get_watchlist(pool))
    (cur.add if body.on_watchlist else cur.discard)(body.event_type)
    try:
        return ok(await ss.set_watchlist(pool, sorted(cur)))
    except ss.StressError as e:
        raise ApiError(422, "invalid_watchlist", str(e))


@router.put("/api/stress/watchlist", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def set_watchlist(request: Request, body: WatchBody):
    try:
        return ok(await ss.set_watchlist(request.app.state.pool, body.event_types))
    except ss.StressError as e:
        raise ApiError(422, "invalid_watchlist", str(e))


@router.get("/api/stress/reverse")
async def reverse(request: Request):
    """Per event type: the loss on today's book if that event type's median historical market move repeated."""
    rt = await _rt(request)
    watch = set(await ss.get_watchlist(request.app.state.pool))
    rows = await asyncio.to_thread(se.reverse_stress, rt.lib, rt.ctx, watch)
    return etag_ok(request, shape.reverse_rows(rows), source="synthetic")


@router.get("/api/stress/worst-shock")
async def worst_shock(request: Request, targetLossPct: float = Query(..., gt=0, le=100)):
    """The smallest market shock (in units of each factor's own 5-day volatility) that loses `targetLossPct` percent of the book."""
    rt = await _rt(request)
    return etag_ok(request, await asyncio.to_thread(se.worst_shock, rt.ctx, targetLossPct), source="synthetic")


@router.get("/api/alerts")
async def alerts(request: Request, source: str = "live", limit: int = Query(50, ge=1, le=200)):
    source_param(source)
    return ok([shape.alert(a) for a in await ss.list_alerts(request.app.state.pool, source, limit)], source=source)
