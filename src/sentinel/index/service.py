"""Module A service: configuration, benchmark, live recompute, rebalances (auto or approval), constituents."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np

from .. import store
from ..audit import ledger
from ..events import publish
from ..market.series import load_prices
from ..universe import UNIVERSE
from .weights import (DEFAULT_CONFIG, constrain, signal_scores, tilt_target, turnover, validate_config, zscores)

log = logging.getLogger(__name__)
TICKERS = [s.ticker for s in UNIVERSE]
NAMES = {s.ticker: s.name for s in UNIVERSE}
SECTORS = {s.ticker: s.sector for s in UNIVERSE}
EPS = 1e-6


class IndexError_(ValueError):
    pass


async def get_config(pool) -> dict:
    stored = await store.get_config(pool, "index_config") or {}
    try:
        return validate_config(stored, len(TICKERS))
    except ValueError:
        log.warning("stored index_config is invalid, using defaults")
        return validate_config({}, len(TICKERS))


async def set_config(pool, redis, patch: dict, actor: str = "api") -> dict:
    unknown = set(patch) - set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    old = await get_config(pool)
    new = validate_config({**old, **patch}, len(TICKERS))          # raises ValueError on a bad value
    await store.set_config(pool, "index_config", new)
    changed = {k: {"from": old[k], "to": new[k]} for k in new if new[k] != old[k]}
    if changed:
        await ledger.append(pool, actor, "config_change", "Adaptive Index configuration changed: " + ", ".join(sorted(changed)),
                            {"changes": changed})
    return new


async def benchmark(pool) -> tuple:
    """(weights array in TICKERS order, basis). Market-cap weights when `sync-caps` has run, else equal weight."""
    caps = (await store.get_config(pool, "benchmark_caps") or {}).get("caps") or {}
    if all(caps.get(t) for t in TICKERS):
        v = np.array([float(caps[t]) for t in TICKERS])
        return v / v.sum(), "market_cap"
    return np.full(len(TICKERS), 1.0 / len(TICKERS)), "equal_weight_fallback"


async def sync_caps(pool) -> dict:
    """Market caps from Yahoo Finance (unofficial, cached in our DB)."""
    import yfinance as yf

    def fetch(t):
        try:
            return float(yf.Ticker(t).fast_info["market_cap"])
        except Exception:
            return None
    caps = {}
    for t in TICKERS:
        caps[t] = await asyncio.to_thread(fetch, t)
        await asyncio.sleep(0.4)
    ok = {t: v for t, v in caps.items() if v and v > 0}
    if len(ok) != len(TICKERS):
        raise RuntimeError(f"market cap missing for {sorted(set(TICKERS) - set(ok))}: keeping the previous benchmark")
    await store.set_config(pool, "benchmark_caps", {"asof": datetime.now(timezone.utc).isoformat(), "caps": ok})
    return ok


ALLOWED = {"live": ("live", "backfill"), "backfill": ("backfill",), "replay": ("live", "backfill", "replay")}


async def weights_asof(pool, source: str, asof: datetime | None = None, con=None):
    """(ts, weights array) of the latest stored weights on or before `asof`; (None, None) when there are none."""
    q = ("SELECT ts, weights FROM index_weights WHERE source = ANY($1) AND ($2::timestamptz IS NULL OR ts <= $2) "
         "ORDER BY ts DESC LIMIT 1")
    r = await (con or pool).fetchrow(q, list(ALLOWED.get(source, (source,))), asof)
    if r is None:
        return None, None
    w = json.loads(r["weights"]) if isinstance(r["weights"], str) else r["weights"]
    return r["ts"], np.array([float(w[t]) for t in TICKERS])


def _weights_json(w: np.ndarray) -> str:
    return json.dumps({t: float(x) for t, x in zip(TICKERS, w)})


async def load_signals(pool, source: str, now: datetime, lookback_days: float) -> list:
    rows = await pool.fetch(
        "SELECT id, ts, ticker, sentiment, confidence, half_life_days, integrity, headline FROM signals "
        "WHERE ticker = ANY($1) AND ts > $2 AND ts <= $3 AND ($4 OR mode <> 'replay') ORDER BY ts",
        TICKERS, now - timedelta(days=lookback_days), now, source == "replay")
    out = []
    for r in rows:
        integ = json.loads(r["integrity"]) if isinstance(r["integrity"], str) else r["integrity"]
        out.append({"id": r["id"], "ts": r["ts"], "ticker": r["ticker"], "sentiment": r["sentiment"],
                    "confidence": r["confidence"], "halfLifeDays": r["half_life_days"], "integrity": integ,
                    "headline": r["headline"]})
    return out


def moves_json(cur: np.ndarray, new: np.ndarray) -> list:
    return [{"ticker": t, "name": NAMES[t], "from": float(a), "to": float(b), "delta": float(b - a)}
            for t, a, b in zip(TICKERS, cur, new)]


def rebalance_api(r) -> dict:
    mv = json.loads(r["moves"]) if isinstance(r["moves"], str) else r["moves"]
    return {"id": r["id"], "ts": r["ts"].isoformat(), "triggerSignalId": r["trigger_signal_id"],
            "triggerHeadline": r["trigger_headline"], "status": r["status"],
            "moves": sorted((m for m in mv if abs(m["delta"]) > EPS), key=lambda m: -abs(m["delta"])),
            "turnover": 0.5 * sum(abs(m["delta"]) for m in mv),
            "decidedAt": r["decided_at"].isoformat() if r["decided_at"] else None, "source": r["source"]}


async def recompute(pool, redis, now: datetime | None = None, source: str = "live", trigger: dict | None = None,
                    actor: str = "index-engine") -> dict | None:
    """Recompute the target weights from the signals as of `now` and rebalance (auto) or propose it (approval).
    Returns the rebalance event in API shape, or None when nothing moved."""
    now = now or datetime.now(timezone.utc)
    cfg = await get_config(pool)
    bench, _ = await benchmark(pool)
    sigs = await load_signals(pool, source, now, cfg["lookbackDays"])
    scores, _ = signal_scores(sigs, now, cfg, TICKERS)
    target = tilt_target(bench, zscores(scores, cfg["zFloor"]), cfg)
    event, weights_row = None, None
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"index:{source}")
            ts0, cur = await weights_asof(pool, source, now, con)
            if cur is None:                                             # first ever state: start from the benchmark
                cur = bench
                await con.execute("INSERT INTO index_weights (ts, weights, source) VALUES ($1,$2::jsonb,$3) "
                                  "ON CONFLICT (source, ts) DO NOTHING", now, _weights_json(cur), source)
            new = constrain(cur, target, bench, cfg)
            if float(np.abs(new - cur).max()) <= EPS:
                return None
            sig_id = trigger["id"] if trigger else None
            head = trigger["headline"] if trigger else "Scheduled recompute (signal decay)"
            mv = json.dumps(moves_json(cur, new))
            if cfg["mode"] == "auto":
                eid = f"rb-{source}-{uuid.uuid4().hex[:10]}"
                await con.execute("INSERT INTO index_weights (ts, weights, source) VALUES ($1,$2::jsonb,$3) "
                                  "ON CONFLICT (source, ts) DO UPDATE SET weights = EXCLUDED.weights", now, _weights_json(new), source)
                await con.execute("INSERT INTO rebalance_events (id, ts, trigger_signal_id, trigger_headline, status, moves, decided_at, source) "
                                  "VALUES ($1,$2,$3,$4,'applied',$5::jsonb,$2,$6)", eid, now, sig_id, head, mv, source)
                action, status = "rebalance", "applied"
            else:
                pend = await con.fetchrow("SELECT id FROM rebalance_events WHERE status='pending' AND source=$1 "
                                          "ORDER BY ts DESC LIMIT 1 FOR UPDATE", source)
                if pend:                                                # one open proposal at a time: refresh it
                    eid = pend["id"]
                    await con.execute("UPDATE rebalance_events SET ts=$2, trigger_signal_id=$3, trigger_headline=$4, moves=$5::jsonb WHERE id=$1",
                                      eid, now, sig_id, head, mv)
                else:
                    eid = f"rb-{source}-{uuid.uuid4().hex[:10]}"
                    await con.execute("INSERT INTO rebalance_events (id, ts, trigger_signal_id, trigger_headline, status, moves, source) "
                                      "VALUES ($1,$2,$3,$4,'pending',$5::jsonb,$6)", eid, now, sig_id, head, mv, source)
                action, status = "rebalance_proposed", "pending"
            tv = turnover(cur, new)
            await ledger.append_con(con, actor, action, f"{'Applied' if status == 'applied' else 'Proposed'} rebalance: {head[:120]}",
                                    {"rebalanceId": eid, "source": source, "turnover": tv, "triggerSignalId": sig_id,
                                     "moves": [m for m in json.loads(mv) if abs(m["delta"]) > EPS]}, ts=now)
            r = await con.fetchrow("SELECT * FROM rebalance_events WHERE id = $1", eid)
            event = rebalance_api(r)
    await publish(redis, "rebalance", event, source)
    return event


async def decide(pool, redis, rebalance_id: str, approve: bool, actor: str = "api") -> dict:
    now = datetime.now(timezone.utc)
    async with pool.acquire() as con:
        async with con.transaction():
            r = await con.fetchrow("SELECT * FROM rebalance_events WHERE id = $1 FOR UPDATE", rebalance_id)
            if r is None:
                raise KeyError(rebalance_id)
            if r["status"] != "pending":
                raise IndexError_(f"rebalance is already {r['status']}")
            mv = json.loads(r["moves"]) if isinstance(r["moves"], str) else r["moves"]
            if approve:
                await con.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"index:{r['source']}")
                _, cur = await weights_asof(pool, r["source"], now, con)
                new = np.array([next(m["to"] for m in mv if m["ticker"] == t) for t in TICKERS])
                if cur is not None and not np.allclose(cur, [next(m["from"] for m in mv if m["ticker"] == t) for t in TICKERS], atol=1e-6):
                    raise IndexError_("the live weights changed since this proposal was made: wait for a refreshed proposal")
                if abs(new.sum() - 1.0) > 1e-6:
                    raise IndexError_("proposal does not sum to 1")
                await con.execute("INSERT INTO index_weights (ts, weights, source) VALUES ($1,$2::jsonb,$3) "
                                  "ON CONFLICT (source, ts) DO UPDATE SET weights = EXCLUDED.weights", now, _weights_json(new), r["source"])
            await con.execute("UPDATE rebalance_events SET status=$2, decided_at=$3 WHERE id=$1",
                              rebalance_id, "applied" if approve else "rejected", now)
            await ledger.append_con(con, actor, "rebalance_approved" if approve else "rebalance_rejected",
                                    f"{'Approved' if approve else 'Rejected'} rebalance {rebalance_id}",
                                    {"rebalanceId": rebalance_id, "source": r["source"]}, ts=now)
            event = rebalance_api(await con.fetchrow("SELECT * FROM rebalance_events WHERE id = $1", rebalance_id))
    await publish(redis, "rebalance", event, event["source"])
    return event


async def list_rebalances(pool, source: str = "live", status: str | None = None, limit: int = 50) -> list:
    rows = await pool.fetch("SELECT * FROM rebalance_events WHERE source = $1 AND ($2::text IS NULL OR status = $2) "
                            "ORDER BY ts DESC LIMIT $3", source, status, limit)
    return [rebalance_api(r) for r in rows]


async def constituents(pool, source: str = "live", now: datetime | None = None) -> list:
    now = now or datetime.now(timezone.utc)
    cfg = await get_config(pool)
    bench, basis = await benchmark(pool)
    _, cur = await weights_asof(pool, source, now)
    cur = bench if cur is None else cur
    sigs = await load_signals(pool, source, now, cfg["lookbackDays"])
    scores, cnt = signal_scores(sigs, now, cfg, TICKERS)
    z = zscores(scores, cfg["zFloor"])
    sent, integ = {}, {}
    for g in sigs:
        sent.setdefault(g["ticker"], []).append(g["sentiment"])
        integ.setdefault(g["ticker"], []).append(g["integrity"]["score"])
    px = await load_prices(pool, TICKERS, (now - timedelta(days=10)).date().isoformat())
    last = {t: float(px[t].dropna().iloc[-1]) for t in TICKERS if t in px and px[t].notna().any()}
    mean = lambda v: float(np.mean(v)) if v else None
    return [{"ticker": t, "name": NAMES[t], "sector": SECTORS[t], "benchmarkWeight": float(bench[i]), "weight": float(cur[i]),
             "activeWeight": float(cur[i] - bench[i]), "signalScore": float(scores[i]), "zScore": float(z[i]),
             "signalCount": int(cnt[i]), "benchmarkBasis": basis,
             "meanSentiment": mean(sent.get(t)), "meanIntegrity": mean(integ.get(t)), "price": last.get(t)}
            for i, t in enumerate(TICKERS)]


async def weights_history(pool, source: str = "live", since: datetime | None = None, until: datetime | None = None,
                          limit: int = 2000) -> list:
    rows = await pool.fetch(
        "SELECT ts, weights, source FROM index_weights WHERE source = ANY($1) AND ($2::timestamptz IS NULL OR ts >= $2) "
        "AND ($3::timestamptz IS NULL OR ts <= $3) ORDER BY ts DESC LIMIT $4",
        list(ALLOWED.get(source, (source,))), since, until, limit)
    out = []
    for r in reversed(rows):
        w = json.loads(r["weights"]) if isinstance(r["weights"], str) else r["weights"]
        out.append({"ts": r["ts"].isoformat(), "source": r["source"], "weights": {t: float(w[t]) for t in TICKERS}})
    return out
