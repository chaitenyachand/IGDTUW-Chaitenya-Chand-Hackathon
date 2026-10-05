"""NLP worker: consumes new documents from Redis Streams, computes features, publishes relevant ones.

The database is the source of truth: a periodic sweep processes any document without features
(initial backfill, or anything missed while the worker was down), so nothing is ever lost.
"""
from __future__ import annotations

import asyncio
import json
import logging
import signal

import redis.asyncio as aioredis

from .. import store
from ..config import settings
from .features import compute_features

log = logging.getLogger("nlp")
IN_STREAM, OUT_STREAM, GROUP = "stream:documents", "stream:relevant", "nlp"

UPSERT = """
INSERT INTO doc_features (document_id, clean_title, entities, relevance, relevant, weak_event,
                          weak_event_scores, features, pipeline_version)
VALUES ($1,$2,$3::jsonb,$4,$5,$6,$7::jsonb,$8::jsonb,$9)
ON CONFLICT (document_id) DO UPDATE SET clean_title=EXCLUDED.clean_title, entities=EXCLUDED.entities,
  relevance=EXCLUDED.relevance, relevant=EXCLUDED.relevant, weak_event=EXCLUDED.weak_event,
  weak_event_scores=EXCLUDED.weak_event_scores, features=EXCLUDED.features,
  pipeline_version=EXCLUDED.pipeline_version, processed_at=now()
"""
COLS = "id, source_type, source_name, url, title, text, meta"


async def process_rows(pool, redis, rows) -> int:
    feats = [compute_features(r) for r in rows]
    if not feats:
        return 0
    async with pool.acquire() as con:
        await con.executemany(UPSERT, [
            (f.document_id, f.clean_title, json.dumps(f.entities), f.relevance, f.relevant, f.weak_event,
             json.dumps(f.weak_event_scores), json.dumps(f.features), f.pipeline_version) for f in feats])
    if redis is not None:
        pipe = redis.pipeline()
        for f in feats:
            if f.relevant:
                pipe.xadd(OUT_STREAM, {"id": f.document_id, "relevance": f.relevance,
                                       "weak_event": f.weak_event or ""}, maxlen=100_000, approximate=True)
        await pipe.execute()
    return len(feats)


async def process_pending(pool, redis, batch: int = 500) -> int:
    total = 0
    while True:
        rows = await pool.fetch(
            f"SELECT {', '.join('d.' + c.strip() for c in COLS.split(','))} FROM documents d "
            "LEFT JOIN doc_features f ON f.document_id = d.id WHERE f.document_id IS NULL "
            "ORDER BY d.published_at DESC LIMIT $1", batch)
        if not rows:
            return total
        total += await process_rows(pool, redis, rows)


async def main():
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    pool = await store.create_pool(settings.database_url)
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.xgroup_create(IN_STREAM, GROUP, id="0", mkstream=True)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    log.info("backfilled %d documents", await process_pending(pool, redis))
    last_sweep = loop.time()
    while not stop.is_set():
        resp = await redis.xreadgroup(GROUP, "worker-1", {IN_STREAM: ">"}, count=100, block=3000)
        msg_ids, doc_ids = [], []
        for _, msgs in resp or []:
            for mid, fields in msgs:
                msg_ids.append(mid)
                doc_ids.append(fields["id"])
        if doc_ids:
            rows = await pool.fetch(f"SELECT {COLS} FROM documents WHERE id = ANY($1)", doc_ids)
            n = await process_rows(pool, redis, rows)
            await redis.xack(IN_STREAM, GROUP, *msg_ids)
            log.info("processed %d documents", n)
        if loop.time() - last_sweep > 30:
            n = await process_pending(pool, redis)
            if n:
                log.info("sweep processed %d missed documents", n)
            last_sweep = loop.time()
    await redis.aclose()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())