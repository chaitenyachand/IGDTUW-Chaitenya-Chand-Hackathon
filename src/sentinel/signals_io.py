"""Mapping between the API shape of a signal (camelCase, per the frontend contract) and the database row."""
from __future__ import annotations

import json
from datetime import datetime

INSERT_SIGNAL = """
INSERT INTO signals (id, document_id, ts, mode, entity, ticker, entities, headline, text, source_type, source_name,
                     url, sentiment, sentiment_probs, event_type, secondary_event_type, impact, book_impact,
                     confidence, half_life_days, integrity, explanation, affected_holdings, embedding, model_version)
VALUES ($1,$1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,$11,$12,$13::jsonb,$14,$15,$16,$17,$18,$19,$20::jsonb,$21::jsonb,
        $22::jsonb,$23,$24)
ON CONFLICT (id) DO UPDATE SET entity=EXCLUDED.entity, ticker=EXCLUDED.ticker, entities=EXCLUDED.entities,
  sentiment=EXCLUDED.sentiment, sentiment_probs=EXCLUDED.sentiment_probs, event_type=EXCLUDED.event_type,
  secondary_event_type=EXCLUDED.secondary_event_type, confidence=EXCLUDED.confidence, integrity=EXCLUDED.integrity,
  explanation=EXCLUDED.explanation, embedding=EXCLUDED.embedding, model_version=EXCLUDED.model_version,
  scored_at=now()
"""


def api_to_params(sig: dict, embedding) -> tuple:
    return (
        sig["id"], datetime.fromisoformat(sig["ts"]), sig["mode"], sig["entity"], sig["ticker"],
        json.dumps(sig["entities"]), sig["headline"], sig["text"], sig["sourceType"], sig["sourceName"], sig["url"],
        sig["sentiment"], json.dumps(sig["sentimentProbs"]), sig["eventType"], sig["secondaryEventType"],
        sig["impact"], sig["bookImpact"], sig["confidence"], sig["halfLifeDays"],
        json.dumps(sig["integrity"]), json.dumps(sig["explanation"]), json.dumps(sig["affectedHoldings"]),
        [round(float(x), 5) for x in embedding], sig["modelVersion"],
    )


def _j(v):
    return json.loads(v) if isinstance(v, str) else v


def row_to_api(r) -> dict:
    return {
        "id": r["id"], "ts": r["ts"].isoformat(), "mode": r["mode"], "entity": r["entity"], "ticker": r["ticker"],
        "headline": r["headline"], "text": r["text"], "sourceType": r["source_type"], "sourceName": r["source_name"],
        "url": r["url"], "sentiment": r["sentiment"], "eventType": r["event_type"],
        "secondaryEventType": r["secondary_event_type"], "impact": r["impact"], "bookImpact": r["book_impact"],
        "confidence": r["confidence"], "halfLifeDays": r["half_life_days"], "integrity": _j(r["integrity"]),
        "explanation": _j(r["explanation"]), "affectedHoldings": _j(r["affected_holdings"]),
    }
