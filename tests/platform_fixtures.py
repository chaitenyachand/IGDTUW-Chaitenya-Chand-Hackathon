"""Shared setup for the platform integration tests: a seeded TEST database (synthetic market world, library, book, filings)."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone

import numpy as np

from sentinel import store
from sentinel.signals_io import INSERT_SIGNAL, api_to_params
from tests.test_serving import fake_embed

DSN = os.getenv("TEST_DATABASE_URL")
RURL = os.getenv("TEST_REDIS_URL")
ART_DIR = tempfile.mkdtemp(prefix="sentinel-test-art-")
IMPACT_PATH = os.path.join(ART_DIR, "impact.joblib")
_seeded = False


def mk_sig(sid, ts, entity="Apple", ticker="AAPL", event="Credit Event", sentiment=-0.6, impact=9.0, mode="live",
           integrity=0.9, headline=None, source="Reuters"):
    headline = headline or f"{entity} faces {event.lower()} as markets slump"
    return {"id": sid, "ts": ts.isoformat(), "mode": mode, "entity": entity, "ticker": ticker, "entities": [], "headline": headline,
            "text": headline, "sourceType": "news", "sourceName": source, "url": f"https://x.test/{sid}", "sentiment": sentiment,
            "sentimentProbs": {}, "eventType": event, "secondaryEventType": None, "impact": impact, "bookImpact": None,
            "confidence": 0.9, "halfLifeDays": None, "integrity": {"score": integrity, "corroboratedBy": [], "flags": []},
            "explanation": [], "affectedHoldings": [], "modelVersion": "test", "impactBasis": "test"}


async def put_signal(pool, sig):
    """Insert a document + signal the way the worker does (embedding from the same fake embedder the library used)."""
    ts = datetime.fromisoformat(sig["ts"])
    await pool.execute("INSERT INTO documents (id,source_type,source_name,mode,url,published_at,title,text,raw_hash) "
                       "VALUES ($1,'news',$2,$3,$4,$5,$6,$6,'h') ON CONFLICT DO NOTHING", sig["id"], "gdelt", sig["mode"], sig["url"], ts, sig["headline"])
    await pool.execute(INSERT_SIGNAL, *api_to_params(sig, fake_embed([sig["headline"]])[0]))


async def _seed():
    from sentinel.impact.edgar_backfill import label_events
    from sentinel.impact.event_study import parse_filings
    from sentinel.impact.jobs import train_impact
    from sentinel.portfolio.store import build_portfolio
    from sentinel.precedent.library import build_library
    from sentinel.stress.service import ensure_default_rules
    from sentinel.universe import UNIVERSE
    from tests.dbutil import apply_migrations
    from tests.filing_fixtures import submissions_block
    from tests.market_fixtures import seed_market
    pool = await store.create_pool(DSN)
    await apply_migrations(pool)
    await pool.execute("TRUNCATE documents, corporate_events, event_library, portfolio_holdings, stress_rules, stress_runs, "
                       "stress_watchlist, alerts, rebalance_events, index_weights, risk_index_history, app_config, model_runs CASCADE")
    await seed_market(pool)
    await build_library(pool, lambda texts: fake_embed(texts))
    await build_portfolio(pool, csv_path=None)
    rows = []
    for s in UNIVERSE:
        rows += parse_filings(submissions_block(s.ticker, 60), s.ticker)
    await pool.executemany("INSERT INTO corporate_events (id, ticker, filed_at, form, items, event_type) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
                           [(r["id"], r["ticker"], r["filed_at"], r["form"], r["items"], r["event_type"]) for r in rows])
    await label_events(pool)
    await train_impact(pool, IMPACT_PATH, os.path.join(ART_DIR, "metrics.json"))
    await ensure_default_rules(pool)
    await pool.close()


def seed_once():
    global _seeded
    if not _seeded:
        asyncio.run(_seed())
        _seeded = True


async def reset_state(pool):
    """Clear everything the tests mutate, keeping the seeded market, library, book and filings."""
    await pool.execute("TRUNCATE documents, stress_runs, stress_watchlist, alerts, rebalance_events, index_weights, "
                       "risk_index_history, app_config CASCADE")
    await pool.execute("UPDATE stress_rules SET last_fired = NULL, enabled = TRUE")
    from sentinel.stress import service
    service._replay_cooldown.clear()
