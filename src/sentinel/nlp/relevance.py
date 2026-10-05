"""Relevance gate (v0, transparent logistic score). Decides whether an item is worth scoring.

Weights are hand-set and fully inspectable; they are validated against a labelled sample in the next
step and replaced by a learned model if that does better. Every feature is stored for explainability.
"""
from __future__ import annotations

import math

from .filters import is_adult, is_automated
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
        # macro-only chatter (no cashtag, no company) is mostly opinion: it needs strong evidence or corroboration
        return {"cashtag": 0.4, "name+finance": 0.3, "macro": -2.0}.get((meta.get("match") or {}).get("reason"), 0.0)
    if source_name == "reddit":
        return 0.3
    return 0.0


def extract_signals(text: str, source_name: str, meta: dict, n_universe: int, n_external: int) -> dict:
    ev = event_hits(text)
    return {
        "source_prior": source_prior(source_name, meta),
        "universe_entities": n_universe,
        "external_cashtags": n_external,
        "event_categories": len(ev),
        "market_terms": len(distinct_hits(MARKET_RX, text)),
        "has_money": bool(MONEY_RX.search(text)),
        "negative_terms": len(distinct_hits(NEGATIVE_RX, text)),
        "automated": is_automated(text),
        "adult": is_adult(text),
    }


def relevance_probability(s: dict) -> float:
    if s["adult"]:
        return 0.0
    logit = s["source_prior"]
    logit += 1.6 if s["universe_entities"] else (0.6 if s["external_cashtags"] else 0.0)
    logit += {0: 0.0, 1: 1.0}.get(s["event_categories"], 1.5)
    logit += {0: 0.0, 1: 0.8}.get(s["market_terms"], 1.3)
    logit += 0.6 if s["has_money"] else 0.0
    logit -= 1.4 * min(s["negative_terms"], 2)
    logit -= 2.5 if s["automated"] else 0.0
    return 1.0 / (1.0 + math.exp(-logit))
