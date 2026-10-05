"""End-to-end test of the NLP worker against real Postgres + Redis (skipped unless both URLs are set)."""
import json
import os
from datetime import datetime, timezone

import pytest
import redis.asyncio as aioredis

from sentinel import store
from sentinel.nlp import worker

DSN, RURL = os.getenv("TEST_DATABASE_URL"), os.getenv("TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not (DSN and RURL), reason="TEST_DATABASE_URL / TEST_REDIS_URL not set")

DOCS = [
    ("gdelt", "g1", "UK Targets Russian LNG Tankers and Bunkering Ships in New Sanctions", "https://shipandbunker.com/a", "news", {}),
    ("gdelt", "g2", "Rihanna claps back at EJ Johnson over Fashion Week claims", "https://geelongadvertiser.com.au/a", "news", {}),
    ("sec_edgar", "a1", "Boeing Co. (BA) files Form 8-K: Item 1.05: Material Cybersecurity Incidents", "https://sec.gov/a", "news",
     {"ticker": "BA", "items": ["1.05"]}),
]


async def test_backfill_and_publish():
    pool = await store.create_pool(DSN)
    redis = aioredis.from_url(RURL, decode_responses=True)
    await pool.execute("TRUNCATE documents CASCADE")
    await redis.delete(worker.OUT_STREAM)
    for src, key, title, url, stype, meta in DOCS:
        await pool.execute(
            "INSERT INTO documents (id, source_type, source_name, url, published_at, title, text, raw_hash, meta) "
            "VALUES ($1,$2,$3,$4,$5,$6,$6,'h',$7::jsonb)", key, stype, src, url, datetime.now(timezone.utc), title, json.dumps(meta))

    assert await worker.process_pending(pool, redis) == 3
    assert await worker.process_pending(pool, redis) == 0          # idempotent: nothing left to do

    rows = {r["document_id"]: r for r in await pool.fetch("SELECT * FROM doc_features")}
    assert rows["g1"]["relevant"] and rows["g1"]["weak_event"] == "Geopolitical"
    assert not rows["g2"]["relevant"]
    assert rows["a1"]["relevant"] and rows["a1"]["weak_event"] == "Cyber"
    assert json.loads(rows["a1"]["entities"])[0]["ticker"] == "BA"

    published = {m[1]["id"] for m in await redis.xrange(worker.OUT_STREAM)}
    assert published == {"g1", "a1"}                                # only relevant documents go downstream
    await redis.aclose(); await pool.close()