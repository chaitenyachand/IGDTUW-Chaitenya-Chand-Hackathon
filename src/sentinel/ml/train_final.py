"""Train the frozen production models (relevance + event) on the dev gold labels and save one artifact."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .baseline import MIN_EVENT_COUNT, make_dense_lr
from .cv import merge_rare
from .hybrid import relevance_event_matrices
from .transformers_eval import EMBED_MODEL, FINBERT_MODEL

VERSION = "hybrid-v1+finbert-zeroshot"
ARTIFACT_PATH = "models/hybrid_v1.joblib"


def train_artifacts(rows: list, emb: np.ndarray) -> dict:
    X_rel, X_ev = relevance_event_matrices(rows, emb)
    y_rel = [int(bool(r["gold_relevant"])) for r in rows]
    rel_model = make_dense_lr().fit(X_rel, y_rel)
    idx = [i for i, r in enumerate(rows) if r["gold_relevant"]]
    y_raw = [rows[i]["gold_event"] for i in idx]
    y_ev = merge_rare(y_raw, MIN_EVENT_COUNT)
    ev_model = make_dense_lr().fit(X_ev[idx], y_ev)
    return {
        "version": VERSION, "relevance": rel_model, "event": ev_model, "threshold": 0.5,
        "embed_model": EMBED_MODEL, "sentiment_model": FINBERT_MODEL,
        "n_train": len(rows), "n_relevant": len(idx), "event_classes": [str(c) for c in ev_model.classes_],
        "merged_into_other": sorted(set(y_raw) - set(y_ev)),
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }


def save_artifacts(art: dict, path: str = ARTIFACT_PATH) -> None:
    import os
    import joblib
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    joblib.dump(art, path)


def load_artifacts(path: str = ARTIFACT_PATH) -> dict:
    import joblib
    return joblib.load(path)
