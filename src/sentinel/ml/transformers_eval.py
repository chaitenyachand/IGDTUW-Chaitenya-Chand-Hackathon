"""Pretrained-model evaluation (sentence embeddings + FinBERT sentiment). Needs the `ml` image.

All heavy imports are lazy so the rest of the package (and the tests) never need torch.
"""
from __future__ import annotations

import numpy as np

from .data import source_group

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
FINBERT_MODEL = "ProsusAI/finbert"
_CLASS = {"positive": 1, "negative": -1, "neutral": 0}


def embed(texts: list, model_name: str = EMBED_MODEL, batch: int = 64) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    return np.asarray(model.encode(texts, batch_size=batch, normalize_embeddings=True, show_progress_bar=False))


def with_source_onehot(emb: np.ndarray, rows: list) -> np.ndarray:
    groups = sorted({source_group(r["source_name"]) for r in rows})
    onehot = np.zeros((len(rows), len(groups)))
    for i, r in enumerate(rows):
        onehot[i, groups.index(source_group(r["source_name"]))] = 1.0
    return np.hstack([emb, onehot])


def finbert_probs(texts: list, model_name: str = FINBERT_MODEL, batch: int = 32) -> list:
    from transformers import pipeline
    clf = pipeline("text-classification", model=model_name, top_k=None, truncation=True, max_length=128)
    return [{d["label"].lower(): float(d["score"]) for d in out} for out in clf(texts, batch_size=batch)]


def finbert_score(p: dict) -> float:
    """Sentiment score in [-1, 1]: P(positive) - P(negative)."""
    return p.get("positive", 0.0) - p.get("negative", 0.0)


def finbert_class(p: dict) -> int:
    return _CLASS[max(p, key=p.get)]


def eval_finbert(rows: list, probs_fn=finbert_probs) -> dict:
    """Zero-shot FinBERT against gold sentiment on relevant items (no training on the gold set)."""
    from collections import Counter
    from scipy.stats import spearmanr
    from .cv import bootstrap_ci, report
    from sklearn.metrics import f1_score

    idx = [i for i, r in enumerate(rows) if r["gold_relevant"] and r["gold_sentiment"] is not None]
    if len(idx) < 10:
        return {"skipped": "fewer than 10 sentiment-labelled relevant items"}
    y = [int(rows[i]["gold_sentiment"]) for i in idx]
    probs = probs_fn([rows[i]["title"] for i in idx])
    pred = [finbert_class(p) for p in probs]
    scores = [finbert_score(p) for p in probs]
    rep = report(y, pred, [-1, 0, 1])
    rep["macro_f1_ci95"] = bootstrap_ci(y, pred, lambda a, b: f1_score(a, b, average="macro", zero_division=0))
    rho = spearmanr(scores, y)
    rep["spearman_score_vs_gold"] = None if np.isnan(rho.correlation) else float(rho.correlation)
    rep["majority_class_baseline_accuracy"] = Counter(y).most_common(1)[0][1] / len(y)
    rep["model"] = FINBERT_MODEL
    return rep


def make_embedder(model_name: str = EMBED_MODEL, batch: int = 64):
    """Load the sentence-embedding model once and return a function texts -> unit-norm vectors (for serving)."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)

    def run(texts: list) -> np.ndarray:
        return np.asarray(model.encode(texts, batch_size=batch, normalize_embeddings=True, show_progress_bar=False))
    return run


def make_finbert(model_name: str = FINBERT_MODEL, batch: int = 32):
    """Load FinBERT once and return a function texts -> [{'positive':..,'negative':..,'neutral':..}] (for serving)."""
    from transformers import pipeline
    clf = pipeline("text-classification", model=model_name, top_k=None, truncation=True, max_length=128)

    def run(texts: list) -> list:
        return [{d["label"].lower(): float(d["score"]) for d in out} for out in clf(texts, batch_size=batch)]
    return run
