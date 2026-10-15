from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ...demo import episodes, replay
from .. import shape
from ..common import ApiError, limiter, ok, require_token, write_limit

router = APIRouter()


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class InjectBody(Camel):
    episode_id: str | None = Field(None, alias="episodeId")
    scenario_id: str | None = Field(None, alias="scenarioId")        # the terminal's name for an episode id
    pace_seconds: float | None = Field(None, ge=0, le=60)
    limit: int | None = Field(None, ge=1, le=5000)


@router.get("/api/demo/episodes")
async def list_episodes():
    return ok(episodes.list_episodes(), source="replay")


@router.get("/api/demo/scenarios")
async def list_scenarios():
    """Archived episodes the terminal can replay (only those whose archive has been downloaded are `available`)."""
    return ok([shape.demo_scenario(e) for e in episodes.list_episodes()], source="replay")


@router.get("/api/demo/status")
async def status(request: Request):
    return ok(await replay.status(request.app.state.pool), source="replay")


@router.post("/api/demo/inject", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def inject(request: Request, body: InjectBody):
    eid = body.episode_id or body.scenario_id
    if not eid:
        raise ApiError(422, "missing_episode", "episodeId (or scenarioId) is required")
    try:
        res = await replay.inject(request.app.state.pool, request.app.state.redis, eid, body.pace_seconds, body.limit)
    except episodes.EpisodeNotFound:
        raise ApiError(404, "unknown_episode", f"unknown episode '{eid}'")
    except episodes.ReplayDataMissing as e:
        raise ApiError(409, "replay_data_missing", str(e))
    return ok(res, source="replay")


@router.post("/api/demo/reset", dependencies=[Depends(require_token)])
@limiter.limit(write_limit)
async def reset(request: Request):
    return ok(await replay.reset(request.app.state.pool), source="replay")
