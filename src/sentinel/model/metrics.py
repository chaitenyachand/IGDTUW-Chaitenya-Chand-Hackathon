"""Everything Model Lab shows, assembled from stored evaluation jobs and live pipeline tables. Nothing is invented:
a section is null (with a reason) until the job that produces it has run."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from . import drift

DATA = "data/models"
LIMITATIONS = [
    "Gold sets are small (hand-labelled, a few hundred headlines): metrics carry wide bootstrap intervals.",
    "Event labels come from weak supervision (8-K item numbers, rules) and a small gold set.",
    "X/Twitter live data is not used (no free read access); social coverage comes from Bluesky and Reddit.",
    "PRECEDENT analog depth is limited by ETF history: sample size n is always shown.",
    "The wholesale banking portfolio is synthetic by design; the rating migration matrix is a documented assumption.",
    "Outputs are risk analytics for demonstration, not investment advice.",
]


def _read(name: str):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


async def _last_run(pool, kind: str):
    r = await pool.fetchrow("SELECT ts, model_version, metrics FROM model_runs WHERE kind = $1 ORDER BY ts DESC LIMIT 1", kind)
    if r is None:
        return None
    m = json.loads(r["metrics"]) if isinstance(r["metrics"], str) else r["metrics"]
    return {"ranAt": r["ts"].isoformat(), "modelVersion": r["model_version"], **m}


async def latency(pool, hours: int = 24) -> dict:
    """Ingest -> publish latency of live signals, from real timestamps (documents.ingested_at -> signals.scored_at)."""
    rows = await pool.fetch(
        "SELECT EXTRACT(EPOCH FROM (s.scored_at - d.ingested_at)) AS sec FROM signals s JOIN documents d ON d.id = s.document_id "
        "WHERE s.mode = 'live' AND s.scored_at > now() - make_interval(hours => $1) AND s.scored_at >= d.ingested_at", hours)
    v = sorted(float(r["sec"]) for r in rows)
    if not v:
        return {"n": 0, "windowHours": hours}
    edges = [1, 5, 15, 60, 300]
    labels = ["<1s", "1-5s", "5-15s", "15-60s", "1-5m", ">5m"]
    lower_ms = [0] + [e * 1000 for e in edges]
    counts = [0] * len(labels)
    for x in v:
        counts[sum(x >= e for e in edges)] += 1
    q = lambda p: v[min(int(p * len(v)), len(v) - 1)]
    return {"n": len(v), "windowHours": hours, "p50Sec": q(0.5), "p95Sec": q(0.95), "maxSec": v[-1],
            "histogram": [{"bucket": l, "bucketMs": ms, "count": c} for l, ms, c in zip(labels, lower_ms, counts)]}


def model_card(art: dict | None, impact: dict | None) -> dict:
    return {
        "name": "SENTINEL NLP risk engine",
        "components": [
            {"task": "relevance gate + event type", "model": "logistic regression on MiniLM embeddings + rule features",
             "version": (art or {}).get("version"), "trainedAt": (art or {}).get("trained_at"),
             "nTrain": (art or {}).get("n_train"), "nRelevant": (art or {}).get("n_relevant"),
             "embedModel": (art or {}).get("embed_model")},
            {"task": "sentiment", "model": (art or {}).get("sentiment_model") or "ProsusAI/finbert", "mode": "zero-shot"},
            {"task": "impact (company filings)", "model": "gradient boosting on SEC 8-K abnormal returns",
             "version": (impact or {}).get("version"), "trainedAt": (impact or {}).get("trained_at"), "nEvents": (impact or {}).get("n_events")},
            {"task": "impact (macro / non-company events)", "model": "PRECEDENT kernel over historical analogs"},
        ],
        "trainingData": ["Hand-labelled headlines from GDELT, publisher RSS, SEC EDGAR, Bluesky and Reddit (gold_labels)",
                         "SEC EDGAR 8-K filing history of the index stocks, labelled with real abnormal returns",
                         "Curated public-record event library with real forward market paths (PRECEDENT)"],
        "knownLimitations": LIMITATIONS,
    }


async def collect(pool) -> dict:
    art = None
    path = os.environ.get("MODEL_PATH", "models/hybrid_v1.joblib")
    if os.path.exists(path):
        try:
            import joblib
            art = joblib.load(path)
        except Exception:
            art = None
    test = _read("metrics_test.json")
    dev = _read("metrics_transformers.json")
    base = _read("metrics_baseline.json")
    impact = await _last_run(pool, "impact") or _read("metrics_impact.json")
    counts = await pool.fetchrow(
        "SELECT (SELECT count(*) FROM documents) AS docs, (SELECT count(*) FROM signals) AS signals, "
        "(SELECT count(*) FROM corporate_events WHERE car3 IS NOT NULL) AS filings, (SELECT count(*) FROM event_library) AS library")
    return {
        "asOf": datetime.now(timezone.utc).isoformat(),
        "modelVersion": (art or {}).get("version"),
        "heldOutTest": test,                                  # one-shot evaluation on the random held-out split
        "devCrossValidation": {"hybrid": (dev or {}).get("hybrid"), "embeddings": (dev or {}).get("embeddings"),
                               "finbertZeroShot": (dev or {}).get("finbert_zero_shot"), "tfidfBaseline": base},
        "calibration": _read("metrics_calibration.json"),
        "impact": impact,
        "precedentValidation": await _last_run(pool, "precedent_validation"),
        "signalBacktest": await _last_run(pool, "signal_backtest"),
        "drift": await drift.current_drift(pool),
        "driftSeries": await drift.series(pool),
        "latency": await latency(pool),
        "pipeline": {"documents": counts["docs"], "signals": counts["signals"], "labelledFilings": counts["filings"],
                     "libraryEvents": counts["library"]},
        "modelCard": model_card(art, impact if isinstance(impact, dict) else None),
    }
