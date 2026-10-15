"""Scheduler service (design section 4): keeps the time-driven parts of the platform moving.

Every minute the Global Risk Index is recomputed and pushed; every 15 minutes Module A re-evaluates the weights because
signals decay; market data, SEC history and the models refresh daily and weekly. Every job reports into source_health.
"""
from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .. import store
from ..config import settings
from ..risk import index as risk_index
from ..stress import service as stress_service
from . import tasks

log = logging.getLogger("scheduler")


def build(sched, pool, redis):
    """Register every job on `sched` (separate from `main` so tests can inspect the schedule)."""
    def job(name, fn, trigger, **kw):
        async def run():
            await tasks.tracked(pool, name, fn())
        sched.add_job(run, trigger, id=name, max_instances=1, coalesce=True, misfire_grace_time=300, **kw)

    job("risk-index", lambda: tasks.risk_tick(pool, redis), "interval", seconds=60)
    job("risk-history", lambda: tasks.risk_hourly(pool), "cron", minute=1)
    job("index-decay", lambda: tasks.index_decay(pool, redis), "interval", minutes=15)
    job("prices", lambda: tasks.prices_daily(pool), "cron", hour=22, minute=30)
    job("fred", lambda: tasks.fred_daily(pool), "cron", hour=22, minute=45)
    job("edgar", lambda: tasks.edgar_refresh(pool), "cron", hour=23, minute=15)
    job("models", lambda: tasks.models_weekly(pool), "cron", day_of_week="sun", hour=3, minute=0)
    return sched


async def main():
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    pool = await store.create_pool(settings.database_url)
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    await stress_service.ensure_default_rules(pool)
    if not await pool.fetchval("SELECT 1 FROM risk_index_history WHERE source = 'live' LIMIT 1"):
        log.info("risk index baseline: %s", await risk_index.backfill(pool, "live"))
    sched = build(AsyncIOScheduler(timezone="UTC"), pool, redis)
    sched.start()
    log.info("scheduler started with %d jobs at %s", len(sched.get_jobs()), datetime.now(timezone.utc).isoformat())
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, stop.set)
    await stop.wait()
    sched.shutdown(wait=False)
    await redis.aclose()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
