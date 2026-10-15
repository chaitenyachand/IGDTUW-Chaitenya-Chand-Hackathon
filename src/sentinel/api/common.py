"""Shared API plumbing: envelope, errors, bearer auth, ETag caching, JSON sanitising, small TTL cache."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import time
from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from ..config import settings

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def encode_cursor(ts: datetime, sid: str) -> str:
    """Opaque, URL-safe cursor: microseconds since epoch (exact integer arithmetic) + id."""
    return f"{(ts - _EPOCH) // timedelta(microseconds=1)}.{sid}"


def decode_cursor(cursor: str):
    us, sid = cursor.split(".", 1)
    return _EPOCH + timedelta(microseconds=int(us)), sid


def clean(o):
    """NaN / inf are not valid JSON: they become null (a missing number is never shown as 0)."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):      # numpy scalar
        try:
            return clean(o.item())
        except Exception:
            pass
    return o


def _default(o):
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


class SafeJSON(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(clean(content), default=_default, allow_nan=False, separators=(",", ":")).encode()


def envelope(data, source: str = "live", **meta) -> dict:
    return {"data": data, "meta": {"source": source, "asOf": datetime.now(timezone.utc).isoformat(), **meta}}


def ok(data, source: str = "live", **meta) -> SafeJSON:
    return SafeJSON(envelope(data, source, **meta))


def etag_ok(request: Request, data, source: str = "live", **meta) -> Response:
    """Envelope with an ETag over `data` only (asOf changes every call); 304 when the client already has it."""
    body = json.dumps(clean(data), default=_default, sort_keys=True, allow_nan=False, separators=(",", ":"))
    tag = '"' + hashlib.sha1(body.encode()).hexdigest()[:20] + '"'
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers={"ETag": tag})
    r = ok(data, source, **meta)
    r.headers["ETag"] = tag
    return r


def require_token(request: Request):
    tok = settings.api_token
    if not tok:
        return
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or not hmac.compare_digest(h[7:], tok):
        raise ApiError(401, "unauthorized", "a valid bearer token is required for this endpoint")


def source_param(v: str) -> str:
    if v not in ("live", "replay"):
        raise ApiError(422, "bad_source", "source must be 'live' or 'replay'")
    return v


class TTL:
    """Tiny per-process cache so many clients polling one heavy endpoint cost one computation."""

    def __init__(self):
        self._d: dict = {}

    async def get(self, key, seconds: float, fn):
        hit = self._d.get(key)
        if hit and time.time() - hit[0] < seconds:
            return hit[1]
        val = await fn()
        self._d[key] = (time.time(), val)
        return val

    def clear(self):
        self._d.clear()


ttl = TTL()


from slowapi import Limiter  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402

limiter = Limiter(key_func=get_remote_address, default_limits=[lambda: f"{settings.rate_limit_per_minute}/minute"])


def write_limit():
    return f"{settings.write_rate_limit_per_minute}/minute"
