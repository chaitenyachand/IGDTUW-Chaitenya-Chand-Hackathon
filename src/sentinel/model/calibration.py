"""Calibration curve, expected calibration error and confusion matrix (pure functions)."""
from __future__ import annotations

import numpy as np


def reliability(confidence, correct, bins: int = 10) -> dict:
    """Confidence = the probability the model gave to its chosen answer; correct = whether that answer was right.
    ECE = sum over bins of (n_bin / n) x |accuracy_bin - mean_confidence_bin|."""
    c, ok = np.asarray(confidence, dtype=float), np.asarray(correct, dtype=float)
    if len(c) == 0:
        return {"n": 0, "ece": None, "curve": []}
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(c, edges[1:-1], right=False), 0, bins - 1)
    curve, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        if not m.any():
            continue
        acc, conf = float(ok[m].mean()), float(c[m].mean())
        ece += m.sum() / len(c) * abs(acc - conf)
        curve.append({"bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}", "meanConfidence": conf, "accuracy": acc, "n": int(m.sum())})
    return {"n": int(len(c)), "ece": float(ece), "curve": curve}


def confusion(y_true: list, y_pred: list, labels: list | None = None) -> dict:
    labels = labels or sorted(set(y_true) | set(y_pred), key=str)
    pos = {l: i for i, l in enumerate(labels)}
    m = np.zeros((len(labels), len(labels)), dtype=int)
    for t, p in zip(y_true, y_pred):
        m[pos[t], pos[p]] += 1
    return {"labels": [str(l) for l in labels], "matrix": m.tolist()}


def calibration_report(rows: list, rel_p: list, ev_proba: list, sent_probs: list, threshold: float = 0.5) -> dict:
    """Reliability curves, ECE and the event-type confusion matrix of the FROZEN pipeline on labelled rows.

    relevance : P(relevant) against how often those items really are relevant
    event     : top-1 probability against top-1 correctness, on gold-relevant items, at API level (as served)
    sentiment : top class probability against correctness, on gold-relevant items that carry a sentiment label
    Uses the exact predictions the held-out evaluation scores; it never changes the pipeline."""
    from ..ml.serving import decide_event
    from ..ml.transformers_eval import finbert_class
    from ..taxonomy import api_event
    y = [int(bool(r["gold_relevant"])) for r in rows]
    idx = [i for i, r in enumerate(rows) if r["gold_relevant"]]
    gold = [api_event(rows[i]["gold_event"]) for i in idx]
    pred = [decide_event(rows[i]["source_name"], rows[i]["rule_event"], ev_proba[i])[0] for i in idx]
    top = [max(ev_proba[i].values()) for i in idx]
    ev = reliability(top, [g == p for g, p in zip(gold, pred)])
    sidx = [i for i in idx if rows[i]["gold_sentiment"] is not None]
    sent = reliability([max(sent_probs[i].values()) for i in sidx],
                       [finbert_class(sent_probs[i]) == int(rows[i]["gold_sentiment"]) for i in sidx])
    return {"n": len(rows), "threshold": threshold,
            "relevance": _binary_reliability(rel_p, y),
            "event": {**ev, "confusion": confusion(gold, pred)},
            "sentiment": sent}


def _binary_reliability(p, y, bins: int = 10) -> dict:
    """ECE of a binary probability: sum over bins of (n_bin / n) x |observed frequency - mean predicted probability|."""
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    if len(p) == 0:
        return {"n": 0, "ece": None, "curve": []}
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    curve, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        if not m.any():
            continue
        obs, mean_p = float(y[m].mean()), float(p[m].mean())
        ece += m.sum() / len(p) * abs(obs - mean_p)
        curve.append({"bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}", "meanConfidence": mean_p, "accuracy": obs, "n": int(m.sum())})
    return {"n": int(len(p)), "ece": float(ece), "curve": curve}
