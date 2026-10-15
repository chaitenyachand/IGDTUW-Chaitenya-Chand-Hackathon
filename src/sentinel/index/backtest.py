"""Point-in-time backtest of the Adaptive Index on real prices: static benchmark vs SENTINEL tilt vs a naive sentiment
rebalancer, each net of the transaction-cost assumption. The same weight code the live engine runs is used here."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from ..market.series import load_prices
from .service import ALLOWED, TICKERS, benchmark, get_config, _weights_json
from .weights import constrain, naive_target, signal_scores, tilt_target, turnover, zscores

ANN = 252


def metrics(daily: np.ndarray, bench_daily: np.ndarray | None, turn_daily: np.ndarray) -> dict:
    daily = np.asarray(daily)
    curve = np.cumprod(1.0 + daily)
    dd = curve / np.maximum.accumulate(curve) - 1.0
    out = {"totalReturn": float(curve[-1] - 1.0), "annReturn": float(curve[-1] ** (ANN / max(len(daily), 1)) - 1.0),
           "annVol": float(np.std(daily, ddof=1) * math.sqrt(ANN)) if len(daily) > 1 else 0.0,
           "maxDrawdown": float(dd.min()), "annTurnover": float(turn_daily.sum() * ANN / max(len(daily), 1)),
           "totalTurnover": float(turn_daily.sum())}
    if bench_daily is not None:
        active = daily - np.asarray(bench_daily)
        te = float(np.std(active, ddof=1) * math.sqrt(ANN)) if len(active) > 1 else 0.0
        td = float(np.mean(active) * ANN)
        out.update({"trackingDifference": td, "trackingError": te, "informationRatio": float(td / te) if te > 1e-12 else None})
    return out


def simulate(rets: pd.DataFrame, bench: np.ndarray, sigs: list, cfg: dict) -> dict:
    """rets: daily simple returns (index = dates, columns = TICKERS). Weights for day d use only signals before d."""
    cost = cfg["costBps"] / 1e4
    w_s, w_n = bench.copy(), bench.copy()
    ts_list = [g["ts"] for g in sigs]
    rows, wts = [], []
    r_b, r_s, r_n, t_s, t_n = [], [], [], [], []
    look = timedelta(days=cfg["lookbackDays"])
    lo_i = 0
    for d, r in rets.iterrows():
        day = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        hi = _bisect(ts_list, day)                           # signals strictly before the day: no look-ahead
        while lo_i < hi and ts_list[lo_i] <= day - look:
            lo_i += 1
        window = sigs[lo_i:hi]
        scores, _ = signal_scores(window, day, cfg, TICKERS)
        new_s = constrain(w_s, tilt_target(bench, zscores(scores, cfg["zFloor"]), cfg), bench, cfg)
        new_n = naive_target(bench, window, day, cfg, TICKERS)
        ts_, tn_ = turnover(w_s, new_s), turnover(w_n, new_n)
        rv = r.values.astype(float)
        r_b.append(float(bench @ rv))
        r_s.append(float(new_s @ rv - cost * ts_))
        r_n.append(float(new_n @ rv - cost * tn_))
        t_s.append(ts_)
        t_n.append(tn_)
        if ts_ > 1e-9 or not wts:
            wts.append((day, new_s.copy()))
        w_s, w_n = new_s, new_n
    r_b, r_s, r_n = np.array(r_b), np.array(r_s), np.array(r_n)
    curves = {k: 100.0 * np.cumprod(1.0 + v) for k, v in (("benchmark", r_b), ("sentinel", r_s), ("naive", r_n))}
    series = [{"date": d.date().isoformat(), "benchmark": float(curves["benchmark"][i]), "sentinel": float(curves["sentinel"][i]),
               "naive": float(curves["naive"][i])} for i, d in enumerate(rets.index)]
    return {"series": series, "weights": wts,
            "metrics": {"benchmark": metrics(r_b, None, np.zeros(len(r_b))), "sentinel": metrics(r_s, r_b, np.array(t_s)),
                        "naive": metrics(r_n, r_b, np.array(t_n))}}


def _bisect(ts_list: list, t) -> int:
    lo, hi = 0, len(ts_list)
    while lo < hi:
        m = (lo + hi) // 2
        if ts_list[m] < t:
            lo = m + 1
        else:
            hi = m
    return lo


async def run_backtest(pool, days: int = 250, source: str = "live") -> dict:
    cfg = await get_config(pool)
    bench, basis = await benchmark(pool)
    px = await load_prices(pool, TICKERS, "2000-01-01")
    missing = [t for t in TICKERS if t not in px]
    if missing:
        return {"status": "no_prices", "message": f"no price history for {missing}: run `make prices`", "series": [], "metrics": {}}
    rets = px[TICKERS].pct_change().dropna().tail(days)
    if len(rets) < 20:
        return {"status": "no_prices", "message": "fewer than 20 days of aligned prices", "series": [], "metrics": {}}
    start = datetime(rets.index[0].year, rets.index[0].month, rets.index[0].day, tzinfo=timezone.utc) - timedelta(days=cfg["lookbackDays"])
    rows = await pool.fetch(
        "SELECT ts, ticker, sentiment, confidence, half_life_days, integrity FROM signals WHERE ticker = ANY($1) AND ts >= $2 "
        "AND ($3 OR mode <> 'replay') ORDER BY ts", TICKERS, start, source == "replay")
    sigs = [{"ts": r["ts"], "ticker": r["ticker"], "sentiment": r["sentiment"], "confidence": r["confidence"],
             "halfLifeDays": r["half_life_days"], "integrity": json.loads(r["integrity"]) if isinstance(r["integrity"], str) else r["integrity"]}
            for r in rows]
    res = simulate(rets, bench, sigs, cfg)
    res.update({"status": "ready" if sigs else "no_signals", "costBps": cfg["costBps"], "benchmarkBasis": basis,
                "signalsUsed": len(sigs), "window": {"from": rets.index[0].date().isoformat(), "to": rets.index[-1].date().isoformat()},
                "assumptions": f"net of {cfg['costBps']:g} bps per unit one-way turnover; weights for each day use only signals "
                               "published before that day; naive = mean sentiment of the last 24h with no integrity filter, "
                               "decay, deadband or turnover cap"})
    return res


async def backfill_weights(pool, days: int = 250) -> dict:
    """Replay the archived signal corpus through the same weight code and store the daily weights (source = backfill)."""
    res = await run_backtest(pool, days, "live")
    if res["status"] == "no_prices":
        return res
    wts = res["weights"]
    start = datetime.fromisoformat(res["window"]["from"]).replace(tzinfo=timezone.utc)
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute("DELETE FROM index_weights WHERE source = 'backfill' AND ts >= $1", start)
            await con.executemany("INSERT INTO index_weights (ts, weights, source) VALUES ($1,$2::jsonb,'backfill') "
                                  "ON CONFLICT (source, ts) DO UPDATE SET weights = EXCLUDED.weights",
                                  [(d, _weights_json(w)) for d, w in wts])
    return {"status": res["status"], "rows": len(wts), "window": res["window"], "signalsUsed": res["signalsUsed"]}
