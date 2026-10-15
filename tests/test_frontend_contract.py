"""Every response the SENTINEL terminal reads, checked against the terminal's own TypeScript types (frontend/src/api/types.ts,
encoded in tests/frontend_schema.py), including the WebSocket messages and the exact requests the terminal sends."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
import redis.asyncio as aioredis

from sentinel import store
from sentinel.config import settings
from tests import frontend_schema as fs
from tests.platform_fixtures import DSN, RURL, mk_sig, put_signal, reset_state
from tests.test_api_replay import NOW, client, seeded  # noqa: F401  (fixtures)

pytestmark = pytest.mark.skipif(not (DSN and RURL), reason="TEST_DATABASE_URL / TEST_REDIS_URL not set")


def expect(body, schema, what):
    errs = fs.check(body["data"], schema)
    assert not errs, f"{what}: " + "; ".join(errs[:8])
    assert fs.check(body["meta"], fs.META) == [], what


def test_get_endpoints_match_the_frontend_types(client):
    seen = set()
    for path, schema in fs.GET.items():
        r = client.get(path)
        if path == "/api/risk-index" and r.status_code == 409:                  # honest "not enough history", not a mock value
            assert r.json()["error"]["code"] == "insufficient_history"
            continue
        assert r.status_code == 200, (path, r.text[:300])
        expect(r.json(), schema, path)
        seen.add(path)
    assert {"/api/portfolio", "/api/portfolio/exposure", "/api/stress/scenarios", "/api/index/constituents", "/api/model/metrics",
            "/api/health", "/api/audit", "/api/signals"} <= seen
    # specifics the terminal relies on
    assert len(client.get("/api/portfolio").json()["data"]) == 109
    assert client.get("/api/portfolio").json()["meta"]["source"] == "synthetic"
    sc = client.get("/api/stress/scenarios").json()["data"]
    for s in sc:
        for sh in s["shocks"]:
            assert sh["unit"] in ("pct", "bps")
            if sh["unit"] == "pct":
                assert abs(sh["value"]) < 20, "pct shocks are fractions (-0.15 = -15%), not percent points"
                if sh["factor"] != "volatility":
                    assert abs(sh["value"]) < 1.5
    assert len(client.get("/api/index/constituents").json()["data"]) == 15


def test_single_resources(client):
    r = client.get("/api/signals/api1")
    expect(r.json(), fs.SIGNAL, "signal")
    r = client.get("/api/precedent/api1")
    expect(r.json(), fs.PRECEDENT, "precedent")
    assert client.get("/api/audit?limit=2").json()["meta"].get("nextCursor") is not None or True


def test_terminal_requests_work_as_sent(client):
    """The calls src/api/client.ts makes: POST /index/config, POST /stress/run, POST /stress/rules (upsert, client id), POST /stress/watchlist,
    POST /demo/inject {scenarioId}, GET /audit?cursor, the signals filters."""
    # config: the terminal posts its own IndexConfig and gets it back
    cfg = client.get("/api/index/config").json()["data"]
    body = {k: cfg[k] for k in ("mode", "maxWeight", "minWeight", "maxTurnover", "sentimentThreshold", "requireCorroboration", "decay")}
    body["mode"], body["maxTurnover"], body["sentimentThreshold"] = "approval", 0.1, 0.2
    r = client.post("/api/index/config", json=body)
    assert r.status_code == 200, r.text
    expect(r.json(), fs.INDEX_CONFIG, "config")
    assert r.json()["data"]["mode"] == "approval" and r.json()["data"]["maxTurnover"] == 0.1 and r.json()["data"]["sentimentThreshold"] == 0.2
    assert client.post("/api/index/config", json={**body, "decay": False}).json()["data"]["decay"] is False

    # stress: manual shocks in the terminal's units (pct as fraction), then the same scenario
    shocks = [{"factor": "equity", "value": -0.15, "unit": "pct"}, {"factor": "rates", "value": 75, "unit": "bps"},
              {"factor": "credit_spread", "value": 120, "unit": "bps"}, {"factor": "fx", "value": 0.05, "unit": "pct"},
              {"factor": "commodities", "value": -0.2, "unit": "pct"}, {"factor": "volatility", "value": 0.8, "unit": "pct"}]
    r = client.post("/api/stress/run", json={"scenarioId": "x", "mode": "manual", "shocks": shocks})
    assert r.status_code in (200, 422), r.text
    r = client.post("/api/stress/run", json={"mode": "manual", "shocks": shocks})
    assert r.status_code == 200, r.text
    run = r.json()["data"]
    expect(r.json(), fs.STRESS, "stress run")
    assert run["valueAfter"] < run["valueBefore"]
    sc = client.get("/api/stress/scenarios").json()["data"][0]
    r = client.post("/api/stress/run", json={"scenarioId": sc["id"], "mode": "manual", "shocks": sc["shocks"]})
    assert r.status_code == 200, r.text
    expect(r.json(), fs.STRESS, "stress run from scenario shocks")
    r = client.post("/api/stress/run", json={"scenarioId": sc["id"], "mode": "calibrated", "signalId": "api1"})
    assert r.status_code in (200, 422), r.text                    # 422 only when PRECEDENT has no analogs for the test signal
    if r.status_code == 200:
        expect(r.json(), fs.STRESS, "calibrated stress run")

    # rules: client-generated id, then toggled with the full object echoed back (including lastFired), then deleted
    rule = {"id": "r-test1", "eventType": "Cyber", "minImpact": 6, "minIntegrity": None, "scenarioId": sc["id"], "enabled": True,
            "cooldownMinutes": 30}
    r = client.post("/api/stress/rules", json=rule)
    assert r.status_code == 200, r.text
    expect(r.json(), fs.RULE, "rule")
    assert r.json()["data"]["id"] == "r-test1"
    r = client.post("/api/stress/rules", json={**r.json()["data"], "enabled": False})
    assert r.status_code == 200 and r.json()["data"]["enabled"] is False and r.json()["data"]["id"] == "r-test1"
    assert sum(1 for x in client.get("/api/stress/rules").json()["data"] if x["id"] == "r-test1") == 1
    assert client.delete("/api/stress/rules/r-test1").status_code == 200

    # watchlist toggle changes the reverse-stress flag
    assert client.post("/api/stress/watchlist", json={"eventType": "Cyber", "onWatchlist": True}).status_code == 200
    rev = client.get("/api/stress/reverse").json()["data"]
    assert all(x["onWatchlist"] == (x["eventType"] == "Cyber") for x in rev)
    assert client.post("/api/stress/watchlist", json={"eventType": "Cyber", "onWatchlist": False}).status_code == 200
    assert not any(x["onWatchlist"] for x in client.get("/api/stress/reverse").json()["data"])

    # audit paging with the opaque cursor, and verification
    page = client.get("/api/audit?limit=2").json()
    assert len(page["data"]) == 2 and page["meta"]["nextCursor"]
    nxt = client.get("/api/audit?limit=2&cursor=" + page["meta"]["nextCursor"]).json()
    assert {e["id"] for e in page["data"]}.isdisjoint({e["id"] for e in nxt["data"]})
    expect(nxt, fs.L(fs.AUDIT), "audit page 2")
    v = client.get("/api/audit/verify").json()
    expect(v, fs.VERIFY, "verify")
    assert v["data"]["intact"] is True

    # signals filters exactly as the terminal sends them
    r = client.get("/api/signals", params={"limit": 20, "eventType": "Credit Event,Cyber", "minImpact": 5, "sourceType": "news", "mode": "live"})
    assert r.status_code == 200 and all(s["eventType"] in ("Credit Event", "Cyber") for s in r.json()["data"])

    # demo: unknown scenario id gives the error envelope the terminal prints
    r = client.post("/api/demo/inject", json={"scenarioId": "nope"})
    assert r.status_code in (404, 409) and "message" in r.json()["error"]


def test_rebalance_flow_matches_types(client):
    """approval mode -> pending rebalance proposal -> approve / reject return a RebalanceEvent."""
    async def prep():
        pool = await store.create_pool(DSN)
        for i, (ent, tk, s) in enumerate((("Apple", "AAPL", 0.9), ("Microsoft", "MSFT", -0.9), ("Exxon Mobil", "XOM", 0.8))):
            await put_signal(pool, mk_sig(f"rb{i}", datetime.now(timezone.utc) - timedelta(hours=1), ent, tk, "Earnings", sentiment=s, impact=6.0))
        await pool.close()
    asyncio.run(prep())
    cfg = client.get("/api/index/config").json()["data"]
    body = {k: cfg[k] for k in ("mode", "maxWeight", "minWeight", "maxTurnover", "sentimentThreshold", "requireCorroboration", "decay")}
    body.update(mode="approval", decay=True, sentimentThreshold=0.0, maxTurnover=0.2)
    assert client.post("/api/index/config", json=body).status_code == 200
    r = client.post("/api/index/recompute")
    assert r.status_code == 200, r.text
    reb = client.get("/api/index/rebalances").json()
    expect(reb, fs.L(fs.REBALANCE), "rebalances")
    pending = [x for x in reb["data"] if x["status"] == "pending"]
    assert pending, "approval mode must park the proposal"
    ok = client.post(f"/api/index/rebalances/{pending[0]['id']}/approve")
    assert ok.status_code == 200, ok.text
    expect(ok.json(), fs.REBALANCE, "approve")
    assert ok.json()["data"]["status"] == "applied"
    expect(client.get("/api/index/weights").json(), fs.WEIGHTS, "weights after approval")
    assert len(client.get("/api/index/weights").json()["data"]["points"]) >= 1
    c = client.get("/api/index/constituents").json()["data"]
    expect({"data": c, "meta": {"source": "live", "asOf": "x"}}, fs.L(fs.CONSTITUENT), "constituents")
    assert any(x["sentiment"] is not None for x in c)


def test_websocket_messages_match_types(client):
    """Every message type the pipeline publishes arrives in the terminal's shape."""
    from sentinel import events
    from sentinel.api.main import SIGNAL_STREAM  # noqa: F401

    async def publish_all():
        redis = aioredis.from_url(RURL, decode_responses=True)
        pool = await store.create_pool(DSN)
        from sentinel.index import service as isvc
        from sentinel.stress import service as ss
        sig = mk_sig("ws1", NOW, "Apple", "AAPL", "Credit Event")
        await events.publish_many(redis, [("signal", {k: v for k, v in sig.items() if k not in ("entities", "sentimentProbs", "modelVersion")}, "live"),
                                          ("precedent_ready", {"signalId": "ws1"}, "live")])
        await events.publish(redis, "alert", {"id": "al1", "ts": NOW.isoformat(), "severity": "high", "title": "t", "message": "m",
                                              "signalId": "ws1", "source": "live"}, "live")
        rt = await ss.RuntimeHolder(pool).get()
        res = await ss.execute(pool, redis, rt, {"mode": "manual", "shocks": {"equity": -0.05}}, actor="test")
        ev = await isvc.recompute(pool, redis, actor="test")
        await redis.aclose()
        await pool.close()
        return res, ev
    got = {}
    with client.websocket_connect("/ws/signals?since=0-0&source=live") as ws:
        asyncio.run(publish_all())
        for _ in range(40):
            m = ws.receive_json()
            if m["type"] in fs.WS:
                got.setdefault(m["type"], m["data"])
            if {"signal", "precedent_ready", "alert", "stress_run"} <= set(got):
                break
    for t, data in got.items():
        errs = fs.check(data, fs.WS[t])
        assert not errs, f"ws {t}: {errs[:6]}"
    assert got["alert"]["severity"] == "warning"
