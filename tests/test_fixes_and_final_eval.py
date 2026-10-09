"""Regression tests for defects seen on live signals (2026-10-08), plus the one-shot test evaluation."""
from sentinel.ml.final_eval import evaluate_test, format_test_report
from sentinel.ml.serving import Scorer, occlusion_weights
from sentinel.ml.train_final import VERSION
from sentinel.nlp.entities import link_entities, strip_urls
from sentinel.nlp.features import PIPELINE_VERSION


def test_url_text_does_not_create_company_entities():
    # real post: the 'share.google' link was linked to Alphabet / GOOGL
    t = ("When the blame President Biden, show them this. Without tariffs, inflation on goods would have fallen: "
         "New York Fed share.google/uC2uzCPgvFc")
    assert not [e for e in link_entities(t) if e["ticker"] == "GOOGL"]
    assert "share.google" not in strip_urls(t) and "New York Fed" in strip_urls(t)
    assert [e["ticker"] for e in link_entities("Google unveils a new AI chip, shares jump")] == ["GOOGL"]
    assert not link_entities("Read more at https://www.reuters.com/markets/apple-shares-fall and www.amazon.com/x")


def test_explanation_uses_log_odds_so_saturated_scores_still_attribute():
    def saturated(texts):      # P(negative) ~ 0.96-0.97 either way: the probability difference barely moves
        return [{"positive": 0.004, "negative": 0.97, "neutral": 0.026} if "fell" in t
                else {"positive": 0.008, "negative": 0.96, "neutral": 0.032} for t in texts]
    scorer = Scorer({}, None, saturated)
    assert scorer.explain("Nasdaq fell sharply on Tuesday") == [{"token": "fell", "weight": -1.0}]


def test_stopwords_and_normalization():
    score = lambda ts: [("rally" in t.lower()) * 0.4 + ("profits" in t) * 0.2 + ("of" in t) * 0.1 for t in ts]
    raw = occlusion_weights("Rally of profits to come", score)
    assert [o["token"] for o in raw] == ["Rally", "profits"]          # 'of' and 'to' are skipped
    norm = occlusion_weights("Rally of profits to come", score, normalize=True)
    assert norm[0]["weight"] == 1.0 and 0 < norm[1]["weight"] < 1.0


def test_artifact_version_changes_with_the_nlp_pipeline():
    assert PIPELINE_VERSION in VERSION


def _rows():
    rows, rel_p, ev, sp = [], [], [], []
    for i in range(40):
        rel = i % 2 == 0
        s = (-1, 0, 1)[i % 3]
        rows.append({"id": str(i), "source_name": "gdelt", "title": f"t{i}", "gold_relevant": rel,
                     "gold_event": "Geopolitical" if rel else "None", "gold_sentiment": s if rel else None,
                     "rule_relevant": i % 4 == 0 or i % 5 == 0, "rule_score": 0.9 if i % 4 == 0 else 0.4,
                     "rule_event": "Geopolitical" if i % 6 == 0 else None})
        rel_p.append(0.95 if rel else 0.05)
        ev.append({"Geopolitical": 0.9, "None": 0.05, "Other": 0.05})
        sp.append({"positive": 0.8, "negative": 0.1, "neutral": 0.1} if s == 1 else
                  {"positive": 0.1, "negative": 0.8, "neutral": 0.1} if s == -1 else
                  {"positive": 0.1, "negative": 0.1, "neutral": 0.8})
    return rows, rel_p, ev, sp


def test_evaluate_test_scores_learned_and_rules_separately():
    rows, rel_p, ev, sp = _rows()
    res = evaluate_test(rows, rel_p, ev, sp)
    assert res["n"] == 40 and res["n_gold_relevant"] == 20
    assert res["relevance"]["learned"]["f1"] == 1.0 and res["relevance"]["learned"]["auc"] == 1.0
    assert res["relevance"]["rules"]["f1"] < 1.0
    assert res["event"]["n"] == 20 and res["event"]["learned"]["accuracy"] == 1.0
    assert res["event"]["rules"]["accuracy"] < res["event"]["learned"]["accuracy"]
    assert res["sentiment"]["accuracy"] == 1.0 and res["sentiment"]["spearman_score_vs_gold"] > 0.9
    text = format_test_report(res, 1)
    assert "HELD-OUT TEST" in text and "run #1" in text and "relevance learned" in text


def test_evaluate_test_handles_tiny_sentiment_set():
    rows, rel_p, ev, sp = _rows()
    for r in rows:
        r["gold_sentiment"] = None
    assert "skipped" in evaluate_test(rows, rel_p, ev, sp)["sentiment"]
