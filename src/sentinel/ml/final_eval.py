"""One-shot evaluation of the frozen pipeline on the random held-out test split (pure function, tested without models)."""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.metrics import f1_score, roc_auc_score

from ..taxonomy import api_event
from ..tools.evaluation import binary_metrics
from .cv import bootstrap_ci, report
from .serving import decide_event
from .transformers_eval import finbert_class, finbert_score


def _f1(a, b):
    return f1_score(a, b, zero_division=0)


def _macro(a, b):
    return f1_score(a, b, average="macro", zero_division=0)


def _binary(y, pred):
    m = binary_metrics((p == 1, g == 1) for p, g in zip(pred, y))
    m["f1_ci95"] = bootstrap_ci(y, pred, _f1)
    return m


def evaluate_test(rows: list, rel_p: list, ev_proba: list, sent_probs: list, threshold: float = 0.5) -> dict:
    y = [int(bool(r["gold_relevant"])) for r in rows]
    learned = _binary(y, [int(p >= threshold) for p in rel_p])
    rules = _binary(y, [int(bool(r["rule_relevant"])) for r in rows])
    if len(set(y)) == 2:
        learned["auc"] = float(roc_auc_score(y, rel_p))
        rules["auc"] = float(roc_auc_score(y, [r["rule_score"] for r in rows]))
    out = {"n": len(rows), "n_gold_relevant": sum(y), "threshold": threshold,
           "relevance": {"learned": learned, "rules": rules}}

    # event type at the level the API serves (8-K item overrides, 'Other' falls back to rules, 'None' -> Market Commentary)
    idx = [i for i, r in enumerate(rows) if r["gold_relevant"]]
    gold = [api_event(rows[i]["gold_event"]) for i in idx]
    pred = [decide_event(rows[i]["source_name"], rows[i]["rule_event"], ev_proba[i])[0] for i in idx]
    rule = [api_event(rows[i]["rule_event"]) for i in idx]
    labels = sorted(set(gold) | set(pred) | set(rule))
    ev_l, ev_r = report(gold, pred, labels), report(gold, rule, labels)
    ev_l["macro_f1_ci95"], ev_r["macro_f1_ci95"] = bootstrap_ci(gold, pred, _macro), bootstrap_ci(gold, rule, _macro)
    out["event"] = {"n": len(idx), "classes": labels, "learned": ev_l, "rules": ev_r}

    # sentiment: zero-shot FinBERT on gold-relevant items that carry a sentiment label
    sidx = [i for i in idx if rows[i]["gold_sentiment"] is not None]
    if len(sidx) >= 5:
        ys = [int(rows[i]["gold_sentiment"]) for i in sidx]
        ps = [finbert_class(sent_probs[i]) for i in sidx]
        sc = [finbert_score(sent_probs[i]) for i in sidx]
        rep = report(ys, ps, [-1, 0, 1])
        rep["macro_f1_ci95"] = bootstrap_ci(ys, ps, _macro)
        from scipy.stats import spearmanr
        rho = spearmanr(sc, ys).correlation
        rep["spearman_score_vs_gold"] = None if np.isnan(rho) else float(rho)
        rep["majority_class_baseline_accuracy"] = Counter(ys).most_common(1)[0][1] / len(ys)
        out["sentiment"] = rep
    else:
        out["sentiment"] = {"skipped": "fewer than 5 sentiment-labelled relevant items"}
    return out


def format_test_report(res: dict, run_number: int) -> str:
    r = res["relevance"]
    lines = [f"== HELD-OUT TEST (n={res['n']}, {res['n_gold_relevant']} gold-relevant; evaluation run #{run_number}) =="]
    for k in ("rules", "learned"):
        m = r[k]
        auc = f" auc={m['auc']:.2f}" if "auc" in m else ""
        lines.append(f"relevance {k:<8} precision={m['precision']:.2f} recall={m['recall']:.2f} f1={m['f1']:.2f} "
                     f"(95% CI {m['f1_ci95'][0]}-{m['f1_ci95'][1]}){auc}")
    e = res["event"]
    lines.append(f"event type (API level, n={e['n']} relevant items; wide intervals expected)")
    for k in ("rules", "learned"):
        m = e[k]
        lines.append(f"  {k:<8} accuracy={m['accuracy']:.2f} macro_f1={m['macro_f1']:.2f} "
                     f"(95% CI {m['macro_f1_ci95'][0]}-{m['macro_f1_ci95'][1]})")
    s = res["sentiment"]
    if "skipped" in s:
        lines.append(f"sentiment: skipped ({s['skipped']})")
    else:
        rho = s["spearman_score_vs_gold"]
        lines.append(f"sentiment FinBERT zero-shot (n={s['n']}) accuracy={s['accuracy']:.2f} macro_f1={s['macro_f1']:.2f} "
                     f"(95% CI {s['macro_f1_ci95'][0]}-{s['macro_f1_ci95'][1]}) spearman={'n/a' if rho is None else f'{rho:.2f}'} "
                     f"majority-class accuracy={s['majority_class_baseline_accuracy']:.2f}")
    return "\n".join(lines)
