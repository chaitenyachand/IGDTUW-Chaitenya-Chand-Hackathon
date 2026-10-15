import random

import numpy as np
import pytest

from sentinel.ml.baseline import format_report, make_dense_lr, make_tfidf_lr, run_tasks
from sentinel.ml.cv import bootstrap_ci, can_cv, merge_rare, n_splits_for, take
from sentinel.ml.data import model_text, source_group
from sentinel.ml.transformers_eval import eval_finbert, finbert_class, finbert_score, with_source_onehot
from sentinel.taxonomy import EVENT_TYPES
from sentinel.nlp.lexicon import EVENT_PATTERNS


def synthetic_rows(seed=3):
    """Deterministic toy gold set: finance headlines vs lifestyle, with event and sentiment signals."""
    rng = random.Random(seed)
    rel = {
        "Geopolitical": ["sanctions imposed on", "missile strike raises tension near", "ceasefire talks stall around"],
        "Macroeconomic": ["central bank holds interest rates as inflation", "jobs report shows unemployment", "treasury yields move on gdp"],
        "Regulatory": ["regulator opens antitrust probe into", "court ruling forces compliance changes at", "new legislation targets"],
        "Cyber": ["ransomware attack hits", "data breach exposes"],
    }
    tails = {1: ["rallies strongly", "beats expectations and gains"], -1: ["slumps sharply", "warns of losses and falls"],
             0: ["steady on the day", "unchanged this week"]}
    irr = ["local football festival results announced", "celebrity wedding recipe goes viral",
           "weather forecast rain over the weekend", "library hosts art showcase fundraiser"]
    rows = []
    for ev, heads in rel.items():
        for k in range(14 if ev != "Cyber" else 2):
            s = rng.choice([-1, 0, 1])
            rows.append({"id": f"r{len(rows)}", "source_name": rng.choice(["gdelt", "rss:cnbc_top", "bluesky"]),
                         "title": f"{rng.choice(heads)} acme {rng.choice(tails[s])} {k}",
                         "gold_relevant": True, "gold_event": ev, "gold_sentiment": s,
                         "rule_relevant": rng.random() < 0.8, "rule_event": ev if rng.random() < 0.5 else None})
    for k in range(40):
        rows.append({"id": f"i{k}", "source_name": rng.choice(["gdelt", "bluesky"]),
                     "title": f"{rng.choice(irr)} edition {k}", "gold_relevant": False, "gold_event": "None",
                     "gold_sentiment": None, "rule_relevant": rng.random() < 0.2, "rule_event": None})
    return rows


def test_helpers():
    assert merge_rare(["a"] * 6 + ["b"] * 2, 6) == ["a"] * 6 + ["Other"] * 2
    assert can_cv([0, 0, 1, 1]) and not can_cv([0, 0, 0, 1]) and not can_cv([1, 1])
    assert n_splits_for([0] * 3 + [1] * 9) == 3 and n_splits_for([0] * 20 + [1] * 20) == 5
    assert take(["a", "b", "c"], [2, 0]) == ["c", "a"]
    assert (take(np.arange(6).reshape(3, 2), [1]) == np.array([[2, 3]])).all()
    assert source_group("rss:cnbc_top") == "rss"
    assert model_text({"source_name": "rss:x", "title": "Hello"}) == "__src_rss Hello"


def test_bootstrap_ci_is_deterministic_and_sane():
    y = [1] * 30 + [0] * 30
    p = [1] * 27 + [0] * 3 + [0] * 28 + [1] * 2
    acc = lambda a, b: float((a == b).mean())
    lo, hi = bootstrap_ci(y, p, acc)
    assert [lo, hi] == bootstrap_ci(y, p, acc) and 0.8 < lo < 0.92 < hi <= 1.0


@pytest.mark.parametrize("make,as_dense", [(make_tfidf_lr, False), (make_dense_lr, True)])
def test_run_tasks_learns_signal_on_toy_data(make, as_dense):
    rows = synthetic_rows()
    if as_dense:
        from sklearn.feature_extraction.text import TfidfVectorizer
        X = TfidfVectorizer().fit_transform([model_text(r) for r in rows]).toarray()
    else:
        X = [model_text(r) for r in rows]
    res = run_tasks(rows, X, make, name="toy")
    assert res["relevance"]["learned"]["f1"] > 0.9
    assert "Cyber" in res["event"]["merged_into_other"] and "Other" in res["event"]["classes"]
    assert res["event"]["learned"]["macro_f1"] > 0.6
    assert res["sentiment"]["learned"]["accuracy"] > res["sentiment"]["majority_class_baseline_accuracy"]
    text = format_report(res)
    assert "relevance rules" in text and "relevance learned" in text and "sentiment" in text


def test_tiny_gold_set_is_skipped_not_crashed():
    rows = synthetic_rows()[:4]
    res = run_tasks(rows, [model_text(r) for r in rows], make_tfidf_lr)
    assert "skipped" in res["relevance"] or "learned" in res["relevance"]
    format_report(res)


def test_finbert_helpers_and_eval_with_fake_model():
    assert finbert_class({"positive": 0.7, "negative": 0.1, "neutral": 0.2}) == 1
    assert finbert_class({"positive": 0.1, "negative": 0.8, "neutral": 0.1}) == -1
    assert finbert_class({"positive": 0.2, "negative": 0.1, "neutral": 0.7}) == 0
    assert abs(finbert_score({"positive": 0.7, "negative": 0.1, "neutral": 0.2}) - 0.6) < 1e-9
    rows = [r for r in synthetic_rows() if r["gold_relevant"]]

    def fake(texts):  # a 'model' that reads the toy sentiment words
        out = []
        for t in texts:
            if any(w in t for w in ("rallies", "gains")):
                out.append({"positive": .8, "negative": .1, "neutral": .1})
            elif any(w in t for w in ("slumps", "falls")):
                out.append({"positive": .1, "negative": .8, "neutral": .1})
            else:
                out.append({"positive": .1, "negative": .1, "neutral": .8})
        return out

    res = eval_finbert(rows, probs_fn=fake)
    assert res["accuracy"] == 1.0 and res["spearman_score_vs_gold"] > 0.9
    assert "skipped" in eval_finbert(rows[:5], probs_fn=fake)


def test_source_onehot_shape():
    rows = synthetic_rows()[:10]
    out = with_source_onehot(np.zeros((10, 4)), rows)
    assert out.shape[0] == 10 and out.shape[1] == 4 + len({source_group(r["source_name"]) for r in rows})


def test_taxonomy_matches_lexicon_and_edgar_labels():
    from sentinel.nlp.lexicon import EDGAR_ITEM_EVENT
    assert set(EVENT_PATTERNS) == set(EVENT_TYPES)
    assert set(EDGAR_ITEM_EVENT.values()) <= set(EVENT_TYPES)
