"""Input / output drift: population stability index of recent signal features against a stored baseline snapshot."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np

NUMERIC = ("sentiment", "confidence", "impact", "integrity")
EPS = 1e-4


def psi(expected: np.ndarray, actual: np.ndarray) -> float:
    e, a = np.clip(np.asarray(expected, float), EPS, None), np.clip(np.asarray(actual, float), EPS, None)
    e, a = e / e.sum(), a / a.sum()
    return float(np.sum((a - e) * np.log(a / e)))


def interpret(v: float | None) -> str | None:
    return None if v is None else ("stable" if v < 0.1 else ("moderate" if v < 0.25 else "significant"))


def snapshot_from_rows(rows: list, bins: int = 10) -> dict:
    """Quantile bin edges + proportions per numeric feature, and the event-type mix."""
    snap = {"n": len(rows), "features": {}, "eventTypes": {}}
    for f in NUMERIC:
        v = np.array([r[f] for r in rows if r[f] is not None], dtype=float)
        if len(v) < 30:
            continue
        edges = np.unique(np.quantile(v, np.linspace(0, 1, bins + 1)))
        if len(edges) < 3:
            continue
        edges[0], edges[-1] = -np.inf, np.inf
        p = np.histogram(v, bins=edges)[0] / len(v)
        snap["features"][f] = {"edges": [None if np.isinf(x) else float(x) for x in edges], "p": p.tolist()}
    tot = max(len(rows), 1)
    for r in rows:
        snap["eventTypes"][r["eventType"]] = snap["eventTypes"].get(r["eventType"], 0) + 1 / tot
    return snap


def compare(snap: dict, rows: list) -> dict:
    out = {"n": len(rows), "features": {}, "eventTypes": None}
    for f, s in snap["features"].items():
        v = np.array([r[f] for r in rows if r[f] is not None], dtype=float)
        if len(v) < 30:
            out["features"][f] = {"psi": None, "status": None, "n": int(len(v))}
            continue
        edges = np.array([-np.inf if x is None and i == 0 else (np.inf if x is None else x) for i, x in enumerate(s["edges"])])
        a = np.histogram(v, bins=edges)[0] / len(v)
        val = psi(np.array(s["p"]), a)
        out["features"][f] = {"psi": val, "status": interpret(val), "n": int(len(v))}
    if rows and snap["eventTypes"]:
        keys = sorted(set(snap["eventTypes"]) | {r["eventType"] for r in rows})
        e = np.array([snap["eventTypes"].get(k, 0.0) for k in keys])
        a = np.array([sum(1 for r in rows if r["eventType"] == k) / len(rows) for k in keys])
        val = psi(e, a)
        out["eventTypes"] = {"psi": val, "status": interpret(val), "n": len(rows)}
    return out


async def _rows(pool, start, end) -> list:
    rs = await pool.fetch("SELECT sentiment, confidence, impact, integrity, event_type FROM signals "
                          "WHERE ts > $1 AND ts <= $2 AND mode <> 'replay'", start, end)
    return [{"sentiment": r["sentiment"], "confidence": r["confidence"], "impact": r["impact"],
             "integrity": (json.loads(r["integrity"]) if isinstance(r["integrity"], str) else r["integrity"])["score"],
             "eventType": r["event_type"]} for r in rs]


async def take_baseline(pool, days: int = 14, recent_hours: int = 24) -> dict:
    now = datetime.now(timezone.utc)
    rows = await _rows(pool, now - timedelta(days=days), now - timedelta(hours=recent_hours))
    snap = snapshot_from_rows(rows)
    if snap["n"] < 100:
        raise RuntimeError(f"only {snap['n']} signals older than {recent_hours}h: let the serving worker run longer before taking a baseline")
    snap["takenAt"] = now.isoformat()
    await pool.execute("INSERT INTO model_runs (kind, metrics) VALUES ('drift_baseline', $1::jsonb)", json.dumps(snap))
    return snap


async def current_drift(pool, recent_hours: int = 24) -> dict | None:
    r = await pool.fetchval("SELECT metrics FROM model_runs WHERE kind = 'drift_baseline' ORDER BY ts DESC LIMIT 1")
    if r is None:
        return None
    snap = json.loads(r) if isinstance(r, str) else r
    now = datetime.now(timezone.utc)
    res = compare(snap, await _rows(pool, now - timedelta(hours=recent_hours), now))
    res.update({"baselineTakenAt": snap["takenAt"], "baselineN": snap["n"], "windowHours": recent_hours})
    return res


THRESHOLD = 0.25          # PSI above this is "significant" (see interpret)


async def series(pool, days: int = 30, window_hours: int = 24, min_rows: int = 30) -> dict | None:
    """Daily drift against the stored baseline: for each of the last `days` days, the largest feature PSI (and the event-type PSI)
    over that day's trailing `window_hours`. Days with too few signals are skipped, never filled in."""
    r = await pool.fetchval("SELECT metrics FROM model_runs WHERE kind = 'drift_baseline' ORDER BY ts DESC LIMIT 1")
    if r is None:
        return None
    snap = json.loads(r) if isinstance(r, str) else r
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    out = []
    for k in range(days, -1, -1):
        end = now - timedelta(days=k)
        res = compare(snap, await _rows(pool, end - timedelta(hours=window_hours), end))
        vals = [v["psi"] for v in res["features"].values() if v["psi"] is not None]
        if res["eventTypes"] and res["eventTypes"]["n"] >= min_rows:
            vals.append(res["eventTypes"]["psi"])
        if vals:
            out.append({"ts": end.isoformat(), "psi": float(max(vals))})
    return {"threshold": THRESHOLD, "series": out}
