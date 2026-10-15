"""Cross-validation and metric helpers (small-data safe)."""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold, cross_val_predict


def merge_rare(labels: list, min_count: int = 6, other: str = "Other") -> list:
    c = Counter(labels)
    return [lab if c[lab] >= min_count else other for lab in labels]


def can_cv(y: list) -> bool:
    c = Counter(y)
    return len(c) >= 2 and min(c.values()) >= 2


def n_splits_for(y: list, max_splits: int = 5) -> int:
    return max(2, min(max_splits, min(Counter(y).values())))


def take(X, idx: list):
    return [X[i] for i in idx] if isinstance(X, list) else X[idx]


def cv_predict(model, X, y: list, seed: int = 7, max_splits: int = 5):
    """Out-of-fold predictions and probabilities. The model is refitted per fold, so there is no leakage."""
    skf = StratifiedKFold(n_splits=n_splits_for(y, max_splits), shuffle=True, random_state=seed)
    proba = cross_val_predict(model, X, y, cv=skf, method="predict_proba")
    classes = sorted(set(y))
    pred = [classes[i] for i in np.argmax(proba, axis=1)]
    return pred, proba, classes


def report(y_true: list, y_pred: list, labels: list) -> dict:
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        "n": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "per_class": {str(l): {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]),
                               "support": int(s[i])} for i, l in enumerate(labels)},
    }


def bootstrap_ci(y_true: list, y_pred: list, metric, n: int = 1000, seed: int = 7, alpha: float = 0.05):
    """Percentile bootstrap interval: with small gold sets this matters more than the point estimate."""
    yt, yp = np.asarray(y_true), np.asarray(y_pred)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(yt), len(yt))
        vals.append(metric(yt[idx], yp[idx]))
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return [round(float(lo), 3), round(float(hi), 3)]
