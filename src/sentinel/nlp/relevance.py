"""Relevance gate (v0, transparent logistic score). Decides whether an item is worth scoring.

Weights are hand-set and fully inspectable; they are validated against a labelled sample in the next
step and replaced by a learned model if that does better. Every feature is stored for explainability.
"""
from __future__ import annotations

import math

from .lexicon import MARKET_RX, MONEY_RX, NEGATIVE_RX, distinct_hits, event_hits

THRESHOLD = 0.5


def source_prior(source_name: str, meta: dict) -> float:
    if source_name == "sec_edgar":
        return 6.0
    if source_name in ("rss:fed_press", "rss:ecb_press"):
        return 2.5
    if source_name.startswith("rss:"):
        return 0.8
    if source_name == "gdelt":
        return -0.8
    if source_name == "bluesky":
        return {"cashtag": 0.8, "name+finance": 0.5, "macro": 0.2}.get((meta.get("match") or {}).get("reason"), 0.0)
    if source_name == "reddit":
        return 0.3
    return 0.0


def extract_signals(text: str, source_name: str, meta: dict, n_companies: int) -> dict:
    ev = event_hits(text)
    return {
        "source_prior": source_prior(source_name, meta),
        "company_entities": n_companies,
        "event_categories": len(ev),
        "market_terms": len(distinct_hits(MARKET_RX, text)),
        "has_money": bool(MONEY_RX.search(text)),
        "negative_terms": len(distinct_hits(NEGATIVE_RX, text)),
    }


def relevance_probability(s: dict) -> float:
    logit = s["source_prior"]
    logit += 1.6 if s["company_entities"] else 0.0
    logit += {0: 0.0, 1: 1.0}.get(s["event_categories"], 1.5)
    logit += {0: 0.0, 1: 0.8}.get(s["market_terms"], 1.3)
    logit += 0.6 if s["has_money"] else 0.0
    logit -= 1.4 * min(s["negative_terms"], 2)
    return 1.0 / (1.0 + math.exp(-logit))