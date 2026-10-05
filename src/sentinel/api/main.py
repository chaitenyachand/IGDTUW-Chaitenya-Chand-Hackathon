"""SENTINEL API (phase 1: health + document inspection). Envelope: {data, meta:{source, asOf}}."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .. import store
from ..config import settings


def envelope(data, source: str = "live"):
    return {"data": data, "meta": {"source": source, "asOf": datetime.now(timezone.utc).isoformat()}}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await store.create_pool(settings.database_url)
    yield
    await app.state.pool.close()


app = FastAPI(title="SENTINEL API", version="0.1.0", lifespan=lifespan)
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
    return envelope({
        "status": "ok",
        "documents": {"total": stats["total"], "lastHour": stats["last_hour"],
                      "latestPublishedAt": stats["latest"].isoformat() if stats["latest"] else None},
        "sources": [{
            "name": r["source_name"], "enabled": r["enabled"], "status": r["status"],
            "lastSuccess": r["last_success"].isoformat() if r["last_success"] else None,
            "lastError": r["last_error_msg"], "itemsLastRun": r["items_last_run"],
            "itemsTotal": r["items_total"], "errorCount": r["error_count"]} for r in sources],
    })


@app.get("/api/documents")
async def documents(limit: int = Query(50, le=200), sourceType: str | None = None):
    q = ("SELECT id, source_type, source_name, url, published_at, title, dup_of, meta FROM documents "
         "WHERE ($1::text IS NULL OR source_type = $1) ORDER BY published_at DESC LIMIT $2")
    rows = await app.state.pool.fetch(q, sourceType, limit)
    return envelope([{
        "id": r["id"], "sourceType": r["source_type"], "sourceName": r["source_name"], "url": r["url"],
        "publishedAt": r["published_at"].isoformat(), "title": r["title"], "dupOf": r["dup_of"],
    } for r in rows])
