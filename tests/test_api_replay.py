"""REST + WebSocket contract, auth, caching and the end-to-end replay (design test 16): WebSocket messages, DB rows and audit
entries must agree. Content of the replay archive below is TEST-ONLY; production episodes come from `make replay-fetch`."""
import json
import os
from datetime import datetime, timedelta, timezone

import pytest
import redis.asyncio as aioredis
from fastapi.testclient import TestClient

from sentinel import store
from sentinel.config import settings
from tests.platform_fixtures import DSN, IMPACT_PATH, RURL, mk_sig, put_signal, reset_state, seed_once
from tests.test_serving import fake_embed, fake_finbert, gold_rows

pytestmark = pytest.mark.skipif(not (DSN and RURL), reason="TEST_DATABASE_URL / TEST_REDIS_URL not set")
NOW = datetime(2026, 10, 9, 14, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def seeded():
    if DSN:
        seed_once()


@pytest.fixture
def client(monkeypatch):
    import asyncio
    monkeypatch.setattr(settings, "database_url", DSN)
    monkeypatch.setattr(settings, "redis_url", RURL)
    monkeypatch.setattr(settings, "api_token", "")
    from sentinel.api.common import ttl
    from sentinel.api.main import app

    async def prep():
        p = await store.create_pool(DSN)
        await reset_state(p)
        await put_signal(p, mk_sig("api1", NOW, "Apple", "AAPL", "Credit Event"))
        await p.close()
    asyncio.run(prep())
    ttl.clear()
    with TestClient(app) as c:
        yield c


def test_read_endpoints_and_envelope(client):
    for path in ("/api/health", "/api/risk-index", "/api/signals", "/api/portfolio", "/api/portfolio/exposure", "/api/stress/scenarios",
                 "/api/stress/rules", "/api/stress/reverse", "/api/stress/worst-shock?targetLossPct=3", "/api/index/constituents", "/api/index/weights",
                 "/api/index/rebalances", "/api/index/config", "/api/index/performance?days=60", "/api/model/metrics", "/api/audit",
                 "/api/audit/verify", "/api/alerts", "/api/stress/runs", "/api/stress/watchlist", "/api/demo/episodes", "/api/demo/status"):
        r = client.get(path)
        assert r.status_code == 200, (path, r.text[:300])
        body = r.json()
        assert set(body) == {"data", "meta"} and {"source", "asOf"} <= set(body["meta"]), path
    assert client.get("/api/portfolio").json()["meta"]["source"] == "synthetic"
    assert client.get("/api/stress/worst-shock?targetLossPct=3").json()["data"]["achievedLossPct"] == pytest.approx(3.0, abs=1e-6)
    assert len(client.get("/api/portfolio").json()["data"]) == 109
    r = client.get("/api/risk-index")
    assert r.status_code == 409 and r.json()["error"]["code"] == "insufficient_history" or r.json()["data"]["regime"] in ("Calm", "Elevated", "Stressed")


def test_errors_use_the_error_envelope(client):
    for path, status in (("/api/signals/nope", 404), ("/api/precedent/nope", 404), ("/api/signals?cursor=garbage", 400),
                         ("/api/risk-index?source=x", 422), ("/api/signals?limit=0", 422), ("/api/stress/runs/zzz", 404)):
        r = client.get(path)
        assert r.status_code == status and set(r.json()) == {"error"} and {"code", "message"} == set(r.json()["error"]), path


def test_precedent_etag_and_shrinkage(client):
    r = client.get("/api/precedent/api1")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["signalId"] == "api1" and d["status"] in ("ready", "insufficient_data")
    for s in d["shocks"]:
        assert {"lowSample", "shrunkMedian", "priorMedian"} <= set(s)
        if s["lowSample"]:
            assert min(s["median"], s["priorMedian"]) - 1e-12 <= s["shrunkMedian"] <= max(s["median"], s["priorMedian"]) + 1e-12
    tag = r.headers["etag"]
    assert client.get("/api/precedent/api1", headers={"If-None-Match": tag}).status_code == 304


def test_stress_run_validation_brief_and_rules(client):
    ok = client.post("/api/stress/run", json={"mode": "manual", "shocks": [{"factor": "equity", "value": -0.15, "unit": "pct"},
                                                                        {"factor": "rates", "value": 75, "unit": "bps"}]})
    assert ok.status_code == 200, ok.text
    run = ok.json()["data"]
    assert run["valueAfter"] < run["valueBefore"] and run["mode"] == "manual"
    assert client.get(f"/api/stress/runs/{run['id']}").json()["data"]["id"] == run["id"]
    assert client.get("/api/stress/runs").json()["data"][0]["id"] == run["id"]
    html = client.get(f"/api/stress/runs/{run['id']}/brief")
    assert html.status_code == 200 and "SYNTHETIC PORTFOLIO" in html.text and "Shapley" in html.text
    pdf = client.get(f"/api/stress/runs/{run['id']}/brief?format=pdf")
    assert pdf.status_code in (200, 501) and (pdf.content[:4] == b"%PDF" if pdf.status_code == 200 else True)
    assert client.post("/api/stress/run", json={"mode": "manual", "shocks": {"equity": -5}}).status_code == 422
    assert client.post("/api/stress/run", json={"mode": "manual", "shocks": {"banana": 1}}).status_code == 422
    assert client.post("/api/stress/run", json={"mode": "calibrated"}).status_code == 422          # needs a signalId
    assert client.post("/api/stress/run", json={"scenarioId": "no-such"}).status_code == 422
    sc = client.get("/api/stress/scenarios").json()["data"]
    assert sc and {"id", "name", "eventType", "shocks", "armed"} <= set(sc[0])
    assert client.post("/api/stress/run", json={"scenarioId": sc[0]["id"]}).status_code == 200
    # rules CRUD
    rule = client.post("/api/stress/rules", json={"eventType": "Cyber", "minImpact": 6, "minIntegrity": 0.5}).json()["data"]
    assert rule["scenarioId"] == "calibrated" and rule["cooldownMinutes"] == 60
    upd = client.put(f"/api/stress/rules/{rule['id']}", json={"eventType": "Cyber", "minImpact": 8, "enabled": False})
    assert upd.json()["data"]["minImpact"] == 8 and upd.json()["data"]["enabled"] is False
    assert client.post("/api/stress/rules", json={"eventType": "Nope", "minImpact": 5}).status_code == 422
    assert client.post("/api/stress/rules", json={"eventType": "Cyber", "minImpact": 50}).status_code == 422
    assert client.delete(f"/api/stress/rules/{rule['id']}").status_code == 200
    assert client.delete(f"/api/stress/rules/{rule['id']}").status_code == 404
    assert client.put("/api/stress/watchlist", json={"eventTypes": ["Cyber"]}).json()["data"] == ["Cyber"]
    assert client.put("/api/stress/watchlist", json={"eventTypes": ["Bad"]}).status_code == 422
    assert client.get("/api/audit/verify").json()["data"]["intact"] is True
    acts = {e["action"] for e in client.get("/api/audit?limit=200").json()["data"]}
    assert {"stress_run", "rule_created", "rule_updated", "rule_deleted", "watchlist_change"} <= acts


def test_index_config_and_rebalance_endpoints(client):
    cfg = client.put("/api/index/config", json={"mode": "approval", "kappa": 0.5, "maxTurnover": 0.08}).json()["data"]
    assert cfg["mode"] == "approval" and cfg["kappa"] == 0.5 and cfg["maxTurnover"] == 0.08
    assert client.put("/api/index/config", json={"minWeight": 0.9}).status_code == 422
    assert client.put("/api/index/config", json={"bogus": 1}).status_code == 422
    assert client.post("/api/index/rebalances/none/approve").status_code == 404
    c = client.get("/api/index/constituents").json()["data"]
    assert len(c) == 15 and sum(x["currentWeight"] for x in c) == pytest.approx(1.0)
    perf = client.get("/api/index/performance?days=60").json()["data"]
    assert "weights" not in perf and perf["status"] in ("ready", "no_signals") and perf["stats"]["tilted"]["turnover"] >= 0


def test_write_endpoints_need_the_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "s3cret")
    body = {"mode": "manual", "shocks": {"equity": -0.05}}
    assert client.post("/api/stress/run", json=body).status_code == 401
    assert client.post("/api/stress/run", json=body, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/api/stress/run", json=body, headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert client.get("/api/stress/rules").status_code == 200            # reads stay open
    assert client.post("/api/demo/reset").status_code == 401


def test_rate_limit(client, monkeypatch):
    from sentinel.api.common import limiter
    monkeypatch.setattr(settings, "write_rate_limit_per_minute", 3)
    limiter.reset()
    codes = [client.post("/api/demo/reset").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
    limiter.reset()


def test_demo_inject_errors(client):
    assert client.post("/api/demo/inject", json={"episodeId": "nope"}).status_code in (404, 409)
    eps = client.get("/api/demo/episodes").json()["data"]
    assert {"svb-2023-03", "ukraine-2022-02"} <= {e["id"] for e in eps}
    missing = next(e for e in eps if not e["available"])
    r = client.post("/api/demo/inject", json={"episodeId": missing["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "replay_data_missing" and "make replay-fetch" in r.json()["error"]["message"]


REPLAY_ROWS = [
    ("Apple shares slump as sanctions hit oil exports", "Reuters", 0), ("Apple shares slump as sanctions hit oil exports today", "CNBC", 7),
    ("Microsoft rally as central bank raises interest rates", "Bloomberg", 40), ("Exxon Mobil slump after sanctions hit oil exports", "FT", 95),
    ("JPMorgan reports record profit and earnings rally", "WSJ", 130), ("Local football festival results flat", "Local", 150),
]


def write_episode(directory):
    (directory / "episodes.yaml").write_text(
        "episodes:\n  - {id: test-ep, title: Test episode, eventType: Geopolitical, start: '2023-03-09T00:00:00Z', end: '2023-03-11T00:00:00Z', keywords: [x]}\n")
    t0 = datetime(2023, 3, 9, 14, tzinfo=timezone.utc)
    with open(directory / "test-ep.jsonl", "w") as fh:
        for i, (title, src, mins) in enumerate(REPLAY_ROWS):
            fh.write(json.dumps({"episode": "test-ep", "key": f"k{i}", "source": "gdelt", "sourceType": "news", "url": f"https://{src.lower()}.test/{i}",
                                 "publishedAt": (t0 + timedelta(minutes=mins)).isoformat(), "title": title, "text": title,
                                 "meta": {"domain": f"{src.lower()}.test"}}) + "\n")


async def test_replay_end_to_end(tmp_path, monkeypatch):
    import asyncio
    from sentinel.audit import ledger
    from sentinel.demo import episodes, replay
    from sentinel.ml import serve_worker
    from sentinel.ml.serving import Scorer
    from sentinel.ml.train_final import train_artifacts
    from sentinel.pipeline import Pipeline
    write_episode(tmp_path)
    monkeypatch.setattr(episodes, "REPLAY_DIR", tmp_path)
    pool = await store.create_pool(DSN)
    redis = aioredis.from_url(RURL, decode_responses=True)
    await reset_state(pool)
    await redis.delete("stream:signals")
    await put_signal(pool, mk_sig("live1", NOW, "Apple", "AAPL", "Credit Event"))            # live state that replay must not touch
    live_audit = await pool.fetchval("SELECT count(*) FROM audit_log")
    base_seq = await pool.fetchval("SELECT coalesce(max(seq), 0) FROM audit_log")     # the ledger is append-only: count only new rows

    res = await replay.inject(pool, redis, "test-ep", pace_seconds=0)
    assert res["queued"] == 6 and res["source"] == "replay" and res["from"].startswith("2023-03-09")
    st = await replay.status(pool)
    assert st["documents"] == 6 and st["scored"] == 0 and not st["done"]

    gold = gold_rows()
    scorer = Scorer(train_artifacts(gold, fake_embed([r["title"] for r in gold])), fake_embed, fake_finbert)
    pipeline = await Pipeline.create(pool, redis, impact_path=IMPACT_PATH, audit_min_impact=0.0)
    assert pipeline.impact is not None
    seen = []
    while True:
        rows = await pool.fetch(serve_worker.REPLAY_SQL, scorer.version, 3)
        if not rows:
            break
        seen += [r["published_at"] for r in rows]
        await serve_worker.score_batch(pool, redis, scorer, rows, pipeline)
    assert seen == sorted(seen)                                                                # chronological, oldest first

    st = await replay.status(pool)
    assert st["done"] and st["signals"] >= 3 and st["scored"] == st["documents"] - st["duplicates"]
    sigs = await pool.fetch("SELECT * FROM signals WHERE mode = 'replay' ORDER BY ts")
    assert all(r["ts"].year == 2023 for r in sigs)                                              # original publication times kept
    assert any(r["impact"] is not None for r in sigs) and all(r["explanation"] is not None for r in sigs)
    assert not any("Local football" in r["headline"] for r in sigs)                             # irrelevant item gated out

    # WebSocket stream agrees with the database
    msgs = await redis.xrange("stream:signals")
    types = [f["type"] for _, f in msgs]
    assert types.count("signal") == len(sigs) and types.count("precedent_ready") == len(sigs) and "risk_index" in types
    assert {f["source"] for _, f in msgs} == {"replay"}
    assert {json.loads(f["payload"])["id"] for _, f in msgs if f["type"] == "signal"} == {r["id"] for r in sigs}

    # derived state is replay-tagged, live state untouched, audit chain intact and consistent
    assert await pool.fetchval("SELECT count(*) FROM rebalance_events WHERE source = 'live'") == 0
    assert await pool.fetchval("SELECT count(*) FROM risk_index_history WHERE source = 'live'") == 0
    assert await pool.fetchval("SELECT count(*) FROM stress_rules WHERE last_fired IS NOT NULL") == 0
    n_reb = await pool.fetchval("SELECT count(*) FROM rebalance_events WHERE source = 'replay'")
    n_audit_reb = await pool.fetchval("SELECT count(*) FROM audit_log WHERE seq > $1 AND action = 'rebalance' AND payload->>'source' = 'replay'", base_seq)
    assert n_reb == n_audit_reb and n_reb >= 1
    n_sig_audit = await pool.fetchval("SELECT count(*) FROM audit_log WHERE seq > $1 AND action = 'signal' AND payload->>'source' = 'replay'", base_seq)
    assert n_sig_audit == sum(1 for r in sigs if r["impact"] is not None)
    assert await pool.fetchval("SELECT count(*) FROM audit_log WHERE seq > $1 AND action = 'demo_inject'", base_seq) == 1
    assert (await ledger.verify(pool))["ok"] and await pool.fetchval("SELECT count(*) FROM audit_log") > live_audit
    live_sigs = await pool.fetch("SELECT id FROM signals WHERE mode <> 'replay'")
    assert [r["id"] for r in live_sigs] == ["live1"]

    # replay is hidden from live views and visible with source=replay
    monkeypatch.setattr(settings, "database_url", DSN)
    monkeypatch.setattr(settings, "redis_url", RURL)
    from sentinel.api.main import app
    from sentinel.api.common import ttl
    ttl.clear()
    with TestClient(app) as c:
        assert [s["id"] for s in c.get("/api/signals").json()["data"]] == ["live1"]
        assert len(c.get("/api/signals?mode=replay").json()["data"]) == len(sigs)
        assert c.get("/api/index/rebalances?source=replay").json()["data"] != [] or n_reb == 0
        assert c.get("/api/index/rebalances").json()["data"] == []
        rr = c.get("/api/risk-index?source=replay").json()
        assert rr["meta"]["source"] == "replay"
        with c.websocket_connect("/ws/signals?since=0&source=replay") as ws:
            assert ws.receive_json()["type"] == "hello"
            first = ws.receive_json()
            assert first["source"] == "replay" and first["type"] in ("signal", "precedent_ready", "risk_index", "rebalance", "stress_run", "alert")
        with c.websocket_connect("/ws/signals?since=0&source=live") as ws:                      # nothing live was published
            assert ws.receive_json()["type"] == "hello"

    cleared = await replay.reset(pool)
    assert cleared["documentsRemoved"] == 6
    assert await pool.fetchval("SELECT count(*) FROM signals WHERE mode = 'replay'") == 0
    assert await pool.fetchval("SELECT count(*) FROM rebalance_events WHERE source = 'replay'") == 0
    assert (await ledger.verify(pool))["ok"]
    await redis.aclose()
    await pool.close()


def test_gdelt_archive_fetch_parsing_and_stamps(tmp_path):
    """Parsing of a GKG archive file in the real column layout (TEST-ONLY synthetic rows) and the sampling grid."""
    import io
    import zipfile
    from sentinel.demo import fetch
    from tests.test_gdelt import row
    r1 = row(title="Silicon Valley Bank collapses as depositors rush")
    r1[1] = "20230310121500"
    r2 = row(title="Unrelated finance story about bonds")
    r2[1] = "20230310121500"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.gkg.csv", "\n".join("\t".join(r) for r in (r1, r2)))
    start, end = datetime(2023, 3, 9, tzinfo=timezone.utc), datetime(2023, 3, 14, tzinfo=timezone.utc)
    recs = fetch.records_from_zip(buf.getvalue(), ["Silicon Valley Bank"], start, end, "svb")
    assert len(recs) == 1 and recs[0]["publishedAt"].startswith("2023-03-10T12:15")
    assert fetch.records_from_zip(buf.getvalue(), ["Silicon Valley Bank"], start, datetime(2023, 3, 10, tzinfo=timezone.utc), "svb") == []
    st = fetch.gkg_stamps(start, start + timedelta(hours=3), 60)
    assert st == ["20230309000000", "20230309010000", "20230309020000"]
