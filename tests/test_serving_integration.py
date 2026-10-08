"""End to end: documents -> nlp features -> model scoring -> signals table -> Redis stream -> REST and WebSocket.
Needs Postgres (migrations through 005) and Redis; skipped unless TEST_DATABASE_URL and TEST_REDIS_URL are set."""
import json
import os
from datetime import datetime, timezone

import pytest
import redis.asyncio as aioredis
from fastapi.testclient import TestClient

from sentinel import store
from sentinel.config import settings
from sentinel.ml import serve_worker
from sentinel.ml.serving import Scorer
from sentinel.ml.train_final import train_artifacts
from sentinel.nlp import worker
from tests.test_serving import fake_embed, fake_finbert, gold_rows

DSN, RURL = os.getenv("TEST_DATABASE_URL"), os.getenv("TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not (DSN and RURL), reason="TEST_DATABASE_URL / TEST_REDIS_URL not set")


async def test_scoring_to_api(monkeypatch):
    pool = await store.create_pool(DSN)
    redis = aioredis.from_url(RURL, decode_responses=True)
    await pool.execute("TRUNCATE documents CASCADE")
    await redis.delete(serve_worker.SIGNAL_STREAM)
    now = datetime.now(timezone.utc)
    docs = [("d1", "gdelt", "sanctions hit oil exports as markets rally", "https://reuters.com/a", {"domain": "reuters.com"}),
            ("d2", "rss:cnbc_finance", "sanctions hit oil exports as markets rally today", "https://cnbc.com/b", {}),
            ("d3", "gdelt", "local football festival results flat", "https://x.com/c", {"domain": "x.com"}),
            ("d4", "bluesky", "central bank raises interest rates stocks slump", "https://bsky.app/d", {"match": {"reason": "macro"}})]
    for did, src, title, url, meta in docs:
        await pool.execute("INSERT INTO documents (id,source_type,source_name,url,published_at,title,text,raw_hash,meta) "
                           "VALUES ($1,'news',$2,$3,$4,$5,$5,'h',$6::jsonb)", did, src, url, now, title, json.dumps(meta))
    await worker.process_pending(pool, None)

    gold = gold_rows()
    art = train_artifacts(gold, fake_embed([r["title"] for r in gold]))
    scorer = Scorer(art, fake_embed, fake_finbert)
    rows = await pool.fetch(serve_worker.PENDING_SQL, scorer.version, 50, 48)
    n, m = await serve_worker.score_batch(pool, redis, scorer, rows)
    assert n == 4 and m >= 2
    assert await pool.fetchval("SELECT count(*) FROM doc_scores") == 4
    assert await pool.fetchval("SELECT count(*) FROM signals") == m
    assert await redis.xlen(serve_worker.SIGNAL_STREAM) == m
    assert len(await pool.fetch(serve_worker.PENDING_SQL, scorer.version, 50, 48)) == 0     # nothing left to score

    # the near-identical second headline corroborates the first one
    corr = [json.loads(r["integrity"])["corroboratedBy"] for r in await pool.fetch("SELECT integrity FROM signals WHERE id IN ('d1','d2')")]
    assert any(corr), corr                       # whichever was scored second sees the first as corroboration

    monkeypatch.setattr(settings, "database_url", DSN)
    monkeypatch.setattr(settings, "redis_url", RURL)
    from sentinel.api.main import app
    with TestClient(app) as c:
        r = c.get("/api/signals?limit=2").json()
        assert len(r["data"]) == 2 and r["meta"]["nextCursor"] and r["meta"]["source"] == "live"
        page2 = c.get(f"/api/signals?limit=50&cursor={r['meta']['nextCursor']}").json()
        assert {s["id"] for s in r["data"]}.isdisjoint({s["id"] for s in page2["data"]})
        one = c.get(f"/api/signals/{r['data'][0]['id']}").json()["data"]
        assert one == r["data"][0] and set(one) >= {"id", "ts", "entity", "sentiment", "eventType", "integrity", "explanation"}
        assert c.get("/api/signals?cursor=garbage").status_code == 400
        assert c.get("/api/signals/nope").status_code == 404
        assert c.get("/api/signals?eventType=NoSuchType").json()["data"] == []
        assert c.get("/api/health").json()["data"]["signals"]["total"] == m
        with c.websocket_connect("/ws/signals?since=0") as ws:
            assert ws.receive_json()["type"] == "hello"
            msg = ws.receive_json()
            assert msg["type"] == "signal" and msg["data"]["id"] in {"d1", "d2", "d4"}
    await redis.aclose()
    await pool.close()
