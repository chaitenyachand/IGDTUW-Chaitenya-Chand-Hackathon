"""Jobs around the company-event impact model: train it from the labelled SEC 8-K history and store the evaluation."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from ..market.series import abs_window_returns, load_prices
from .model import VERSION, train

MODEL_PATH = "models/impact_v1.joblib"
METRICS_PATH = "data/models/metrics_impact.json"


async def load_training_rows(pool) -> list:
    rows = await pool.fetch(
        "SELECT t0, event_type, abs_car3, vol60, vix_prev, prior_abs, beta FROM corporate_events "
        "WHERE car3 IS NOT NULL AND t0 IS NOT NULL AND vol60 IS NOT NULL AND prior_abs IS NOT NULL AND beta IS NOT NULL "
        "ORDER BY t0")
    return [dict(r) for r in rows]


async def train_impact(pool, path: str = MODEL_PATH, metrics_path: str = METRICS_PATH) -> dict:
    import joblib
    rows = await load_training_rows(pool)
    if len(rows) < 30:
        raise RuntimeError(f"only {len(rows)} labelled 8-K events: run `make edgar` and `make label-events` first")
    px = await load_prices(pool, ["SPY"], "1999-01-01")
    if "SPY" not in px:
        raise RuntimeError("no SPY prices: run `make prices` first")
    art, metrics = train(rows, abs_window_returns(px["SPY"], 5))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    joblib.dump(art, path)
    by_type: dict = {}
    for r in rows:
        by_type[r["event_type"]] = by_type.get(r["event_type"], 0) + 1
    metrics.update({"version": VERSION, "trained_at": art["trained_at"], "events_by_type": by_type,
                    "label": "|3-day cumulative abnormal return| vs SPY market model (250-day estimation window)"})
    os.makedirs(os.path.dirname(metrics_path) or ".", exist_ok=True)
    with open(metrics_path, "w") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    await pool.execute("INSERT INTO model_runs (kind, model_version, metrics) VALUES ('impact', $1, $2::jsonb)",
                       VERSION, json.dumps(metrics, default=str))
    return metrics
