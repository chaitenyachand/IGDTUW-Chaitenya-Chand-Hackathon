import hashlib
from datetime import datetime, timezone

import numpy as np

from sentinel.ml.serving import (Scorer, build_signal, choose_entity, decide_event, find_corroboration, integrity,
                                 occlusion_weights, source_label)
from sentinel.ml.train_final import train_artifacts
from sentinel.taxonomy import API_NO_EVENT, api_event


def fake_embed(texts):
    out = []
    for t in texts:
        v = np.zeros(32)
        for w in t.lower().split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 32] += 1
        out.append(v / (np.linalg.norm(v) or 1))
    return np.array(out)


def fake_finbert(texts):
    out = []
    for t in texts:
        pos, neg = ("rally" in t) * 0.6, ("slump" in t) * 0.6
        out.append({"positive": 0.2 + pos, "negative": 0.2 + neg, "neutral": 0.6 - pos - neg + 0.0})
    return out


REL = ["sanctions hit oil exports", "central bank raises interest rates", "regulator opens antitrust probe",
       "bank reports record profit and earnings", "merger agreed in billion deal", "inflation data surprises markets"]
IRR = ["local football festival results", "celebrity wedding recipe goes viral", "weather forecast rain weekend"]
EVENTS = ["Geopolitical", "Macroeconomic", "Regulatory", "Earnings", "Merger/Acquisition", "Macroeconomic"]


def gold_rows(n=120):
    rows = []
    for i in range(n):
        rel = i % 2 == 0
        k = (i // 2) % len(REL)
        title = (REL[k] if rel else IRR[i % len(IRR)]) + f" item {i} " + ("rally" if i % 3 == 0 else "slump" if i % 3 == 1 else "flat")
        rows.append({"id": f"g{i}", "source_name": ["gdelt", "rss:cnbc_top", "bluesky"][i % 3], "title": title,
                     "features": {"source_prior": 0.5, "event_categories": int(rel), "event_hard": rel,
                                  "market_terms": int(rel) * 2, "has_money": rel},
                     "rule_event": EVENTS[k] if rel and i % 4 == 0 else None,
                     "gold_relevant": rel, "gold_event": EVENTS[k] if rel else "None", "gold_sentiment": 0})
    return rows


def test_occlusion_weights_find_the_driving_word():
    score = lambda ts: [("rally" in t) * 0.5 - ("slump" in t) * 0.5 for t in ts]
    out = occlusion_weights("Stocks rally as banks report profits", score)
    assert out[0]["token"] == "rally" and out[0]["weight"] == 0.5 and all(o["weight"] != 0 for o in out)
    assert occlusion_weights("single", score) == []


def test_choose_entity_priority():
    ents = [{"kind": "institution", "name": "Federal Reserve", "ticker": None, "confidence": 0.8},
            {"kind": "company", "name": None, "ticker": "TSLA", "confidence": 0.6},
            {"kind": "company", "name": "Boeing Co.", "ticker": "BA", "confidence": 0.75}]
    assert choose_entity(ents) == ("Boeing Co.", "BA")
    assert choose_entity(ents[:2]) == ("Federal Reserve", None)
    assert choose_entity(ents[1:2]) == ("TSLA", "TSLA")
    assert choose_entity([]) == ("Market", None)


def test_decide_event_rules():
    assert decide_event("sec_edgar", "Cyber", {"Other": 0.9, "Earnings": 0.1}) == ("Cyber", None)
    assert decide_event("sec_edgar", "Cyber", {"Earnings": 0.9})[0] == "Cyber"          # 8-K item overrides
    assert decide_event("gdelt", "Credit Event", {"Other": 0.7, "Macroeconomic": 0.2})[0] == "Credit Event"   # Other -> rules
    assert decide_event("gdelt", None, {"Other": 0.7})[0] == API_NO_EVENT
    assert decide_event("gdelt", None, {"None": 0.8, "Regulatory": 0.3}) == (API_NO_EVENT, "Regulatory")
    assert decide_event("gdelt", None, {"Geopolitical": 0.6, "Macroeconomic": 0.1}) == ("Geopolitical", None)
    assert api_event("None") == api_event("Other") == API_NO_EVENT


def test_integrity_and_corroboration():
    assert integrity("sec_edgar", False, []) == {"score": 1.0, "corroboratedBy": [], "flags": []}
    i = integrity("bluesky", True, [])
    assert i["score"] == 0.0 and set(i["flags"]) == {"bot_likely", "single_source"}
    j = integrity("gdelt", False, ["Reuters", "BBC"])
    assert j["score"] == 0.8 and j["flags"] == []
    e = np.array([1.0, 0.0])
    recent = [("Reuters", np.array([0.95, 0.31])), ("Other", np.array([0.0, 1.0])), ("Self", np.array([1.0, 0.0]))]
    assert find_corroboration(e, "Self", recent) == ["Reuters"]
    assert find_corroboration(e, "Self", []) == []


def test_source_label():
    assert source_label("gdelt", {"domain": "reuters.com"}) == "reuters.com"
    assert source_label("rss:cnbc_top", {}) == "cnbc top" and source_label("sec_edgar", {}) == "SEC EDGAR"


def test_trained_scorer_is_batch_independent_and_builds_signals():
    rows = gold_rows()
    art = train_artifacts(rows, fake_embed([r["title"] for r in rows]))
    scorer = Scorer(art, fake_embed, fake_finbert)
    batch = rows[:12]
    _, p_batch, ev_batch = scorer.score_relevance_event(batch)
    _, p_single, ev_single = scorer.score_relevance_event([batch[5]])
    assert abs(p_batch[5] - p_single[0]) < 1e-9                 # same score alone or in a batch (fixed feature layout)
    assert all(abs(ev_batch[5][k] - ev_single[0][k]) < 1e-9 for k in ev_single[0])
    assert np.mean([(p >= 0.5) == r["gold_relevant"] for p, r in zip(p_batch, batch)]) > 0.9

    row = {**batch[0], "id": "abc", "source_type": "news", "url": "https://x.com/a", "mode": "live",
           "published_at": datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc), "text": batch[0]["title"]}
    sig = build_signal(row, {"domain": "x.com"}, [], p_batch[0], ev_batch[0], {"positive": 0.8, "negative": 0.1, "neutral": 0.1},
                       [], ["BBC"], scorer.version)
    assert sig["sentiment"] == 0.7 and sig["impact"] is None and sig["entity"] == "Market"
    assert 0 < sig["confidence"] <= 1 and sig["integrity"]["corroboratedBy"] == ["BBC"]
    assert {"id", "ts", "eventType", "integrity", "explanation", "affectedHoldings"} <= set(sig)
