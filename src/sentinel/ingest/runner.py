"""Ingestion service: runs every connector, de-duplicates, stores, publishes to Redis Streams,
and keeps source_health current."""
from __future__ import annotations

import asyncio
import logging
import signal

import httpx
import redis.asyncio as aioredis

from .. import store
from ..config import settings
from .bluesky import BlueskyJetstream
from .dedupe import NearDuplicateIndex
from .edgar import EdgarFilings
from .gdelt import GdeltGKG
from .reddit import RedditPosts
from .rss import RssFeeds

log = logging.getLogger("ingest")
STREAM = "stream:documents"


async def publish(redis, inserted: list):
    if not inserted:
        return
    pipe = redis.pipeline()
    for d, dup in inserted:
        pipe.xadd(STREAM, {"id": d.id, "type": d.source_type, "source": d.source_name, "dup_of": dup or ""},
                  maxlen=100_000, approximate=True)
    await pipe.execute()


async def _sleep(stop: asyncio.Event, seconds: float):
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


async def run_polling(conn, pool, redis, index, stop: asyncio.Event):
    fails = 0
    while not stop.is_set():
        try:
            docs = await conn.fetch()
            inserted = await store.insert_documents(pool, docs, index)
            await publish(redis, inserted)
            await store.record_success(pool, conn.name, len(inserted))
            log.info("%s: fetched=%d new=%d", conn.name, len(docs), len(inserted))
            fails = 0
        except Exception as e:
            fails += 1
            log.exception("%s failed", conn.name)
            await store.record_error(pool, conn.name, repr(e))
        delay = min(conn.poll_seconds * (2 ** min(fails, 3)), 3600) if fails else conn.poll_seconds
        await _sleep(stop, delay)


async def run_streaming(conn, pool, redis, index, stop: asyncio.Event, flush_every: float = 2.0, max_batch: int = 200):
    buf, last = [], asyncio.get_event_loop().time()
    gen = conn.stream()
    try:
        async for doc in gen:
            buf.append(doc)
            now = asyncio.get_event_loop().time()
            if len(buf) >= max_batch or now - last >= flush_every:
                try:
                    inserted = await store.insert_documents(pool, buf, index)
                    await publish(redis, inserted)
                    await store.record_success(pool, conn.name, len(inserted))
                except Exception as e:
                    log.exception("%s flush failed", conn.name)
                    await store.record_error(pool, conn.name, repr(e))
                buf, last = [], now
            if stop.is_set():
                break
    finally:
        await gen.aclose()


async def main():
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    pool = await store.create_pool(settings.database_url)
    redis = aioredis.from_url(settings.redis_url)
    index = NearDuplicateIndex(max_distance=3)
    log.info("loaded %d recent documents into dedupe index", await store.load_recent_into_index(pool, index))

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    web = httpx.AsyncClient(timeout=30, headers={"User-Agent": settings.reddit_user_agent})
    sec = httpx.AsyncClient(timeout=30, headers={"User-Agent": settings.sec_user_agent})

    pollers = [
        GdeltGKG(pool, web, settings.gdelt_poll_seconds),
        RssFeeds(web, settings.rss_poll_seconds),
        EdgarFilings(sec, settings.edgar_poll_seconds),
    ]
    if settings.reddit_client_id and settings.reddit_client_secret:
        pollers.append(RedditPosts(web, settings.reddit_client_id, settings.reddit_client_secret,
                                   settings.reddit_user_agent, settings.reddit_poll_seconds))
    else:
        await store.set_disabled(pool, "reddit", "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set")

    tasks = [asyncio.create_task(run_polling(c, pool, redis, index, stop)) for c in pollers]
    tasks.append(asyncio.create_task(
        run_streaming(BlueskyJetstream(settings.bluesky_jetstream_url), pool, redis, index, stop)))

    await stop.wait()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await web.aclose(); await sec.aclose(); await redis.aclose(); await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
