"""PRECEDENT: match a live signal to historical events and summarise what markets did afterwards (all real data)."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np

HORIZON_IDX = 4            # path index 4 = five trading days including the reaction day
DEFAULT_MIN_SIM = 0.40
W_EMB, W_TYPE, W_REGIME = 0.55, 0.25, 0.20
FACTOR_ASSETS = ("dgs10_bps", "dgs2_bps", "vix_pts")


@dataclass
class Event:
    id: str
    title: str
    date: object
    reaction: object
    type: str
    region: str
    vix: float | None
    emb: np.ndarray
    paths: dict = field(default_factory=dict)          # asset_key -> [(k, value)]
    stats: dict = field(default_factory=dict)          # asset_key -> (max_drawdown, recovery_days)


class Library:
    def __init__(self, events: list):
        self.events = events

    @classmethod
    async def load(cls, pool):
        rows = await pool.fetch("SELECT * FROM event_library ORDER BY event_date")
        outs = await pool.fetch("SELECT event_id, asset_key, path, max_drawdown, recovery_days FROM event_outcomes")
        by: dict = {}
        for o in outs:
            by.setdefault(o["event_id"], {})[o["asset_key"]] = o
        events = []
        for r in rows:
            e = Event(r["id"], r["title"], r["event_date"], r["reaction_date"], r["event_type"], r["region"], r["vix_level"],
                      np.asarray(r["embedding"] or [], dtype=float))
            for k, o in by.get(r["id"], {}).items():
                p = o["path"]
                e.paths[k] = json.loads(p) if isinstance(p, str) else p
                e.stats[k] = (o["max_drawdown"], o["recovery_days"])
            events.append(e)
        return cls(events)

    def __len__(self):
        return len(self.events)

    def match(self, emb, event_type: str | None, vix_now: float | None, min_sim: float = DEFAULT_MIN_SIM,
              k: int = 10, before=None) -> list:
        """Top analogs as [(similarity, Event)]. `before` restricts to events earlier than a date (point-in-time use)."""
        out = []
        e_norm = float(np.linalg.norm(emb)) or 1.0
        for ev in self.events:
            if before is not None and ev.date >= before:
                continue
            if ev.emb.size == 0 or ev.emb.shape != np.asarray(emb).shape:
                continue
            cos = max(0.0, float(np.dot(emb, ev.emb)) / (e_norm * (float(np.linalg.norm(ev.emb)) or 1.0)))
            type_match = 1.0 if (event_type and event_type == ev.type) else 0.0
            regime = math.exp(-abs(vix_now - ev.vix) / 10.0) if (vix_now is not None and ev.vix is not None) else 0.5
            sim = W_EMB * cos + W_TYPE * type_match + W_REGIME * regime
            if sim >= min_sim:
                out.append((sim, ev))
        out.sort(key=lambda t: -t[0])
        return out[:k]


def _quantiles(arr):
    a = np.asarray(arr, dtype=float)
    return float(np.median(a)), float(np.percentile(a, 10)), float(np.percentile(a, 90))


def aggregate(analogs: list, horizon_idx: int = HORIZON_IDX) -> dict:
    """Median path, p10-p90 band and the shock at the horizon, per asset class, over the matched analogs."""
    assets = sorted({k for _, ev in analogs for k in ev.paths})
    series, shocks, factor_shocks = {}, [], {}
    for a in assets:
        paths = [ev.paths[a] for _, ev in analogs if a in ev.paths]
        if not paths:
            continue
        mat = np.array([[v for _, v in p] for p in paths])
        med = np.median(mat, axis=0)
        p10, p90 = np.percentile(mat, 10, axis=0), np.percentile(mat, 90, axis=0)
        days = [k for k, _ in paths[0]]
        if a in FACTOR_ASSETS:
            m, lo, hi = _quantiles(mat[:, horizon_idx])
            factor_shocks[a] = {"median": m, "p10": lo, "p90": hi, "n": int(mat.shape[0])}
            continue
        series[a] = {"n": int(mat.shape[0]), "median": [{"day": d, "ret": float(x)} for d, x in zip(days, med)],
                     "band": [{"day": d, "p10": float(l), "p90": float(h)} for d, l, h in zip(days, p10, p90)]}
        m, lo, hi = _quantiles(mat[:, horizon_idx])
        shocks.append({"assetClass": a, "median": m, "p10": lo, "p90": hi, "n": int(mat.shape[0])})
    return {"series": series, "shocks": shocks, "factorShocks": factor_shocks}


def half_life_days(series: dict):
    """Trading days for the median equity-index move to halve after its peak (None if it does not within the window)."""
    s = series.get("equity_index")
    if not s:
        return None
    m = np.abs([p["ret"] for p in s["median"]])
    peak = int(np.argmax(m))
    if m[peak] < 1e-4:
        return None
    for k in range(peak + 1, len(m)):
        if m[k] <= m[peak] / 2:
            return float(k - peak)
    return None


def build_result(signal_id: str, analogs: list, horizon_idx: int = HORIZON_IDX) -> dict:
    if not analogs:
        return {"signalId": signal_id, "status": "insufficient_data", "n": 0, "dateRange": {"from": None, "to": None},
                "horizonDays": horizon_idx + 1, "analogs": [], "series": {}, "halfLifeDays": None, "shocks": [],
                "factorShocks": {}}
    agg = aggregate(analogs, horizon_idx)
    dates = [ev.date for _, ev in analogs]
    rows = []
    for sim, ev in analogs:
        eq = ev.stats.get("equity_index", (None, None))
        rows.append({"eventId": ev.id, "title": ev.title, "date": ev.date.isoformat(), "similarity": round(float(sim), 3),
                     "region": ev.region, "maxDrawdown": eq[0] if eq[0] is not None else 0.0, "recoveryDays": eq[1],
                     "paths": {k: [{"day": d, "ret": v} for d, v in p] for k, p in ev.paths.items() if k not in FACTOR_ASSETS}})
    return {"signalId": signal_id, "status": "ready", "n": len(analogs),
            "dateRange": {"from": min(dates).isoformat(), "to": max(dates).isoformat()},
            "horizonDays": horizon_idx + 1, "analogs": rows, "series": agg["series"],
            "halfLifeDays": half_life_days(agg["series"]), "shocks": agg["shocks"], "factorShocks": agg["factorShocks"]}


def spy_abs_move(ev: Event, horizon_idx: int = HORIZON_IDX):
    p = ev.paths.get("equity_index")
    return abs(p[horizon_idx][1]) if p else None


def validate_leave_one_out(lib: Library, vix_of=None, min_analogs: int = 3) -> dict:
    """Point-in-time check: calibrate each event only from EARLIER events, then compare with what really happened.
    Metrics: MAE of the calibrated 5-day equity shock vs a naive baseline (median of all earlier events), directional
    hit rate, p10-p90 band coverage, and Spearman of the kernel expected move vs realised |move|."""
    from scipy.stats import spearmanr
    ctx = [e for e in lib.events if "equity_index" in e.paths and e.emb.size]
    ctx.sort(key=lambda e: e.date)
    rows = []
    for ev in ctx:
        earlier = Library([e for e in ctx if e.date < ev.date])
        analogs = earlier.match(ev.emb, ev.type, ev.vix, min_sim=0.30, k=10)
        analogs = [(s, a) for s, a in analogs if "equity_index" in a.paths]
        if len(analogs) < min_analogs:
            continue
        real = ev.paths["equity_index"][HORIZON_IDX][1]
        vals = np.array([a.paths["equity_index"][HORIZON_IDX][1] for _, a in analogs])
        naive = float(np.median([e.paths["equity_index"][HORIZON_IDX][1] for e in earlier.events if "equity_index" in e.paths]))
        med, lo, hi = _quantiles(vals)
        rows.append({"real": real, "pred": med, "naive": naive, "lo": lo, "hi": hi})
    if len(rows) < 8:
        return {"n": len(rows), "skipped": "too few events with enough earlier analogs"}
    real = np.array([r["real"] for r in rows])
    pred = np.array([r["pred"] for r in rows])
    naive = np.array([r["naive"] for r in rows])
    return {"n": len(rows),
            "mae_calibrated": float(np.mean(np.abs(real - pred))), "mae_naive": float(np.mean(np.abs(real - naive))),
            "maeVsNaive": float(np.mean(np.abs(real - pred)) / max(np.mean(np.abs(real - naive)), 1e-9)),
            "directionalHitRate": float(np.mean(np.sign(real) == np.sign(pred))),
            "bandCoverage": float(np.mean([(r["lo"] <= r["real"] <= r["hi"]) for r in rows])),
            "spearman_pred_vs_real": float(spearmanr(pred, real).correlation)}
