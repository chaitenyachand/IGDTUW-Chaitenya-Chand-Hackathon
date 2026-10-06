"""Compute all v0 NLP features for one stored document."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .clean import clean_title
from .entities import link_entities
from .lexicon import EDGAR_ITEM_EVENT, event_hits
from .relevance import THRESHOLD, extract_signals, relevance_probability

PIPELINE_VERSION = "nlp-0.1.2-rules"


@dataclass
class DocFeatures:
    document_id: str
    clean_title: str
    entities: list
    relevance: float
    relevant: bool
    weak_event: str | None
    weak_event_scores: dict
    features: dict = field(default_factory=dict)
    pipeline_version: str = PIPELINE_VERSION


def _meta(row) -> dict:
    m = row["meta"]
    return json.loads(m) if isinstance(m, str) else (m or {})


def compute_features(row) -> DocFeatures:
    meta = _meta(row)
    title = clean_title(row["title"] or "", row["url"])
    text = f"{title}. {row['text']}" if row["text"] and row["text"] != row["title"] else title
    entities = link_entities(text, row["source_name"], meta)
    companies = [e for e in entities if e["kind"] == "company"]
    n_universe = sum(1 for e in companies if e["name"] is not None)
    n_external = len(companies) - n_universe

    signals = extract_signals(text, row["source_name"], meta, n_universe, n_external)
    p = relevance_probability(signals)

    ev = event_hits(text)
    weak = None
    if row["source_name"] == "sec_edgar":
        weak = next((EDGAR_ITEM_EVENT[i] for i in meta.get("items", []) if i in EDGAR_ITEM_EVENT), None)
    if weak is None and ev:
        weak = max(ev, key=lambda k: len(ev[k]))
    return DocFeatures(row["id"], title, entities, round(p, 4), p >= THRESHOLD, weak,
                       {k: len(v) for k, v in ev.items()}, signals)