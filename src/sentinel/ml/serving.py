"""Model serving logic: scoring, entity choice, event decision, integrity and explanations.

Everything here is pure or takes injected model functions, so it is unit-tested without torch.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np

from ..taxonomy import EVENT_TYPES, NO_EVENT, api_event
from .hybrid import relevance_event_matrices
from .transformers_eval import finbert_score

CORROBORATION_THRESHOLD = 0.80      # cosine similarity between headline embeddings
CREDIBILITY = {"sec_edgar": 1.0, "rss:fed_press": 1.0, "rss:ecb_press": 1.0, "gdelt": 0.5, "bluesky": 0.3, "reddit": 0.3}


def credibility(source_name: str) -> float:
    if source_name in CREDIBILITY:
        return CREDIBILITY[source_name]
    return 0.7 if source_name.startswith("rss:") else 0.4


def source_label(source_name: str, meta: dict) -> str:
    if source_name == "gdelt":
        return meta.get("domain") or "GDELT"
    if source_name.startswith("rss:"):
        return source_name[4:].replace("_", " ")
    return {"sec_edgar": "SEC EDGAR", "bluesky": "Bluesky", "reddit": "Reddit"}.get(source_name, source_name)


def choose_entity(entities: list):
    """Primary entity: an index company first, then a macro institution, then an external cashtag, else 'Market'."""
    companies = [e for e in entities if e.get("kind") == "company"]
    known = [e for e in companies if e.get("name")]
    if known:
        return known[0]["name"], known[0].get("ticker")
    institutions = [e for e in entities if e.get("kind") == "institution"]
    if institutions:
        return institutions[0]["name"], None
    if companies:
        return companies[0]["ticker"], companies[0]["ticker"]
    return "Market", None


def decide_event(source_name: str, rule_event, proba: dict):
    """Primary and secondary event type. 8-K item numbers override the model; 'Other' falls back to the rules."""
    ranked = sorted(proba, key=proba.get, reverse=True)
    if source_name == "sec_edgar" and rule_event in EVENT_TYPES:
        primary = rule_event
    else:
        primary = ranked[0] if ranked else NO_EVENT
        if primary == "Other":
            primary = rule_event if rule_event in EVENT_TYPES else NO_EVENT
    secondary = next((c for c in ranked if c not in (primary, "Other", NO_EVENT) and proba[c] >= 0.25), None)
    return api_event(primary), (api_event(secondary) if secondary else None)


def find_corroboration(emb: np.ndarray, own_source: str, recent: list, threshold: float = CORROBORATION_THRESHOLD) -> list:
    """Distinct other sources whose recent headlines are semantically close (embeddings are unit-norm)."""
    if not recent:
        return []
    sims = np.array([float(np.dot(emb, e)) for _, e in recent])
    return sorted({src for (src, _), s in zip(recent, sims) if s >= threshold and src != own_source})[:5]


def integrity(source_name: str, automated: bool, corroborators: list) -> dict:
    base = credibility(source_name)
    score = base + min(0.15 * len(corroborators), 0.45) - (0.4 if automated else 0.0)
    flags = []
    if automated:
        flags.append("bot_likely")
    if not corroborators and base < 0.9:
        flags.append("single_source")
    return {"score": round(max(0.0, min(1.0, score)), 3), "corroboratedBy": list(corroborators), "flags": flags}


def occlusion_weights(text: str, score_fn, top_k: int = 8, max_words: int = 40) -> list:
    """Leave-one-out attribution: how much the sentiment score changes when each word is removed."""
    words = text.split()[:max_words]
    if len(words) < 2:
        return []
    variants = [" ".join(words)] + [" ".join(words[:i] + words[i + 1:]) for i in range(len(words))]
    scores = score_fn(variants)
    base = scores[0]
    out = [{"token": w, "weight": round(float(base - s), 4)} for w, s in zip(words, scores[1:])]
    out = [o for o in out if o["weight"] != 0]
    return sorted(out, key=lambda o: -abs(o["weight"]))[:top_k]


def build_signal(row: dict, meta: dict, entities: list, rel_p: float, ev_proba: dict, sent_probs: dict,
                 explanation: list, corroborators: list, version: str) -> dict:
    """One signal in the API shape (camelCase, matching the frontend contract)."""
    entity, ticker = choose_entity(entities)
    primary, secondary = decide_event(row["source_name"], row.get("rule_event"), ev_proba)
    automated = bool((row.get("features") or {}).get("automated"))
    text = row.get("text") or row["title"]
    return {
        "id": row["id"], "ts": row["published_at"].isoformat(), "mode": row.get("mode", "live"),
        "entity": entity, "ticker": ticker, "headline": row["title"], "text": text[:600],
        "sourceType": row["source_type"], "sourceName": source_label(row["source_name"], meta), "url": row.get("url"),
        "sentiment": round(finbert_score(sent_probs), 4),
        "eventType": primary, "secondaryEventType": secondary,
        "impact": None, "bookImpact": None,
        "confidence": round(math.sqrt(max(rel_p, 0.0) * max(sent_probs.values())), 3),
        "halfLifeDays": None,
        "integrity": integrity(row["source_name"], automated, corroborators),
        "explanation": explanation, "affectedHoldings": [],
        "entities": entities, "sentimentProbs": sent_probs, "modelVersion": version,
    }


class Scorer:
    """Wraps the frozen artifacts and the two pretrained models (injected, so tests can fake them)."""

    def __init__(self, artifacts: dict, embed_fn, finbert_fn):
        self.art, self.embed_fn, self.finbert_fn = artifacts, embed_fn, finbert_fn

    @classmethod
    def from_disk(cls, path: str):
        from .train_final import load_artifacts
        from .transformers_eval import make_embedder, make_finbert
        art = load_artifacts(path)
        return cls(art, make_embedder(art["embed_model"]), make_finbert(art["sentiment_model"]))

    @property
    def version(self) -> str:
        return self.art["version"]

    @property
    def threshold(self) -> float:
        return self.art.get("threshold", 0.5)

    def score_relevance_event(self, rows: list):
        emb = self.embed_fn([r["title"] for r in rows])
        X_rel, X_ev = relevance_event_matrices(rows, emb)
        rel = self.art["relevance"]
        rel_p = rel.predict_proba(X_rel)[:, list(rel.classes_).index(1)]
        ev = self.art["event"]
        ev_proba = [dict(zip([str(c) for c in ev.classes_], map(float, p))) for p in ev.predict_proba(X_ev)]
        return emb, [float(p) for p in rel_p], ev_proba

    def sentiment(self, titles: list) -> list:
        return self.finbert_fn(titles) if titles else []

    def explain(self, title: str) -> list:
        return occlusion_weights(title, lambda ts: [finbert_score(p) for p in self.finbert_fn(ts)])
