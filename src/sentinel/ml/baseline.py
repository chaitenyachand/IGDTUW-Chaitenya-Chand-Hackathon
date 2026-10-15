"""Learned classifiers evaluated against the gold labels (relevance, event type, sentiment).

Every number is an out-of-fold cross-validation estimate on the hand-checked gold set, reported with a
bootstrap interval, next to the rule baseline where one exists.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.pipeline import Pipeline

from ..tools.evaluation import binary_metrics
from .cv import bootstrap_ci, can_cv, cv_predict, merge_rare, report, take

MIN_EVENT_COUNT = 6


def make_tfidf_lr():
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, strip_accents="unicode")),
        ("lr", LogisticRegression(max_iter=2000, C=3.0, class_weight="balanced")),
    ])


def make_dense_lr():
    return LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")


def _f1(a, b):
    return f1_score(a, b, zero_division=0)


def _macro(a, b):
    return f1_score(a, b, average="macro", zero_division=0)


def _relevance(rows, X, make_model, seed):
    y = [int(bool(r["gold_relevant"])) for r in rows]
    if not can_cv(y):
        return {"skipped": "need at least 2 examples of each class"}
    pred, proba, _ = cv_predict(make_model(), X, y, seed)
    learned = binary_metrics((p == 1, g == 1) for p, g in zip(pred, y))
    learned["auc"] = float(roc_auc_score(y, proba[:, 1]))
    learned["f1_ci95"] = bootstrap_ci(y, pred, _f1, seed=seed)
    rule_pred = [int(bool(r["rule_relevant"])) for r in rows]
    rules = binary_metrics((p == 1, g == 1) for p, g in zip(rule_pred, y))
    rules["f1_ci95"] = bootstrap_ci(y, rule_pred, _f1, seed=seed)
    return {"n": len(y), "learned": learned, "rules": rules}


def _event(rows, X, make_model, seed):
    idx = [i for i, r in enumerate(rows) if r["gold_relevant"]]
    y_raw = [rows[i]["gold_event"] for i in idx]
    y = merge_rare(y_raw, MIN_EVENT_COUNT)
    if not can_cv(y):
        return {"skipped": "need at least 2 examples of each class"}
    kept = set(y) - {"Other"}
    labels = sorted(set(y))
    pred, _, _ = cv_predict(make_model(), take(X, idx), y, seed)
    rule_pred = [(rows[i]["rule_event"] or "None") for i in idx]
    rule_pred = [lab if lab in kept else "Other" for lab in rule_pred]
    learned, rules = report(y, pred, labels), report(y, rule_pred, labels)
    learned["macro_f1_ci95"] = bootstrap_ci(y, pred, _macro, seed=seed)
    rules["macro_f1_ci95"] = bootstrap_ci(y, rule_pred, _macro, seed=seed)
    return {"n": len(y), "classes": labels, "merged_into_other": sorted(set(y_raw) - kept),
            "learned": learned, "rules": rules}


def _sentiment(rows, X, make_model, seed):
    idx = [i for i, r in enumerate(rows) if r["gold_relevant"] and r["gold_sentiment"] is not None]
    y = [int(rows[i]["gold_sentiment"]) for i in idx]
    if not can_cv(y):
        return {"skipped": "need at least 2 examples of each class"}
    pred, _, _ = cv_predict(make_model(), take(X, idx), y, seed)
    learned = report(y, pred, [-1, 0, 1])
    learned["macro_f1_ci95"] = bootstrap_ci(y, pred, _macro, seed=seed)
    top = Counter(y).most_common(1)[0]
    return {"n": len(y), "learned": learned, "majority_class_baseline_accuracy": top[1] / len(y)}


def run_tasks(rows, X, make_model, seed: int = 7, name: str = "model") -> dict:
    return {"name": name, "seed": seed, "n_gold": len(rows),
            "relevance": _relevance(rows, X, make_model, seed),
            "event": _event(rows, X, make_model, seed),
            "sentiment": _sentiment(rows, X, make_model, seed)}


def format_report(res: dict) -> str:
    out = [f"== {res['name']}  (gold labels: {res['n_gold']}, 5-fold cross-validation, seed {res['seed']}) =="]
    r = res["relevance"]
    if "skipped" in r:
        out.append(f"relevance: skipped ({r['skipped']})")
    else:
        for k in ("rules", "learned"):
            m = r[k]
            auc = f" auc={m['auc']:.2f}" if "auc" in m else ""
            out.append(f"relevance {k:<8} precision={m['precision']:.2f} recall={m['recall']:.2f} "
                       f"f1={m['f1']:.2f} (95% CI {m['f1_ci95'][0]}-{m['f1_ci95'][1]}){auc}")
    e = res["event"]
    if "skipped" in e:
        out.append(f"event: skipped ({e['skipped']})")
    else:
        out.append(f"event (relevant items, n={e['n']}, rare classes merged into Other: {e['merged_into_other']})")
        for k in ("rules", "learned"):
            m = e[k]
            out.append(f"  {k:<8} accuracy={m['accuracy']:.2f} macro_f1={m['macro_f1']:.2f} "
                       f"(95% CI {m['macro_f1_ci95'][0]}-{m['macro_f1_ci95'][1]})")
        for c in e["classes"]:
            lc, rc = e["learned"]["per_class"][c], e["rules"]["per_class"][c]
            out.append(f"    {c:<20} n={lc['support']:<3} learned f1={lc['f1']:.2f}   rules f1={rc['f1']:.2f}")
    s = res["sentiment"]
    if "skipped" in s:
        out.append(f"sentiment: skipped ({s['skipped']})")
    else:
        m = s["learned"]
        out.append(f"sentiment (relevant items, n={s['n']})  learned accuracy={m['accuracy']:.2f} "
                   f"macro_f1={m['macro_f1']:.2f} (95% CI {m['macro_f1_ci95'][0]}-{m['macro_f1_ci95'][1]})  "
                   f"majority-class baseline accuracy={s['majority_class_baseline_accuracy']:.2f}")
    return "\n".join(out)


def save_json(path: str, obj) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))
