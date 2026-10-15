"""Global Risk Index.

raw(t)  = sum over signals in the last 6h of impact x integrity x confidence x decay x (0.5 + 0.5 x negativity)
index   = percentile rank of raw(t) against the hourly raw values of the trailing 90 days, scaled 0 to 100.

decay = 2^(-age / halfLifeHours) (default half-life 3h); negativity = max(0, -sentiment). Signals without an impact score
are skipped (never imputed). The baseline only counts hours after the first signal exists, so a quiet hour is a real
zero but "no data yet" is not; until `minBaselinePoints` hours exist the index is reported as insufficient_history.
Mid-rank percentile: (count below + 0.5 x count equal) / n.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np

from .. import store
from ..events import publish

DEFAULT_CONFIG = {"windowHours": 6.0, "halfLifeHours": 3.0, "baselineDays": 90, "minBaselinePoints": 48,
                  "calmBelow": 40.0, "stressedAt": 70.0}
HOUR = timedelta(hours=1)


async def get_config(pool) -> dict:
    return {**DEFAULT_CONFIG, **(await store.get_config(pool, "risk_index_config") or {})}


def regime(value: float | None, cfg: dict) -> str | None:
    if value is None:
        return None
    return "Calm" if value < cfg["calmBelow"] else ("Elevated" if value < cfg["stressedAt"] else "Stressed")


def percentile_rank(x: float, ref) -> float:
    ref = np.asarray(ref, dtype=float)
    return float(100.0 * (np.sum(ref < x) + 0.5 * np.sum(ref == x)) / len(ref))


class Frame:
    """Signals as sorted numpy columns, so raw(t) over a long hourly grid costs one slice per grid point."""

    def __init__(self, rows: list):
        rows = sorted(rows, key=lambda r: r["ts"])
        self.rows = rows
        self.ts = np.array([r["ts"].timestamp() for r in rows], dtype=float)
        self.base = np.array([(r["impact"] or 0.0) * r["integrity"] * r["confidence"] for r in rows], dtype=float)
        self.neg = np.array([max(0.0, -r["sentiment"]) for r in rows], dtype=float)
        self.valid = np.array([r["impact"] is not None for r in rows], dtype=bool)

    def raw_at(self, t: datetime, cfg: dict) -> tuple:
        """(raw, number of contributing signals, per-signal contributions array aligned with the slice, slice)"""
        t0 = t.timestamp()
        lo = int(np.searchsorted(self.ts, t0 - cfg["windowHours"] * 3600, side="right"))
        hi = int(np.searchsorted(self.ts, t0, side="right"))
        if hi <= lo:
            return 0.0, 0, np.array([]), slice(lo, hi)
        age_h = (t0 - self.ts[lo:hi]) / 3600.0
        contrib = self.base[lo:hi] * (0.5 ** (age_h / cfg["halfLifeHours"])) * (0.5 + 0.5 * self.neg[lo:hi]) * self.valid[lo:hi]
        return float(contrib.sum()), int(self.valid[lo:hi].sum()), contrib, slice(lo, hi)

    def first_ts(self):
        return datetime.fromtimestamp(self.ts[0], timezone.utc) if len(self.ts) else None


def floor_hour(t: datetime) -> datetime:
    return t.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def baseline_raws(frame: Frame, t: datetime, cfg: dict) -> np.ndarray:
    first = frame.first_ts()
    if first is None:
        return np.array([])
    start = max(floor_hour(t) - timedelta(days=cfg["baselineDays"]), floor_hour(first) + timedelta(hours=cfg["windowHours"]))
    grid = []
    g = start
    end = floor_hour(t)
    while g < end:                                  # strictly before the current hour: the baseline never contains `t`
        grid.append(g)
        g += HOUR
    return np.array([frame.raw_at(g, cfg)[0] for g in grid])


def value_at(frame: Frame, t: datetime, cfg: dict) -> dict:
    raw, n, contrib, sl = frame.raw_at(t, cfg)
    ref = baseline_raws(frame, t, cfg)
    ok = len(ref) >= cfg["minBaselinePoints"]
    val = round(percentile_rank(raw, ref), 2) if ok else None
    top = []
    if n:
        order = np.argsort(-contrib)[:5]
        rows = frame.rows[sl]
        top = [{"signalId": rows[i]["id"], "headline": rows[i]["headline"], "entity": rows[i]["entity"],
                "contribution": float(contrib[i])} for i in order if contrib[i] > 0]
    return {"raw": raw, "value": val, "regime": regime(val, cfg), "nSignals": n, "baselinePoints": int(len(ref)),
            "status": "ready" if ok else "insufficient_history", "components": top}


async def load_frame(pool, source: str, start: datetime, end: datetime) -> Frame:
    rows = await pool.fetch(
        "SELECT id, ts, entity, headline, impact, sentiment, confidence, integrity FROM signals "
        "WHERE ts > $1 AND ts <= $2 AND ($3 OR mode <> 'replay') ORDER BY ts", start, end, source == "replay")
    out = []
    for r in rows:
        integ = json.loads(r["integrity"]) if isinstance(r["integrity"], str) else r["integrity"]
        out.append({"id": r["id"], "ts": r["ts"], "entity": r["entity"], "headline": r["headline"], "impact": r["impact"],
                    "sentiment": r["sentiment"], "confidence": r["confidence"], "integrity": integ["score"]})
    return Frame(out)


async def current(pool, source: str = "live", now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cfg = await get_config(pool)
    frame = await load_frame(pool, source, now - timedelta(days=cfg["baselineDays"] + 1), now)
    res = value_at(frame, now, cfg)
    res.update({"asOf": now.isoformat(), "windowHours": cfg["windowHours"],
                "thresholds": {"calm": cfg["calmBelow"], "stressed": cfg["stressedAt"]}})
    return res


async def update_and_publish(pool, redis, source: str = "live", now: datetime | None = None) -> dict:
    res = await current(pool, source, now)
    await publish(redis, "risk_index", {k: res[k] for k in ("value", "regime", "raw", "nSignals", "asOf", "status", "thresholds")}, source)
    return res


async def record_hours(pool, source: str, start: datetime, end: datetime) -> int:
    """Compute and store the hourly index for [start, end]. Idempotent. Used by the scheduler and the setup backfill."""
    cfg = await get_config(pool)
    frame = await load_frame(pool, source, start - timedelta(days=cfg["baselineDays"] + 1), end)
    rows, g = [], floor_hour(start)
    while g <= end:
        r = value_at(frame, g, cfg)
        rows.append((g, source, r["raw"], r["value"], r["regime"], r["nSignals"]))
        g += HOUR
    async with pool.acquire() as con:
        await con.executemany(
            "INSERT INTO risk_index_history (ts, source, raw, value, regime, n_signals) VALUES ($1,$2,$3,$4,$5,$6) "
            "ON CONFLICT (source, ts) DO UPDATE SET raw=EXCLUDED.raw, value=EXCLUDED.value, regime=EXCLUDED.regime, n_signals=EXCLUDED.n_signals",
            rows)
    return len(rows)


async def backfill(pool, source: str = "live") -> dict:
    """Process the archived corpus at setup so the baseline exists from day one."""
    first = await pool.fetchval("SELECT min(ts) FROM signals WHERE ($1 OR mode <> 'replay')", source == "replay")
    if first is None:
        return {"hours": 0, "message": "no signals yet: run the serving worker first"}
    end = floor_hour(datetime.now(timezone.utc))
    n = await record_hours(pool, source, floor_hour(first), end)
    return {"hours": n, "from": floor_hour(first).isoformat(), "to": end.isoformat()}


async def history(pool, source: str = "live", hours: int = 72, now: datetime | None = None) -> list:
    now = now or datetime.now(timezone.utc)
    rows = await pool.fetch("SELECT ts, value, regime, raw FROM risk_index_history WHERE source = $1 AND ts > $2 AND ts <= $3 ORDER BY ts",
                            source, now - timedelta(hours=hours), now)
    return [{"ts": r["ts"].isoformat(), "value": r["value"], "regime": r["regime"], "raw": r["raw"]} for r in rows]
