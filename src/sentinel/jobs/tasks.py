"""Scheduled and on-demand jobs. Plain async functions (no scheduler imports) so the CLI and the tests call them directly."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from .. import store
from ..config import settings
from ..index import service as index_service
from ..risk import index as risk_index
from ..universe import FRED_SERIES, all_price_symbols

log = logging.getLogger(__name__)


async def tracked(pool, name: str, coro):
    """Run a job coroutine and record success or failure in source_health (visible in /api/health)."""
    try:
        out = await coro
        n = out if isinstance(out, int) else (len(out) if hasattr(out, "__len__") else 1)
        await store.record_success(pool, f"job:{name}", n)
        return out
    except Exception as e:
        log.exception("job %s failed", name)
        await store.record_error(pool, f"job:{name}", repr(e))
        return None


async def risk_tick(pool, redis) -> dict:
    """Recompute the current Global Risk Index and push it to WebSocket clients (the index decays with time even
    when no new signal arrives)."""
    return await risk_index.update_and_publish(pool, redis, "live")


async def risk_hourly(pool) -> int:
    """Store the last few hourly index values (idempotent)."""
    now = datetime.now(timezone.utc)
    return await risk_index.record_hours(pool, "live", risk_index.floor_hour(now) - timedelta(hours=3), now)


async def index_decay(pool, redis):
    """Signals decay with time, so the target weights drift even without news: recompute and rebalance if needed."""
    return await index_service.recompute(pool, redis, source="live", actor="scheduler")


async def prices_daily(pool) -> dict:
    from ..market.prices import sync_prices
    return await sync_prices(pool, all_price_symbols())


async def fred_daily(pool) -> dict:
    from ..market.fred import sync_fred
    if not settings.fred_api_key:
        raise RuntimeError("FRED_API_KEY is not set")
    return await sync_fred(pool, settings.fred_api_key, FRED_SERIES)


async def edgar_refresh(pool) -> dict:
    """New 8-K filings since the last run, then real abnormal-return labels for everything not yet labelled."""
    from ..impact.edgar_backfill import backfill_edgar, label_events
    filings = await backfill_edgar(pool, settings.sec_user_agent)
    labels = await label_events(pool)
    return {"filings": filings, **labels}


async def models_weekly(pool) -> dict:
    """Retrain the company-event impact model, re-run the PRECEDENT point-in-time validation and the signal backtest."""
    from ..impact.jobs import train_impact
    from ..model.backtest import signal_backtest
    out = {}
    try:
        out["impact"] = {k: v for k, v in (await train_impact(pool)).items() if k in ("n_events", "spearman", "mae", "mae_baseline")}
    except RuntimeError as e:
        out["impact"] = {"skipped": str(e)}
    out["precedent"] = await validate_precedent(pool)
    out["signalBacktest"] = {k: v for k, v in (await signal_backtest(pool)).items() if k in ("status", "n")}
    return out


async def validate_precedent(pool) -> dict:
    """Leave-one-out, point-in-time validation of PRECEDENT's calibrated shocks; stored for Model Lab."""
    from ..precedent.engine import Library, validate_leave_one_out
    lib = await Library.load(pool)
    res = validate_leave_one_out(lib)
    res["libraryEvents"] = len(lib)
    await pool.execute("INSERT INTO model_runs (kind, metrics) VALUES ('precedent_validation', $1::jsonb)", json.dumps(res))
    return res
