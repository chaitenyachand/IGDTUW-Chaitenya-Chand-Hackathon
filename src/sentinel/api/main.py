"""SENTINEL API. Envelope: {data, meta:{source, asOf, nextCursor?}}. Errors: {error:{code, message}}. Keys are camelCase.
OpenAPI docs at /docs. Write endpoints need `Authorization: Bearer <API_TOKEN>` when API_TOKEN is set."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler  # noqa: F401
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import store
from ..config import settings
from ..portfolio.pricing import MarketDataMissing
from . import state
from .common import ApiError, SafeJSON, decode_cursor, encode_cursor, envelope, limiter  # noqa: F401
from .routes import audit, demo, health, index, model, portfolio, precedent, risk, signals, stress, ws

log = logging.getLogger(__name__)
SIGNAL_STREAM = "stream:signals"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await store.create_pool(settings.database_url)
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    state.attach(app, app.state.pool)
    if not settings.api_token:
        log.warning("API_TOKEN is not set: write endpoints are open (development only)")
    yield
    await app.state.redis.aclose()
    await app.state.pool.close()


app = FastAPI(title="SENTINEL API", version="0.3.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"], expose_headers=["ETag"])


def _err(status: int, code: str, message: str) -> SafeJSON:
    return SafeJSON({"error": {"code": code, "message": message}}, status_code=status)


@app.exception_handler(ApiError)
async def _api_error(request: Request, e: ApiError):
    return _err(e.status, e.code, e.message)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, e: StarletteHTTPException):
    return _err(e.status_code, "http_error", str(e.detail))


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, e: RequestValidationError):
    msg = "; ".join(f"{'.'.join(str(p) for p in x['loc'][1:])}: {x['msg']}" for x in e.errors())
    return _err(422, "validation_error", msg)


@app.exception_handler(RateLimitExceeded)
async def _rate_limited(request: Request, e: RateLimitExceeded):
    return _err(429, "rate_limited", f"rate limit exceeded: {e.detail}")


@app.exception_handler(MarketDataMissing)
async def _no_market_data(request: Request, e: MarketDataMissing):
    return _err(503, "market_data_missing", str(e))


for r in (health, signals, risk, precedent, index, portfolio, stress, model, audit, demo, ws):
    app.include_router(r.router)
