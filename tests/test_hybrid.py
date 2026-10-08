import json

import numpy as np

from sentinel.ml.data import load_gold
from sentinel.ml.hybrid import build_matrices, finbert_features, rule_features, run_hybrid, summary, weak_event_onehot
from sentinel.taxonomy import EVENT_TYPES


def rows_with_signal(seed=5, n=120):
    rng = np.random.default_rng(seed)
    rows, emb, probs = [], [], []
    events = ["Geopolitical", "Macroeconomic", "Regulatory"]
    for i in range(n):
        rel = i % 2 == 0
        ev = events[(i // 2) % 3] if rel else "None"
        s = int(rng.choice([-1, 0, 1])) if rel else None
        feats = {"source_prior": 1.0, "universe_entities": int(rel), "event_categories": int(rel) * 2,
                 "event_hard": rel, "market_terms": int(rel) * 2, "has_money": rel, "negative_terms": int(not rel),
                 "automated": False}
        rows.append({"id": str(i), "source_name": "gdelt" if i % 3 else "rss:cnbc_top", "title": f"t{i}",
                     "features": feats, "gold_relevant": rel, "gold_event": ev, "gold_sentiment": s,
                     "rule_relevant": rng.random() < 0.7, "rule_event": ev if rng.random() < 0.6 else None})
        v = rng.normal(0, 0.3, 8)
        v[0] += 1.0 if rel else -1.0
        if rel:
            v[1 + events.index(ev)] += 1.0
        emb.append(v)
        p = {"positive": 0.1, "negative": 0.1, "neutral": 0.8}
        if s == 1:
            p = {"positive": 0.8, "negative": 0.1, "neutral": 0.1}
        elif s == -1:
            p = {"positive": 0.1, "negative": 0.8, "neutral": 0.1}
        probs.append(p)
    return rows, np.array(emb), probs


def test_feature_builders():
    r = {"features": {"source_prior": 6.0, "universe_entities": 5, "event_hard": True, "automated": True}}
    f = rule_features(r)
    assert len(f) == 9 and f[0] == 1.0 and f[1] == 1.0 and f[4] == 1.0 and f[8] == 1.0
    assert rule_features({"features": None}) == [0.0] * 9
    oh = weak_event_onehot([{"rule_event": "Cyber"}, {"rule_event": None}, {"rule_event": "unknown"}])
    assert oh.shape == (3, len(EVENT_TYPES) + 1) and (oh.sum(axis=1) == 1).all()
    assert finbert_features([{"positive": 0.7, "negative": 0.1, "neutral": 0.2}])[0].tolist() == [0.7, 0.1, 0.2, 0.6]


def test_matrices_and_hybrid_run():
    rows, emb, probs = rows_with_signal()
    X = build_matrices(rows, emb, probs)
    assert X["relevance"].shape[0] == len(rows) == X["event"].shape[0] == X["sentiment"].shape[0]
    res = run_hybrid(rows, emb, probs)
    assert res["relevance"]["learned"]["f1"] > 0.9
    assert res["event"]["learned"]["macro_f1"] > 0.7
    assert res["sentiment"]["learned"]["accuracy"] > res["sentiment"]["majority_class_baseline_accuracy"]
    text = summary({"hybrid": res}, {"macro_f1": 0.5, "accuracy": 0.6, "spearman_score_vs_gold": 0.4, "macro_f1_ci95": [0.4, 0.6]})
    assert "RELEVANCE" in text and "EVENT" in text and "SENTIMENT" in text and "FinBERT zero-shot" in text
    undefined = summary({"hybrid": res}, {"macro_f1": 0.5, "accuracy": 0.6, "spearman_score_vs_gold": None, "macro_f1_ci95": [0.4, 0.6]})
    assert "spearman=n/a" in undefined       # constant scores give an undefined correlation: must not crash


class FakePool:
    def __init__(self, rows):
        self.rows, self.args = rows, None

    async def fetch(self, sql, *args):
        self.args = args
        return self.rows


async def test_load_gold_parses_features_and_passes_split():
    row = {"id": "a", "source_name": "gdelt", "title": "t", "features": json.dumps({"market_terms": 2}),
           "rule_relevant": True, "rule_score": 0.9, "rule_event": None,
           "gold_relevant": True, "gold_event": "None", "gold_sentiment": None}
    pool = FakePool([row, {**row, "id": "b", "features": None}])
    out = await load_gold(pool, "test")
    assert pool.args == ("test",) and out[0]["features"] == {"market_terms": 2} and out[1]["features"] == {}
