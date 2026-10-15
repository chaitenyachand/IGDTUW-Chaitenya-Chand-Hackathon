"""Pure-function tests: Adaptive Index weight constraints, Global Risk Index maths, audit hashing, impact kernel and event study."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from sentinel.audit.ledger import canonical_json, entry_hash
from sentinel.impact.event_study import classify_items, event_study, parse_filings, reaction_day
from sentinel.impact.kernel import expected_move, percentile_impact
from sentinel.index import weights as W
from sentinel.risk import index as R

N = 15
CFG = W.validate_config({}, N)
BENCH = np.random.default_rng(1).dirichlet(np.ones(N) * 4)
NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
TICKERS = [f"T{i}" for i in range(N)]


def sig(i, sent, age_days=0.5, integ=0.9, conf=0.9, **kw):
    return {"ts": NOW - timedelta(days=age_days), "ticker": TICKERS[i], "sentiment": sent, "confidence": conf,
            "halfLifeDays": None, "integrity": {"score": integ, "corroboratedBy": []}, **kw}


def test_zero_signal_reproduces_benchmark():
    z = W.zscores(np.zeros(N), CFG["zFloor"])
    assert np.allclose(W.tilt_target(BENCH, z, CFG), BENCH)


def test_tilt_respects_caps_sum_and_direction():
    sigs = [sig(0, -0.9), sig(1, 0.9), sig(2, 0.8), sig(3, -0.7)]
    s, _ = W.signal_scores(sigs, NOW, CFG, TICKERS)
    t = W.tilt_target(BENCH, W.zscores(s, CFG["zFloor"]), CFG)
    lo, hi = W.bounds(BENCH, CFG)
    assert t.sum() == pytest.approx(1.0) and (t >= lo - 1e-9).all() and (t <= hi + 1e-9).all()
    assert t[0] < BENCH[0] and t[1] > BENCH[1]


def test_constrain_deadband_and_turnover_cap():
    target = W.tilt_target(BENCH, np.linspace(-3, 3, N), {**CFG, "kappa": 1.0})
    new = W.constrain(BENCH, target, BENCH, CFG)
    assert new.sum() == pytest.approx(1.0) and W.turnover(BENCH, new) <= CFG["turnoverCap"] + 1e-9
    tiny = BENCH + np.r_[1e-4, -1e-4, np.zeros(N - 2)]
    assert np.array_equal(W.constrain(BENCH, tiny, BENCH, CFG), BENCH)          # all moves inside the deadband: no trade


def test_integrity_filter_and_point_in_time():
    sigs = [sig(0, -0.9, integ=0.2), sig(1, 0.5), {**sig(2, 0.9), "ts": NOW + timedelta(hours=1)}]
    s, cnt = W.signal_scores(sigs, NOW, CFG, TICKERS)
    assert s[0] == 0 and cnt[0] == 0 and s[1] > 0 and s[2] == 0                 # low integrity ignored, future ignored


def test_invalid_config_rejected():
    for bad in ({"mode": "x"}, {"minWeight": 0.2, "maxWeight": 0.1}, {"turnoverCap": 0}, {"minWeight": 0.1}):
        with pytest.raises(ValueError):
            W.validate_config(bad, N)


def test_percentile_rank_and_risk_frame():
    assert R.percentile_rank(5, [1, 2, 3]) == 100.0 and R.percentile_rank(0, [1, 2, 3]) == 0.0
    assert R.percentile_rank(2, [1, 2, 3]) == pytest.approx(50.0)
    rows = [{"id": "a", "ts": NOW - timedelta(hours=3), "entity": "X", "headline": "h", "impact": 8.0, "sentiment": -1.0, "confidence": 1.0, "integrity": 1.0},
            {"id": "b", "ts": NOW - timedelta(hours=1), "entity": "Y", "headline": "g", "impact": None, "sentiment": -1.0, "confidence": 1.0, "integrity": 1.0}]
    f = R.Frame(rows)
    raw, n, contrib, _ = f.raw_at(NOW, R.DEFAULT_CONFIG)
    assert n == 1 and raw == pytest.approx(8.0 * 0.5)                           # 3h old = one half-life; negativity 1; impact-less skipped
    r = R.value_at(f, NOW, R.DEFAULT_CONFIG)
    assert r["status"] == "insufficient_history" and r["value"] is None


def test_hash_chain_canonical_form():
    a = {"id": "1", "ts": "t", "payload": {"b": 1.0, "a": [2, 1]}}
    assert canonical_json(a) == canonical_json({"payload": {"a": [2, 1], "b": 1}, "ts": "t", "id": "1"})
    assert entry_hash(None, a) != entry_hash("x", a)


def test_kernel_reverts_to_ordinary_day_without_analogs():
    assert expected_move([], 0.01) == pytest.approx(0.01)
    assert expected_move([(0.9, 0.08)], 0.01) > 0.07
    assert expected_move([(0.2, 0.5)], 0.01) == pytest.approx(0.01)             # below the similarity floor: no weight
    assert percentile_impact(0.5, [0.1, 0.2, 0.3]) == 10.0 and percentile_impact(0.0, [0.1, 0.2, 0.3]) == 1.0


def test_filings_and_event_study():
    arr = {"form": ["8-K", "10-Q", "8-K"], "accessionNumber": ["a", "b", "c"], "items": ["1.05,9.01", "", "2.02"],
           "acceptanceDateTime": ["2024-05-02T21:30:00.000Z", "2024-05-03T10:00:00.000Z", "2024-05-06T13:00:00.000Z"]}
    rows = parse_filings(arr, "AAPL")
    assert [r["event_type"] for r in rows] == ["Cyber", "Earnings"] and classify_items(["8.01"]) == "Other 8-K"
    assert reaction_day(rows[0]["filed_at"]) == pd.Timestamp("2024-05-03")      # 5:30pm ET Thursday -> Friday session
    assert reaction_day(datetime(2024, 5, 4, 15, tzinfo=timezone.utc)) == pd.Timestamp("2024-05-05")    # Saturday -> Sunday; event_study rolls it to Monday's session
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2022-01-03", periods=500)
    m = pd.Series(rng.normal(0, 0.01, 500), index=idx)
    s = 1.2 * m + rng.normal(0, 0.002, 500)
    s.iloc[400] += 0.08                                                          # a planted +8% abnormal move
    res = event_study((1 + s).cumprod(), (1 + m).cumprod(), idx[400])
    assert res["car3"] == pytest.approx(0.08, abs=0.02) and res["beta"] == pytest.approx(1.2, abs=0.1)
    assert event_study((1 + s).cumprod(), (1 + m).cumprod(), idx[5]) is None     # not enough history before the event
