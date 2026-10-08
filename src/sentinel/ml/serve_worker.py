"""Serving worker: scores every new document with the frozen models and writes signals.

Loop: pick unscored (or stale-version) documents, newest first -> hybrid relevance + event -> FinBERT sentiment and
explanations for the relevant ones -> integrity from corroboration -> signals table + Redis stream for the WebSocket.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timedelta, timezone

import numpy as np
import redis.asyncio as aioredis

from .. import store
from ..config import settings
from ..signals_io import INSERT_SIGNAL, api_to_params
from .serving import Scorer, build_signal, find_corroboration, source_label

log = logging.getLogger("serve")
SIGNAL_STREAM = "stream:signals"
MODEL_PATH = os.environ.get("MODEL_PATH", "models/hybrid_v1.joblib")
BACKLOG_HOURS = int(os.environ.get("SERVE_BACKLOG_HOURS", "48"))
EXPLAIN_MAX_AGE_HOURS = float(os.environ.get("EXPLAIN_MAX_AGE_HOURS", "6"))
BATCH = int(os.environ.get("SERVE_BATCH", "64"))

PENDING_SQL = """
SELECT d.id, d.source_type, d.source_name, d.url, d.published_at, d.mode, d.text, d.meta,
       f.clean_title AS title, f.entities, f.features, f.weak_event AS rule_event
FROM documents d
JOIN doc_features f ON f.document_id = d.id
LEFT JOIN doc_scores s ON s.document_id = d.id
WHERE d.dup_of IS NULL AND (s.document_id IS NULL OR s.model_version <> $1)
  AND d.published_at > now() - make_interval(hours => $3)
ORDER BY d.published_at DESC LIMIT $2
"""
UPSERT_SCORE = """
INSERT INTO doc_scores (document_id, relevance_p, relevant, event_pred, event_proba, model_version)
VALUES ($1,$2,$3,$4,$5::jsonb,$6)
ON CONFLICT (document_id) DO UPDATE SET relevance_p=EXCLUDED.relevance_p, relevant=EXCLUDED.relevant,
  event_pred=EXCLUDED.event_pred, event_proba=EXCLUDED.event_proba, model_version=EXCLUDED.model_version, scored_at=now()
"""
API_FIELDS_DROP = ("entities", "sentimentProbs", "modelVersion")


def _loads(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


def normalize(r) -> dict:
    d = dict(r)
    d["meta"], d["features"] = _loads(d["meta"]), _loads(d["features"])
    d["entities"] = json.loads(d["entities"]) if isinstance(d["entities"], str) else (d["entities"] or [])
    return d


async def load_recent(pool) -> list:
    rows = await pool.fetch("SELECT source_name, embedding FROM signals WHERE ts > now() - interval '24 hours' "
                            "AND embedding IS NOT NULL ORDER BY ts DESC LIMIT 5000")
    return [(r["source_name"], np.asarray(r["embedding"], dtype=float)) for r in rows]


async def duplicate_sources(pool, ids: list) -> dict:
    """Outlets that republished the same text (near-duplicates) also corroborate a signal."""
    if not ids:
        return {}
    rows = await pool.fetch("SELECT dup_of, source_name, meta FROM documents WHERE dup_of = ANY($1)", ids)
    out: dict = {}
    for r in rows:
        out.setdefault(r["dup_of"], set()).add(source_label(r["source_name"], _loads(r["meta"])))
    return out


async def score_batch(pool, redis, scorer: Scorer, raw_rows: list):
    rows = [normalize(r) for r in raw_rows]
    if not rows:
        return 0, 0
    emb, rel_p, ev_proba = scorer.score_relevance_event(rows)
    keep = [i for i, p in enumerate(rel_p) if p >= scorer.threshold]
    sent = scorer.sentiment([rows[i]["title"] for i in keep])
    recent = await load_recent(pool)
    dups = await duplicate_sources(pool, [rows[i]["id"] for i in keep])
    now = datetime.now(timezone.utc)
    made = []
    for k, i in enumerate(keep):
        row = rows[i]
        label = source_label(row["source_name"], row["meta"])
        corr = sorted(set(find_corroboration(emb[i], label, recent)) | (dups.get(row["id"], set()) - {label}))[:5]
        fresh = (now - row["published_at"]) < timedelta(hours=EXPLAIN_MAX_AGE_HOURS)
        explanation = scorer.explain(row["title"]) if fresh else []
        sig = build_signal(row, row["meta"], row["entities"], rel_p[i], ev_proba[i], sent[k], explanation, corr,
                           scorer.version)
        made.append((sig, emb[i]))
        recent.append((label, emb[i]))
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(UPSERT_SCORE, [
                (r["id"], rel_p[i], rel_p[i] >= scorer.threshold, max(ev_proba[i], key=ev_proba[i].get),
                 json.dumps(ev_proba[i]), scorer.version) for i, r in enumerate(rows)])
            for sig, e in made:
                await con.execute(INSERT_SIGNAL, *api_to_params(sig, e))
    if redis is not None and made:
        pipe = redis.pipeline()
        for sig, _ in made:
            payload = {k: v for k, v in sig.items() if k not in API_FIELDS_DROP}
            pipe.xadd(SIGNAL_STREAM, {"payload": json.dumps(payload)}, maxlen=20000, approximate=True)
        await pipe.execute()
    return len(rows), len(made)


async def main():
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not os.path.exists(MODEL_PATH):
        raise SystemExit(f"{MODEL_PATH} not found: run `make train-final` first")
    scorer = Scorer.from_disk(MODEL_PATH)
    log.info("loaded models: %s", scorer.version)
    pool = await store.create_pool(settings.database_url)
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    while not stop.is_set():
        rows = await pool.fetch(PENDING_SQL, scorer.version, BATCH, BACKLOG_HOURS)
        if not rows:
            try:
                await asyncio.wait_for(stop.wait(), timeout=3)
            except asyncio.TimeoutError:
                pass
            continue
        t0 = loop.time()
        n, m = await score_batch(pool, redis, scorer, rows)
        log.info("scored %d documents -> %d signals in %.1fs", n, m, loop.time() - t0)
    await redis.aclose()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
