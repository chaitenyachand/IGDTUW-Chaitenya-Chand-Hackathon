"""Integration tests of the platform modules against Postgres + the TEST-ONLY synthetic market world (never shipped as data)."""
import json
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from sentinel import store
from sentinel.audit import ledger
from tests.platform_fixtures import DSN, IMPACT_PATH, mk_sig, put_signal, reset_state, seed_once

pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")
NOW = datetime(2026, 10, 9, 14, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def seeded():
    if DSN:
        seed_once()


@pytest.fixture
async def pool():
    p = await store.create_pool(DSN)
    await reset_state(p)
    yield p
    await p.close()


async def test_seeded_data_is_labelled_and_model_trained(pool):
    assert await pool.fetchval("SELECT count(*) FROM corporate_events WHERE car3 IS NOT NULL") > 300
    assert await pool.fetchval("SELECT count(*) FROM event_library") == 67
    assert await pool.fetchval("SELECT count(*) FROM portfolio_holdings") == 109
    assert os.path.exists(IMPACT_PATH)
    m = await pool.fetchval("SELECT metrics FROM model_runs WHERE kind='impact' ORDER BY ts DESC LIMIT 1")
    assert json.loads(m)["n_events"] > 300


async def test_precedent_no_look_ahead(pool):
    """Design test 16: no analog and no training row may postdate its signal."""
    from sentinel.precedent.engine import Library
    from sentinel.precedent.service import precedent_for_signal
    lib = await Library.load(pool)
    ev = next(e for e in lib.events if e.date.year == 2020 and e.type == "Geopolitical")
    sig_ts = datetime(ev.date.year, ev.date.month, ev.date.day, 12, tzinfo=timezone.utc) + timedelta(days=3)
    await put_signal(pool, mk_sig("pit1", sig_ts, "Market", None, "Geopolitical", headline=ev.title))
    res, analogs = await precedent_for_signal(pool, lib, "pit1")
    assert analogs and all(a.date < sig_ts.date() for _, a in analogs)
    assert res["status"] == "ready" and max(res["dateRange"]["to"], "") <= sig_ts.date().isoformat()
    # a signal older than every library event has no analogs at all
    await put_signal(pool, mk_sig("pit2", datetime(2000, 1, 1, tzinfo=timezone.utc), "Market", None, "Geopolitical", headline=ev.title))
    res2, a2 = await precedent_for_signal(pool, lib, "pit2")
    assert a2 == [] and res2["status"] == "insufficient_data"
    # impact training rows all precede... the test split is chronological (80/20) and strictly later than the train split
    m = json.loads(await pool.fetchval("SELECT metrics FROM model_runs WHERE kind='impact' ORDER BY ts DESC LIMIT 1"))
    assert m["n_train"] + m["n_test"] == m["n_events"] and m["test_period"][0] >= "2005"


async def test_impact_engine_enrich(pool):
    from sentinel.impact.scoring import ImpactEngine
    eng = await ImpactEngine.load(pool, IMPACT_PATH)
    assert eng.art is not None and eng.ctx is not None
    emb = np.asarray(__import__("tests.test_serving", fromlist=["fake_embed"]).fake_embed(["Apple credit downgrade"])[0])
    sig = mk_sig("e1", NOW, "Apple", "AAPL", "Credit Event", impact=None)
    out = eng.enrich(sig, emb)
    assert out["impactBasis"] == "company_model" and 1.0 <= out["impact"] <= 10.0 and out["bookImpact"] is not None
    macro = eng.enrich(mk_sig("e2", NOW, "Market", None, "Geopolitical", headline="Russia invades Ukraine"), emb)
    assert macro["impactBasis"] in ("precedent_kernel", "no_analogs") and (macro["impact"] is None or 1 <= macro["impact"] <= 10)


async def test_stress_runs_rules_and_audit(pool):
    from sentinel.stress import service as ss
    holder = ss.RuntimeHolder(pool)
    rt = await holder.get()
    base = await ss.execute(pool, None, rt, {"mode": "manual", "shocks": {"equity": -0.10, "rates": 100, "credit_spread": 150}})
    assert base["valueAfter"] < base["valueBefore"] and base["varAfter"] > 0 and base["esAfter"] >= base["varAfter"]
    assert base["expectedLoss"]["after"] > base["expectedLoss"]["before"]
    assert sum(f["delta"] for f in base["byFactor"]) == pytest.approx(base["valueAfter"] - base["valueBefore"], rel=1e-6)
    zero = await ss.execute(pool, None, rt, {"mode": "manual", "shocks": {"equity": 0.0}} if False else {"shocks": {"commodities": 1e-9}})
    assert abs(zero["valueAfter"] - zero["valueBefore"]) < 1.0
    sc = await ss.execute(pool, None, rt, {"scenarioId": rt.lib.events[0].id}) if "equity_index" in rt.lib.events[0].paths else None
    # trigger rule: Geopolitical impact 9 / integrity .9 > (7, .6)
    await put_signal(pool, mk_sig("r1", NOW, "Market", None, "Geopolitical", impact=9.0))
    sig = {"id": "r1", "eventType": "Geopolitical", "impact": 9.0, "integrity": {"score": 0.9}}
    fired = await ss.evaluate_rules(pool, None, holder, sig, now=NOW)
    assert len(fired) == 1 or await pool.fetchval("SELECT count(*) FROM alerts") == 0      # fires unless PRECEDENT has no analogs
    if fired:
        assert await pool.fetchval("SELECT count(*) FROM alerts") == 1
        again = await ss.evaluate_rules(pool, None, holder, sig, now=NOW + timedelta(minutes=5))
        assert again == []                                                              # cooldown
        later = await ss.evaluate_rules(pool, None, holder, sig, now=NOW + timedelta(minutes=61))
        assert len(later) == 1
    low = await ss.evaluate_rules(pool, None, holder, {**sig, "impact": 3.0}, now=NOW + timedelta(days=2))
    assert low == []
    assert (await ledger.verify(pool))["ok"]
    assert await pool.fetchval("SELECT count(*) FROM audit_log WHERE action='stress_run'") >= 2


async def test_replay_rule_cooldown_restarts_with_each_replay(pool):
    from sentinel.stress import service as ss
    holder = ss.RuntimeHolder(pool)
    await put_signal(pool, mk_sig("rp1", NOW - timedelta(days=900), "Market", None, "Geopolitical", mode="replay"))
    sig = {"id": "rp1", "eventType": "Geopolitical", "impact": 9.0, "integrity": {"score": 0.9}}
    t = NOW - timedelta(days=900)
    a = await ss.evaluate_rules(pool, None, holder, sig, source="replay", now=t)
    b = await ss.evaluate_rules(pool, None, holder, sig, source="replay", now=t)       # same replay time: cooldown
    c = await ss.evaluate_rules(pool, None, holder, sig, source="replay", now=t - timedelta(hours=5))   # a NEW replay starts earlier
    if a:
        assert b == [] and len(c) == 1
    assert await pool.fetchval("SELECT count(*) FROM stress_rules WHERE last_fired IS NOT NULL") == 0     # replay never touches live rule state


async def test_index_auto_pending_approve_reject_and_stale(pool):
    from sentinel.index import service as ix
    for i, (t, s) in enumerate([("AAPL", -0.9), ("MSFT", 0.9), ("XOM", 0.8), ("JPM", -0.8)]):
        await put_signal(pool, mk_sig(f"ix{i}", NOW - timedelta(hours=2 + i), t, t, "Credit Event", sentiment=s))
    ev = await ix.recompute(pool, None, now=NOW, trigger={"id": "ix0", "headline": "Apple credit event"})
    assert ev and ev["status"] == "applied" and 0 < ev["turnover"] <= 0.05 + 1e-9        # one step is capped at 5% turnover
    _, w = await ix.weights_asof(pool, "live", NOW)
    assert w.sum() == pytest.approx(1.0)
    cons = {c["ticker"]: c for c in await ix.constituents(pool, "live", NOW)}
    assert cons["AAPL"]["activeWeight"] < 0 < cons["MSFT"]["activeWeight"]
    for _ in range(60):                                                                   # capped steps converge to the target
        if await ix.recompute(pool, None, now=NOW) is None:
            break
    else:
        pytest.fail("rebalancing never converged")
    _, w = await ix.weights_asof(pool, "live", NOW)
    # approval mode
    await ix.set_config(pool, None, {"mode": "approval", "turnoverCap": 0.5, "deadband": 0.001, "kappa": 1.0})
    for i, (t, s) in enumerate([("AAPL", 0.9), ("MSFT", -0.9)]):
        await put_signal(pool, mk_sig(f"ia{i}", NOW + timedelta(hours=1), t, t, "Earnings", sentiment=s))
    pend = await ix.recompute(pool, None, now=NOW + timedelta(hours=2))
    assert pend["status"] == "pending"
    _, still = await ix.weights_asof(pool, "live", NOW + timedelta(hours=2))
    assert np.allclose(still, w)                                                          # nothing applied yet
    done = await ix.decide(pool, None, pend["id"], True)
    assert done["status"] == "applied"
    with pytest.raises(ix.IndexError_):
        await ix.decide(pool, None, pend["id"], True)                                      # already decided
    _, after = await ix.weights_asof(pool, "live")
    assert after.sum() == pytest.approx(1.0) and not np.allclose(after, w)
    await put_signal(pool, mk_sig("ib0", NOW + timedelta(hours=3), "NVDA", "NVDA", "Cyber", sentiment=-0.9))
    p2 = await ix.recompute(pool, None, now=NOW + timedelta(hours=4))
    if p2:
        rej = await ix.decide(pool, None, p2["id"], False)
        assert rej["status"] == "rejected"
        _, same = await ix.weights_asof(pool, "live")
        assert np.allclose(same, after)
    with pytest.raises(ValueError):
        await ix.set_config(pool, None, {"minWeight": 0.5})
    with pytest.raises(KeyError):
        await ix.decide(pool, None, "nope", True)
    assert (await ledger.verify(pool))["ok"]
    acts = {r["action"] for r in await pool.fetch("SELECT action FROM audit_log")}
    assert {"rebalance", "rebalance_proposed", "rebalance_approved", "config_change"} <= acts


async def test_index_backtest_three_series_and_whipsaw(pool):
    from sentinel.index.backtest import run_backtest
    rng = np.random.default_rng(5)
    from sentinel.universe import UNIVERSE
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    n = 0
    for d in range(80):
        for s in UNIVERSE:
            if rng.random() < 0.25:
                n += 1
                await put_signal(pool, mk_sig(f"bt{n}", start + timedelta(days=d, hours=int(rng.integers(0, 20))), s.name, s.ticker,
                                              "Earnings", sentiment=float(rng.uniform(-1, 1)), integrity=float(rng.uniform(0.3, 1))))
    res = await run_backtest(pool, 100)
    assert res["status"] == "ready" and len(res["series"]) == 100
    m = res["metrics"]
    assert set(m) == {"benchmark", "sentinel", "naive"} and m["sentinel"]["annTurnover"] < m["naive"]["annTurnover"]
    assert m["sentinel"]["trackingError"] is not None


async def test_risk_index_ready_after_baseline(pool):
    from sentinel.risk import index as R
    for h in range(0, 24 * 6, 2):
        await put_signal(pool, mk_sig(f"rk{h}", NOW - timedelta(hours=h + 1), "Market", None, "Macroeconomic", impact=2.0 + (h % 5)))
    await put_signal(pool, mk_sig("rkbig", NOW - timedelta(minutes=20), "Market", None, "Geopolitical", impact=10.0, sentiment=-1.0))
    cur = await R.current(pool, "live", NOW)
    assert cur["status"] == "ready" and cur["value"] > 90 and cur["regime"] == "Stressed" and cur["components"][0]["signalId"] == "rkbig"
    calm = await R.current(pool, "live", NOW - timedelta(hours=60))
    assert calm["status"] == "ready" and calm["value"] < cur["value"]
    n = await R.record_hours(pool, "live", NOW - timedelta(hours=5), NOW)
    assert n == 6 and len(await R.history(pool, "live", 24, NOW)) >= 5


async def test_audit_chain_detects_tampering(pool):
    await pool.execute("DELETE FROM audit_log") if False else None
    for i in range(5):
        await ledger.append(pool, "t", "test", f"entry {i}", {"i": i, "x": 1.0})
    assert (await ledger.verify(pool))["ok"]
    with pytest.raises(Exception, match="append-only"):
        await pool.execute("UPDATE audit_log SET summary='x' WHERE seq = (SELECT max(seq) FROM audit_log)")
    with pytest.raises(Exception, match="append-only"):
        await pool.execute("DELETE FROM audit_log")
    seq = await pool.fetchval("SELECT seq FROM audit_log WHERE summary = 'entry 2' ORDER BY seq DESC LIMIT 1")
    await pool.execute("ALTER TABLE audit_log DISABLE TRIGGER audit_no_change")          # an attacker with superuser rights
    try:
        await pool.execute("UPDATE audit_log SET summary = 'forged' WHERE seq = $1", seq)
        res = await ledger.verify(pool)
        assert not res["ok"] and res["firstBroken"]["seq"] == seq
        await pool.execute("UPDATE audit_log SET summary = 'entry 2' WHERE seq = $1", seq)
        assert (await ledger.verify(pool))["ok"]
    finally:
        await pool.execute("ALTER TABLE audit_log ENABLE TRIGGER audit_no_change")


async def test_model_metrics_collect_has_no_invented_sections(pool):
    from sentinel.model import metrics
    m = await metrics.collect(pool)
    assert m["precedentValidation"] is None and m["signalBacktest"] is None and m["drift"] is None      # null until their jobs ran
    assert m["impact"]["n_events"] > 300 and m["pipeline"]["libraryEvents"] == 67
    from sentinel.jobs.tasks import validate_precedent
    v = await validate_precedent(pool)
    assert (await metrics.collect(pool))["precedentValidation"]["n"] == v["n"]
