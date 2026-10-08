"""SENTINEL API. Envelope: {data, meta:{source, asOf, nextCursor?}}. Keys are camelCase."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .. import store
from ..config import settings
from ..signals_io import row_to_api

SIGNAL_STREAM = "stream:signals"
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def encode_cursor(ts: datetime, sid: str) -> str:
    """Opaque, URL-safe cursor: microseconds since epoch (exact integer arithmetic) + id."""
    return f"{(ts - _EPOCH) // timedelta(microseconds=1)}.{sid}"


def decode_cursor(cursor: str):
    us, sid = cursor.split(".", 1)
    return _EPOCH + timedelta(microseconds=int(us)), sid


def envelope(data, source: str = "live", **meta):
    return {"data": data, "meta": {"source": source, "asOf": datetime.now(timezone.utc).isoformat(), **meta}}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await store.create_pool(settings.database_url)
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    yield
    await app.state.redis.aclose()
    await app.state.pool.close()


app = FastAPI(title="SENTINEL API", version="0.2.0", lifespan=lifespan)
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
async def health():
    pool = app.state.pool
    sources = await pool.fetch(
        "SELECT source_name, enabled, status, last_success, last_error_msg, items_last_run, items_total, error_count "
        "FROM source_health ORDER BY source_name")
    stats = await pool.fetchrow(
        "SELECT count(*) AS total, count(*) FILTER (WHERE ingested_at > now() - interval '1 hour') AS last_hour, "
        "max(published_at) AS latest FROM documents")
    sig = await pool.fetchrow("SELECT count(*) AS n, max(ts) AS latest, max(model_version) AS version FROM signals")
    return envelope({
        "status": "ok",
        "documents": {"total": stats["total"], "lastHour": stats["last_hour"],
                      "latestPublishedAt": stats["latest"].isoformat() if stats["latest"] else None},
        "signals": {"total": sig["n"], "latestTs": sig["latest"].isoformat() if sig["latest"] else None},
        "modelVersion": sig["version"],
        "sources": [{
            "name": r["source_name"], "enabled": r["enabled"], "status": r["status"],
            "lastSuccess": r["last_success"].isoformat() if r["last_success"] else None,
            "lastError": r["last_error_msg"], "itemsLastRun": r["items_last_run"],
            "itemsTotal": r["items_total"], "errorCount": r["error_count"]} for r in sources],
    })


@app.get("/api/documents")
async def documents(limit: int = Query(50, le=200), sourceType: str | None = None):
    q = ("SELECT id, source_type, source_name, url, published_at, title, dup_of FROM documents "
         "WHERE ($1::text IS NULL OR source_type = $1) ORDER BY published_at DESC LIMIT $2")
    rows = await app.state.pool.fetch(q, sourceType, limit)
    return envelope([{
        "id": r["id"], "sourceType": r["source_type"], "sourceName": r["source_name"], "url": r["url"],
        "publishedAt": r["published_at"].isoformat(), "title": r["title"], "dupOf": r["dup_of"],
    } for r in rows])


@app.get("/api/signals")
async def signals(limit: int = Query(50, ge=1, le=200), cursor: str | None = None, entity: str | None = None,
                  eventType: str | None = None, minImpact: float | None = None, sourceType: str | None = None,
                  mode: str | None = None):
    where, args = [], []

    def add(cond: str, value):
        args.append(value)
        where.append(cond.replace("?", f"${len(args)}"))

    if entity:
        add("(lower(entity) = lower(?) OR upper(ticker) = upper(?))", entity)
    if eventType:
        add("event_type = ?", eventType)
    if minImpact is not None:
        add("impact >= ?", minImpact)
    if sourceType:
        add("source_type = ?", sourceType)
    if mode:
        add("mode = ?", mode)
    if cursor:
        try:
            ts, sid = decode_cursor(cursor)
            args.extend([ts, sid])
            where.append(f"(ts, id) < (${len(args) - 1}, ${len(args)})")
        except ValueError:
            raise HTTPException(400, "invalid cursor")
    args.append(limit + 1)
    sql = ("SELECT * FROM signals" + (" WHERE " + " AND ".join(where) if where else "") +
           f" ORDER BY ts DESC, id DESC LIMIT ${len(args)}")
    rows = await app.state.pool.fetch(sql, *args)
    page = rows[:limit]
    nxt = encode_cursor(page[-1]["ts"], page[-1]["id"]) if len(rows) > limit else None
    modes = {r["mode"] for r in page}
    return envelope([row_to_api(r) for r in page], source=modes.pop() if len(modes) == 1 else "live", nextCursor=nxt)


@app.get("/api/signals/{signal_id}")
async def signal_detail(signal_id: str):
    r = await app.state.pool.fetchrow("SELECT * FROM signals WHERE id = $1", signal_id)
    if not r:
        raise HTTPException(404, "signal not found")
    return envelope(row_to_api(r), source=r["mode"])


@app.websocket("/ws/signals")
async def ws_signals(ws: WebSocket, since: str | None = None, minImpact: float | None = None):
    """Server messages: {type, id, data}. `since` is the last Redis stream id the client saw (missed events are replayed)."""
    await ws.accept()
    redis = app.state.redis
    last = since or "$"
    try:
        await ws.send_json({"type": "hello", "id": last, "data": {"stream": SIGNAL_STREAM}})
        while True:
            resp = await redis.xread({SIGNAL_STREAM: last}, count=50, block=15000)
            if not resp:
                await ws.send_json({"type": "ping", "id": last, "data": {}})
                continue
            for _, entries in resp:
                for entry_id, fields in entries:
                    last = entry_id
                    await ws.send_json({"type": "signal", "id": entry_id, "data": json.loads(fields["payload"])})
    except WebSocketDisconnect:
        return
