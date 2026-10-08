"""Hybrid models: pretrained embeddings + the transparent rule signals + calibrated FinBERT outputs.

The rules are not thrown away: their signals become features, so the learned model keeps what the rules
know (source reliability, entity matches, 8-K item labels) and adds what embeddings capture (meaning).
"""
from __future__ import annotations

import numpy as np

from ..taxonomy import EVENT_TYPES, NO_EVENT
from .baseline import _event, _relevance, _sentiment, make_dense_lr
from .transformers_eval import with_source_onehot

_EVENT_INDEX = {e: i for i, e in enumerate(EVENT_TYPES + [NO_EVENT])}


def rule_features(row: dict) -> list:
    f = row.get("features") or {}
    return [
        float(f.get("source_prior", 0.0)) / 6.0,
        min(f.get("universe_entities", 0), 2) / 2.0,
        min(f.get("external_cashtags", 0), 2) / 2.0,
        min(f.get("event_categories", 0), 3) / 3.0,
        float(bool(f.get("event_hard"))),
        min(f.get("market_terms", 0), 3) / 3.0,
        float(bool(f.get("has_money"))),
        min(f.get("negative_terms", 0), 2) / 2.0,
        float(bool(f.get("automated"))),
    ]


def weak_event_onehot(rows: list) -> np.ndarray:
    out = np.zeros((len(rows), len(_EVENT_INDEX)))
    for i, r in enumerate(rows):
        out[i, _EVENT_INDEX.get(r.get("rule_event") or NO_EVENT, _EVENT_INDEX[NO_EVENT])] = 1.0
    return out


def finbert_features(probs: list) -> np.ndarray:
    return np.array([[p.get("positive", 0.0), p.get("negative", 0.0), p.get("neutral", 0.0),
                      p.get("positive", 0.0) - p.get("negative", 0.0)] for p in probs])


def build_matrices(rows: list, emb: np.ndarray, probs: list) -> dict:
    base = with_source_onehot(emb, rows)
    rules = np.array([rule_features(r) for r in rows])
    return {
        "relevance": np.hstack([base, rules]),
        "event": np.hstack([base, weak_event_onehot(rows), rules[:, [3, 4]]]),
        "sentiment": finbert_features(probs),
    }


def run_hybrid(rows: list, emb: np.ndarray, probs: list, seed: int = 7,
               name: str = "hybrid (MiniLM + rule signals + calibrated FinBERT)") -> dict:
    X = build_matrices(rows, emb, probs)
    return {"name": name, "seed": seed, "n_gold": len(rows),
            "relevance": _relevance(rows, X["relevance"], make_dense_lr, seed),
            "event": _event(rows, X["event"], make_dense_lr, seed),
            "sentiment": _sentiment(rows, X["sentiment"], make_dense_lr, seed)}


def _fmt(m: dict, key: str) -> str:
    ci = m.get(f"{key}_ci95")
    return f"{m[key]:.2f}" + (f" ({ci[0]}-{ci[1]})" if ci else "")


def summary(named: dict, finbert: dict | None = None) -> str:
    """One comparison table. `named` maps a model name to a run_tasks/run_hybrid result."""
    lines = ["", "SUMMARY (cross-validated on the dev gold set; 95% bootstrap intervals in brackets)"]
    first = next(iter(named.values()))
    rel, ev = first["relevance"], first["event"]
    if "rules" in rel:
        lines.append(f"RELEVANCE F1   rules {_fmt(rel['rules'], 'f1')}")
    for n, r in named.items():
        if "learned" in r["relevance"]:
            m = r["relevance"]["learned"]
            lines.append(f"               {n:<46} {_fmt(m, 'f1')}  precision={m['precision']:.2f} recall={m['recall']:.2f} auc={m['auc']:.2f}")
    if "rules" in ev:
        lines.append(f"EVENT macro-F1 rules {_fmt(ev['rules'], 'macro_f1')}")
    for n, r in named.items():
        if "learned" in r["event"]:
            lines.append(f"               {n:<46} {_fmt(r['event']['learned'], 'macro_f1')}  accuracy={r['event']['learned']['accuracy']:.2f}")
    sent = first["sentiment"]
    if "majority_class_baseline_accuracy" in sent:
        lines.append(f"SENTIMENT      majority-class accuracy {sent['majority_class_baseline_accuracy']:.2f}")
    if finbert and "skipped" not in finbert:
        rho = finbert.get("spearman_score_vs_gold")
        rho_txt = "n/a" if rho is None else f"{rho:.2f}"
        lines.append(f"               {'FinBERT zero-shot (no training)':<46} {_fmt(finbert, 'macro_f1')}  accuracy={finbert['accuracy']:.2f} spearman={rho_txt}")
    for n, r in named.items():
        if "learned" in r["sentiment"]:
            lines.append(f"               {n:<46} {_fmt(r['sentiment']['learned'], 'macro_f1')}  accuracy={r['sentiment']['learned']['accuracy']:.2f}")
    return "\n".join(lines)
