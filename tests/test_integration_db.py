"""Integration tests against a real Postgres. Skipped automatically when TEST_DATABASE_URL is not set."""
import os
from datetime import datetime, timezone

import pytest

from sentinel import store
from sentinel.ingest.base import Document
from sentinel.ingest.dedupe import NearDuplicateIndex

DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")


def doc(src, key, title, url=None, ts=None, stype="news"):
    return Document(stype, src, key, url, ts or datetime.now(timezone.utc), title, title)


async def test_insert_dedupe_and_health():
    pool = await store.create_pool(DSN)
    await pool.execute("TRUNCATE documents, source_health, app_config CASCADE")
    idx = NearDuplicateIndex()

    a = doc("rss:a", "1", "Oil prices surge after OPEC announces surprise production cut", "https://a.com/x?utm_source=q")
    b = doc("rss:b", "2", "Oil prices surge after OPEC announces surprise production cut", "https://b.com/y")  # syndicated copy
    c = doc("rss:c", "3", "Apple unveils new iPhone with improved camera and longer battery life", "https://c.com/z")
    same_url = doc("rss:d", "4", "Different words entirely about central bank policy decisions", "https://www.a.com/x/")

    ins = await store.insert_documents(pool, [a, b, c, same_url], idx)
    ids = {d.key: dup for d, dup in ins}
    assert set(ids) == {"1", "2", "3"}              # same canonical URL as 'a' is skipped
    assert ids["1"] is None and ids["2"] == a.id and ids["3"] is None   # b is a near-duplicate of a, kept as corroboration

    again = await store.insert_documents(pool, [a], NearDuplicateIndex())   # idempotent re-insert
    assert again == []

    fresh = NearDuplicateIndex()
    assert await store.load_recent_into_index(pool, fresh) == 3             # index rebuilds from the DB after a restart

    await store.record_success(pool, "rss", 3)
    await store.record_success(pool, "rss", 2)
    await store.record_error(pool, "gdelt", "boom")
    await store.set_disabled(pool, "reddit", "no creds")
    rows = {r["source_name"]: r for r in await pool.fetch("SELECT * FROM source_health")}
    assert rows["rss"]["items_total"] == 5 and rows["rss"]["status"] == "ok"
    assert rows["gdelt"]["status"] == "error" and rows["reddit"]["enabled"] is False

    await store.set_config(pool, "k", {"v": 1})
    assert await store.get_config(pool, "k") == {"v": 1}
    assert await store.get_config(pool, "missing") is None
    await pool.close()
