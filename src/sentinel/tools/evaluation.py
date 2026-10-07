"""Small, dependency-free evaluation helpers."""
from __future__ import annotations


def binary_metrics(pairs) -> dict:
    """pairs: iterable of (predicted: bool, gold: bool)."""
    tp = fp = fn = tn = 0
    for pred, gold in pairs:
        if pred and gold:
            tp += 1
        elif pred and not gold:
            fp += 1
        elif not pred and gold:
            fn += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision,
            "recall": recall, "f1": f1, "accuracy": (tp + tn) / n if n else 0.0}


def fmt_metrics(name: str, m: dict) -> str:
    return (f"{name:<10} n={m['n']:<4} precision={m['precision']:.2f} recall={m['recall']:.2f} "
            f"f1={m['f1']:.2f} accuracy={m['accuracy']:.2f}  (tp={m['tp']} fp={m['fp']} fn={m['fn']} tn={m['tn']})")
