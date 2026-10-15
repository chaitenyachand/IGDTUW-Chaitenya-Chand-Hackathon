"""Company-event impact model: predicts the size of the abnormal move (|CAR over 3 days|) from real SEC 8-K history."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor

from .kernel import percentile_impact

TYPES = ["Credit Event", "Cyber", "Merger/Acquisition", "Regulatory", "Earnings", "Other 8-K"]
API_TO_TRAIN = {"Credit Event": "Credit Event", "Cyber": "Cyber", "Merger/Acquisition": "Merger/Acquisition",
                "Regulatory": "Regulatory", "Earnings": "Earnings"}
VERSION = "impact-gbm-v1"


def map_type(api_event: str) -> str:
    return API_TO_TRAIN.get(api_event, "Other 8-K")


def featurize(event_type: str, vol60: float, vix_prev, prior_abs: float, beta: float) -> list:
    onehot = [1.0 if event_type == t else 0.0 for t in TYPES]
    return onehot + [float(vol60), (float(vix_prev) if vix_prev is not None else 20.0) / 100.0, float(prior_abs), float(beta)]


def make_model():
    return GradientBoostingRegressor(n_estimators=250, max_depth=3, learning_rate=0.04, subsample=0.8, random_state=7)


def train(rows: list, spy_ref: np.ndarray) -> tuple:
    """rows: dicts with t0, event_type, abs_car3, vol60, vix_prev, prior_abs, beta. Chronological 80/20 evaluation."""
    rows = sorted(rows, key=lambda r: r["t0"])
    X = np.array([featurize(r["event_type"], r["vol60"], r["vix_prev"], r["prior_abs"], r["beta"]) for r in rows])
    y = np.array([r["abs_car3"] for r in rows])
    cut = int(len(rows) * 0.8)
    metrics = {"n_events": len(rows), "n_train": cut, "n_test": len(rows) - cut}
    if cut >= 50 and len(rows) - cut >= 20:
        m = make_model().fit(X[:cut], y[:cut])
        pred = m.predict(X[cut:])
        base = float(np.mean(y[:cut]))
        metrics.update({"spearman": float(spearmanr(pred, y[cut:]).correlation),
                        "mae": float(np.mean(np.abs(pred - y[cut:]))), "mae_baseline": float(np.mean(np.abs(base - y[cut:]))),
                        "test_period": [str(rows[cut]["t0"]), str(rows[-1]["t0"])]})
        order = np.argsort(pred)
        q = np.array_split(order, 5)
        metrics["quintile_mean_actual"] = [float(np.mean(y[cut:][i])) for i in q]
    final = make_model().fit(X, y) if len(rows) >= 30 else None
    ref = np.sort(final.predict(X)) if final is not None else np.array([])
    art = {"version": VERSION, "model": final, "ref_preds": ref,
           "spy_ref": np.quantile(spy_ref, np.linspace(0, 1, 1001)), "a0": float(np.median(spy_ref)),
           "n_events": len(rows), "trained_at": datetime.now(timezone.utc).isoformat()}
    return art, metrics


def predict_abs_car(art: dict, event_type: str, vol60, vix_prev, prior_abs, beta):
    if art.get("model") is None:
        return None
    x = np.array([featurize(map_type(event_type), vol60, vix_prev, prior_abs, beta)])
    return float(art["model"].predict(x)[0])


def impact_from_pred(art: dict, pred: float) -> float:
    return percentile_impact(pred, art["ref_preds"])
