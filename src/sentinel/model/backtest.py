"""Point-in-time backtest of the signals themselves: do higher-sentiment signals precede higher forward abnormal returns?

For every signal on an index stock that is old enough, the 3-day cumulative abnormal return from the next tradable session
(market model against SPY, estimated before the event) is measured with the same code that labels the training events.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.stats import spearmanr

from ..impact.event_study import event_study, reaction_day
from ..market.series import load_prices
from ..universe import UNIVERSE

TICKERS = [s.ticker for s in UNIVERSE]
MIN_SIGNALS = 50


def quintiles(score: np.ndarray, car: np.ndarray) -> list:
    order = np.argsort(score, kind="stable")
    return [{"quintile": i + 1, "n": int(len(ix)), "meanScore": float(score[ix].mean()), "meanCar3": float(car[ix].mean()),
             "hitRate": float(np.mean(car[ix] > 0))} for i, ix in enumerate(np.array_split(order, 5)) if len(ix)]


def summarize(score: np.ndarray, car: np.ndarray) -> dict:
    q = quintiles(score, car)
    rho = spearmanr(score, car)
    return {"quintiles": q, "spearman": None if np.isnan(rho.correlation) else float(rho.correlation),
            "pValue": None if np.isnan(rho.pvalue) else float(rho.pvalue),
            "topMinusBottom": float(q[-1]["meanCar3"] - q[0]["meanCar3"]) if len(q) >= 2 else None}


async def signal_backtest(pool, min_age_days: int = 8) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
    rows = await pool.fetch(
        "SELECT ts, ticker, sentiment, confidence, integrity FROM signals WHERE ticker = ANY($1) AND ts <= $2 AND mode <> 'replay' ORDER BY ts",
        TICKERS, cutoff)
    px = await load_prices(pool, TICKERS + ["SPY"], "1999-01-01")
    out = {"minAgeDays": min_age_days, "signalsConsidered": len(rows)}
    if "SPY" not in px:
        out.update({"status": "no_prices", "n": 0})
        return out
    sent, comp, car = [], [], []
    for r in rows:
        if r["ticker"] not in px:
            continue
        res = event_study(px[r["ticker"]].dropna(), px["SPY"].dropna(), reaction_day(r["ts"]))
        if not res:
            continue
        integ = json.loads(r["integrity"]) if isinstance(r["integrity"], str) else r["integrity"]
        sent.append(r["sentiment"])
        comp.append(r["sentiment"] * integ["score"] * r["confidence"])
        car.append(res["car3"])
    out["n"] = len(car)
    if len(car) < MIN_SIGNALS:
        out["status"] = "insufficient_data"
        out["message"] = f"{len(car)} signals with forward returns; at least {MIN_SIGNALS} are needed for quintiles"
        return out
    s, c, k = np.array(sent), np.array(comp), np.array(car)
    out.update({"status": "ready", "bySentiment": summarize(s, k), "byCompositeScore": summarize(c, k),
                "label": "3-day cumulative abnormal return vs SPY market model, from the next tradable session",
                "period": [rows[0]["ts"].date().isoformat(), rows[-1]["ts"].date().isoformat()]})
    await pool.execute("INSERT INTO model_runs (kind, metrics) VALUES ('signal_backtest', $1::jsonb)", json.dumps(out, default=str))
    return out
