"""Command line tools: seed, sync-prices, sync-fred, check-sources."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time

import httpx

from . import store
from .config import settings
from .universe import FRED_SERIES, UNIVERSE, all_price_symbols

async def migrate():
    """Apply every db/init/*.sql file once, in order (the same files a fresh database runs on first start)."""
    from pathlib import Path
    pool = await store.create_pool(settings.database_url)
    await pool.execute("CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, "
                       "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
    done = {r["filename"] for r in await pool.fetch("SELECT filename FROM schema_migrations")}
    for f in sorted(Path("db/init").glob("*.sql")):
        if f.name in done:
            print(f"skip   {f.name}")
            continue
        await pool.execute(f.read_text())
        await pool.execute("INSERT INTO schema_migrations (filename) VALUES ($1) ON CONFLICT DO NOTHING", f.name)
        print(f"applied {f.name}")
    await pool.close()
    
async def labels_sample():
    """Write a stratified headline sample to data/labeling/sample_300.txt for hand-labelling."""
    from pathlib import Path
    from .tools.labeling import format_line, stratified_sample
    pool = await store.create_pool(settings.database_url)
    rows = await pool.fetch("""SELECT d.id, d.source_name, f.clean_title AS title, f.relevant
        FROM documents d JOIN doc_features f ON f.document_id = d.id
        WHERE d.dup_of IS NULL AND d.published_at > now() - interval '7 days'
          AND NOT COALESCE((f.features->>'automated')::boolean, false)
          AND NOT COALESCE((f.features->>'adult')::boolean, false)
          AND NOT COALESCE((f.features->>'gibberish')::boolean, false)""")
    sample = stratified_sample([dict(r) for r in rows], n=300)
    out = Path("data/labeling")
    out.mkdir(parents=True, exist_ok=True)
    (out / "sample_300.txt").write_text("\n".join(format_line(r) for r in sample) + "\n")
    print(f"wrote {len(sample)} lines to data/labeling/sample_300.txt")
    await pool.close()


async def import_labels():
    """Load a gold CSV (id prefix, relevant, event, sentiment) into gold_labels.
    Env: GOLD_FILE (default data/labeling/gold_labels.csv) and GOLD_SPLIT ('dev' or 'test')."""
    import csv
    import os
    path = os.environ.get("GOLD_FILE", "data/labeling/gold_labels.csv")
    split = os.environ.get("GOLD_SPLIT", "dev")
    pool = await store.create_pool(settings.database_url)
    ok = missing = ambiguous = 0
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            ids = await pool.fetch("SELECT id FROM documents WHERE id LIKE $1", r["id"].strip() + "%")
            if not ids:
                missing += 1
                continue
            if len(ids) > 1:
                ambiguous += 1
                continue
            sent = int(r["sentiment"]) if r["sentiment"].strip() else None
            await pool.execute(
                """INSERT INTO gold_labels (document_id, relevant, event_type, sentiment, split) VALUES ($1,$2,$3,$4,$5)
                   ON CONFLICT (document_id) DO UPDATE SET relevant=EXCLUDED.relevant, event_type=EXCLUDED.event_type,
                     sentiment=EXCLUDED.sentiment, split=EXCLUDED.split, labeled_at=now()""",
                ids[0]["id"], r["relevant"].strip() == "1", r["event"].strip(), sent, split)
            ok += 1
    print(f"imported {ok} '{split}' labels from {path}; {missing} ids not found in the database; {ambiguous} ambiguous prefixes")
    await pool.close()


async def eval_gate():
    """Compare the current relevance gate with the gold labels (dev split unless GOLD_SPLIT is set)."""
    import os
    from .tools.evaluation import binary_metrics, fmt_metrics
    split = os.environ.get("GOLD_SPLIT", "dev")
    pool = await store.create_pool(settings.database_url)
    rows = await pool.fetch(
        """SELECT d.source_name, f.relevant AS pred, g.relevant AS gold, f.relevance, f.clean_title
           FROM gold_labels g JOIN doc_features f ON f.document_id = g.document_id
           JOIN documents d ON d.id = g.document_id WHERE g.split = $1""", split)
    if not rows:
        print(f"no '{split}' gold labels found: run import-labels first")
        return
    group = lambda r: r["source_name"].split(":")[0]
    print(fmt_metrics("ALL", binary_metrics((r["pred"], r["gold"]) for r in rows)))
    for g in sorted({group(r) for r in rows}):
        print(fmt_metrics(g, binary_metrics((r["pred"], r["gold"]) for r in rows if group(r) == g)))
    for title, pred, gold in (("FALSE POSITIVES (gate kept, labelled irrelevant)", True, False),
                              ("FALSE NEGATIVES (gate blocked, labelled relevant)", False, True)):
        sel = sorted((r for r in rows if r["pred"] == pred and r["gold"] == gold), key=lambda r: -r["relevance"])[:12]
        print(f"\n{title}")
        for r in sel:
            print(f"  {r['relevance']:.2f} | {group(r):<9} | {r['clean_title'][:100]}")
    await pool.close()


async def train_baseline():
    """Cross-validated TF-IDF classifiers vs the rule pipeline, scored on the gold labels."""
    from .ml.baseline import format_report, make_tfidf_lr, run_tasks, save_json
    from .ml.data import load_gold, model_text
    pool = await store.create_pool(settings.database_url)
    rows = await load_gold(pool)
    await pool.close()
    if len(rows) < 30:
        print(f"only {len(rows)} gold labels in the database: run import-labels first")
        return
    res = run_tasks(rows, [model_text(r) for r in rows], make_tfidf_lr, name="tfidf+logistic-regression")
    print(format_report(res))
    save_json("data/models/metrics_baseline.json", res)
    print("\nsaved data/models/metrics_baseline.json")


async def eval_transformers():
    """MiniLM embeddings, zero-shot FinBERT and the hybrid models, scored on the dev gold labels (ml image)."""
    import json
    import os
    from .ml import transformers_eval as te
    from .ml.baseline import format_report, make_dense_lr, run_tasks, save_json
    from .ml.data import load_gold
    from .ml.hybrid import run_hybrid, summary
    pool = await store.create_pool(settings.database_url)
    rows = await load_gold(pool, "dev")
    await pool.close()
    if len(rows) < 30:
        print(f"only {len(rows)} dev gold labels in the database: run import-labels first")
        return
    titles = [r["title"] for r in rows]
    emb = te.embed(titles)
    probs = te.finbert_probs(titles)
    by_title = dict(zip(titles, probs))
    res_emb = run_tasks(rows, te.with_source_onehot(emb, rows), make_dense_lr, name="MiniLM-embeddings+logistic-regression")
    res_hyb = run_hybrid(rows, emb, probs)
    fin = te.eval_finbert(rows, probs_fn=lambda ts: [by_title[t] for t in ts])
    print(format_report(res_emb))
    print()
    print(format_report(res_hyb))
    named = {}
    if os.path.exists("data/models/metrics_baseline.json"):
        named["TF-IDF + logistic regression"] = json.load(open("data/models/metrics_baseline.json"))
    named["MiniLM + logistic regression"] = res_emb
    named["hybrid (embeddings + rules + FinBERT)"] = res_hyb
    print(summary(named, fin))
    save_json("data/models/metrics_transformers.json",
              {"embeddings": res_emb, "hybrid": res_hyb, "finbert_zero_shot": fin})
    print("\nsaved data/models/metrics_transformers.json")


async def labels_sample_random():
    """Uniform random sample (NOT stratified) for an unbiased, held-out test set."""
    from pathlib import Path
    from .tools.labeling import format_line
    pool = await store.create_pool(settings.database_url)
    rows = await pool.fetch("""SELECT d.id, d.source_name, f.clean_title AS title
        FROM documents d JOIN doc_features f ON f.document_id = d.id
        WHERE d.dup_of IS NULL AND d.published_at > now() - interval '7 days'
          AND NOT COALESCE((f.features->>'automated')::boolean, false)
          AND NOT COALESCE((f.features->>'adult')::boolean, false)
          AND NOT COALESCE((f.features->>'gibberish')::boolean, false)
          AND d.id NOT IN (SELECT document_id FROM gold_labels)
        ORDER BY md5(d.id || 'test-split-v1') LIMIT 150""")
    out = Path("data/labeling")
    out.mkdir(parents=True, exist_ok=True)
    (out / "random_150.txt").write_text("\n".join(format_line(dict(r)) for r in rows) + "\n")
    print(f"wrote {len(rows)} lines to data/labeling/random_150.txt")
    await pool.close()


async def train_final():
    """Train the frozen production models on the dev gold labels and save models/hybrid_v1.joblib (ml image)."""
    from .ml import transformers_eval as te
    from .ml.data import load_gold
    from .ml.train_final import ARTIFACT_PATH, save_artifacts, train_artifacts
    pool = await store.create_pool(settings.database_url)
    rows = await load_gold(pool, "dev")
    await pool.close()
    if len(rows) < 30:
        print(f"only {len(rows)} dev gold labels in the database: run import-labels first")
        return
    art = train_artifacts(rows, te.embed([r["title"] for r in rows]))
    save_artifacts(art, ARTIFACT_PATH)
    print(f"saved {ARTIFACT_PATH}: {art['version']}  trained on {art['n_train']} labels "
          f"({art['n_relevant']} relevant); event classes {art['event_classes']}; "
          f"merged into Other: {art['merged_into_other']}")


async def eval_test():
    """Score the FROZEN pipeline on the random held-out test split. Meant to be run once, when the pipeline is final."""
    from datetime import datetime, timezone
    from .ml.baseline import save_json
    from .ml.data import load_gold
    from .ml.final_eval import evaluate_test, format_test_report
    from .ml.serving import Scorer
    from .ml.train_final import ARTIFACT_PATH
    pool = await store.create_pool(settings.database_url)
    rows = await load_gold(pool, "test")
    if len(rows) < 30:
        print(f"only {len(rows)} test labels in the database: run import-test-labels first")
        await pool.close()
        return
    runs = await store.get_config(pool, "test_eval_runs") or []
    if runs:
        print(f"WARNING: the test split was already evaluated {len(runs)} time(s) (last: {runs[-1]['at']}). "
              "Re-running after changing the pipeline turns the test set into a second dev set.")
    scorer = Scorer.from_disk(ARTIFACT_PATH)
    _, rel_p, ev_proba = scorer.score_relevance_event(rows)
    probs = scorer.sentiment([r["title"] for r in rows])
    res = evaluate_test(rows, rel_p, ev_proba, probs, scorer.threshold)
    res["model_version"] = scorer.version
    runs.append({"at": datetime.now(timezone.utc).isoformat(), "model_version": scorer.version})
    res["run_number"] = len(runs)
    await store.set_config(pool, "test_eval_runs", runs)
    await pool.close()
    print(format_test_report(res, len(runs)))
    save_json("data/models/metrics_test.json", res)
    print("\nsaved data/models/metrics_test.json")


async def seed():
    pool = await store.create_pool(settings.database_url)
    async with pool.acquire() as con:
        await con.executemany(
            """INSERT INTO entities (ticker, name, sector, aliases) VALUES ($1,$2,$3,$4)
               ON CONFLICT (ticker) DO UPDATE SET name=EXCLUDED.name, sector=EXCLUDED.sector, aliases=EXCLUDED.aliases""",
            [(s.ticker, s.name, s.sector, list(s.aliases)) for s in UNIVERSE])
    print(f"seeded {len(UNIVERSE)} entities")
    await pool.close()


async def sync_prices_cmd():
    from .market.prices import sync_prices
    pool = await store.create_pool(settings.database_url)
    report = await sync_prices(pool, all_price_symbols())
    print(json.dumps(report, indent=2))
    await pool.close()


async def sync_fred_cmd():
    from .market.fred import sync_fred
    pool = await store.create_pool(settings.database_url)
    try:
        report = await sync_fred(pool, settings.fred_api_key, FRED_SERIES)
        print(json.dumps(report, indent=2))
    except RuntimeError as e:
        print(f"skipped: {e}")
        await store.set_disabled(pool, "fred", str(e))
    await pool.close()


async def check_sources():
    """Ping every source once so you can see what works from this machine."""
    import feedparser
    import websockets
    import yaml
    from pathlib import Path

    rows = []

    async def probe(name, coro):
        t = time.time()
        try:
            detail = await coro
            rows.append((name, "OK", f"{detail} ({time.time() - t:.1f}s)"))
        except Exception as e:
            rows.append((name, "FAIL", repr(e)[:120]))

    web = httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": settings.reddit_user_agent})
    sec = httpx.AsyncClient(timeout=20, headers={"User-Agent": settings.sec_user_agent})

    async def gdelt():
        r = await web.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt"); r.raise_for_status()
        return r.text.splitlines()[-1].split()[-1].rsplit("/", 1)[-1]

    async def edgar():
        r = await sec.get("https://www.sec.gov/files/company_tickers.json"); r.raise_for_status()
        return f"{len(r.json())} tickers"

    async def feed(f):
        r = await web.get(f["url"]); r.raise_for_status()
        return f"{len(feedparser.parse(r.content).entries)} entries"

    async def bsky():
        url = f"{settings.bluesky_jetstream_url}?wantedCollections=app.bsky.feed.post"
        async with websockets.connect(url) as ws:
            await asyncio.wait_for(ws.recv(), 10)
        return "stream receiving"

    async def reddit():
        if not (settings.reddit_client_id and settings.reddit_client_secret):
            raise RuntimeError("credentials not set")
        r = await web.post("https://www.reddit.com/api/v1/access_token", data={"grant_type": "client_credentials"},
                           auth=(settings.reddit_client_id, settings.reddit_client_secret))
        r.raise_for_status(); return "token issued"

    async def fred():
        if not settings.fred_api_key:
            raise RuntimeError("FRED_API_KEY not set")
        r = await web.get("https://api.stlouisfed.org/fred/series", params={"series_id": "DGS10",
                          "api_key": settings.fred_api_key, "file_type": "json"}); r.raise_for_status()
        return "key valid"

    async def yahoo():
        from .market.prices import _download
        rows_ = await asyncio.to_thread(_download, "SPY", time.strftime("%Y-%m-%d", time.gmtime(time.time() - 864000)))
        return f"{len(rows_)} recent SPY rows"

    feeds = yaml.safe_load(Path("config/feeds.yaml").read_text())["feeds"]
    await asyncio.gather(
        probe("gdelt", gdelt()), probe("sec_edgar", edgar()), probe("bluesky", bsky()),
        probe("reddit", reddit()), probe("fred", fred()), probe("yahoo (yfinance)", yahoo()),
        *[probe(f"rss:{f['name']}", feed(f)) for f in feeds])
    await web.aclose(); await sec.aclose()
    w = max(len(r[0]) for r in rows)
    for name, status, detail in sorted(rows):
        print(f"{name:<{w}}  {status:<4}  {detail}")



# ---------------- platform commands (phases 4-8) ----------------
async def _with_pool(fn):
    pool = await store.create_pool(settings.database_url)
    try:
        return await fn(pool)
    finally:
        await pool.close()


def _show(x):
    print(json.dumps(x, indent=2, default=str))


async def edgar_backfill_cmd():
    """Full SEC 8-K history of the index stocks (needs SEC_USER_AGENT), then real abnormal-return labels."""
    from .impact.edgar_backfill import backfill_edgar, label_events
    async def run(pool):
        _show(await backfill_edgar(pool, settings.sec_user_agent))
        _show(await label_events(pool))
    await _with_pool(run)


async def label_events_cmd():
    from .impact.edgar_backfill import label_events
    await _with_pool(lambda pool: _wrap(label_events(pool)))


async def _wrap(coro):
    _show(await coro)


async def train_impact_cmd():
    from .impact.jobs import train_impact
    async def run(pool):
        m = await train_impact(pool)
        _show({k: v for k, v in m.items() if k != "quintile_mean_actual"})
    await _with_pool(run)


async def build_library_cmd():
    """Embed the curated event library and compute every event's real forward market paths (ml image: needs MiniLM)."""
    from .ml.train_final import ARTIFACT_PATH, load_artifacts
    from .ml.transformers_eval import EMBED_MODEL, make_embedder
    from .precedent.library import build_library
    import os
    name = load_artifacts(ARTIFACT_PATH)["embed_model"] if os.path.exists(ARTIFACT_PATH) else EMBED_MODEL
    embed = make_embedder(name)          # must be the model that embeds live signals, or similarities are meaningless
    await _with_pool(lambda pool: _wrap(build_library(pool, lambda texts: embed(texts))))


async def portfolio_cmd():
    from .portfolio.store import build_portfolio
    from .stress.service import ensure_default_rules
    async def run(pool):
        _show(await build_portfolio(pool))
        print("default stress rules created:", await ensure_default_rules(pool))
    await _with_pool(run)


async def sync_caps_cmd():
    from .index.service import sync_caps
    await _with_pool(lambda pool: _wrap(sync_caps(pool)))


async def risk_backfill_cmd():
    from .risk.index import backfill
    await _with_pool(lambda pool: _wrap(backfill(pool, "live")))


async def index_backfill_cmd():
    from .index.backtest import backfill_weights
    await _with_pool(lambda pool: _wrap(backfill_weights(pool)))


async def validate_precedent_cmd():
    from .jobs.tasks import validate_precedent
    await _with_pool(lambda pool: _wrap(validate_precedent(pool)))


async def signal_backtest_cmd():
    from .model.backtest import signal_backtest
    await _with_pool(lambda pool: _wrap(signal_backtest(pool)))


async def drift_baseline_cmd():
    from .model.drift import take_baseline
    async def run(pool):
        s = await take_baseline(pool)
        print(f"drift baseline stored from {s['n']} signals")
    await _with_pool(run)


async def eval_calibration():
    """Calibration (reliability, ECE) of the FROZEN pipeline on the held-out test split. Same predictions as eval-test; it
    refuses to run if the pipeline changed since eval-test, so it can never become a second tuning loop (ml image)."""
    from .ml.baseline import save_json
    from .ml.data import load_gold
    from .ml.serving import Scorer
    from .ml.train_final import ARTIFACT_PATH
    from .model.calibration import calibration_report
    pool = await store.create_pool(settings.database_url)
    rows = await load_gold(pool, "test")
    await pool.close()
    try:
        done = json.load(open("data/models/metrics_test.json"))
    except FileNotFoundError:
        print("run eval-test first: calibration is reported for the same frozen pipeline")
        return
    scorer = Scorer.from_disk(ARTIFACT_PATH)
    if done.get("model_version") != scorer.version:
        print(f"pipeline changed since eval-test ({done.get('model_version')} -> {scorer.version}): refusing")
        return
    _, rel_p, ev_proba = scorer.score_relevance_event(rows)
    res = calibration_report(rows, rel_p, ev_proba, scorer.sentiment([r["title"] for r in rows]), scorer.threshold)
    save_json("data/models/metrics_calibration.json", res)
    print(f"ECE relevance={res['relevance']['ece']:.3f} event={res['event']['ece']} sentiment={res['sentiment']['ece']}")


async def replay_fetch(episode: str):
    from .demo.fetch import fetch_episode
    _show(await fetch_episode(episode))


async def replay_inject(episode: str):
    import redis.asyncio as aioredis
    from .demo.replay import inject
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    await _with_pool(lambda pool: _wrap(inject(pool, r, episode, actor="cli")))
    await r.aclose()


async def replay_reset():
    from .demo.replay import reset
    await _with_pool(lambda pool: _wrap(reset(pool, "cli")))


async def audit_verify():
    from .audit.ledger import verify
    await _with_pool(lambda pool: _wrap(verify(pool)))


COMMANDS = {
    "migrate": migrate, "labels-sample": labels_sample, "import-labels": import_labels, "eval-gate": eval_gate,
    "eval-test": eval_test, "train-final": train_final, "labels-sample-random": labels_sample_random,
    "train-baseline": train_baseline, "eval-transformers": eval_transformers, "seed": seed, "sync-prices": sync_prices_cmd,
    "sync-fred": sync_fred_cmd, "check-sources": check_sources,
    "edgar-backfill": edgar_backfill_cmd, "label-events": label_events_cmd, "train-impact": train_impact_cmd,
    "build-library": build_library_cmd, "portfolio": portfolio_cmd, "sync-caps": sync_caps_cmd,
    "risk-backfill": risk_backfill_cmd, "index-backfill": index_backfill_cmd, "validate-precedent": validate_precedent_cmd,
    "signal-backtest": signal_backtest_cmd, "drift-baseline": drift_baseline_cmd, "eval-calibration": eval_calibration,
    "replay-fetch": replay_fetch, "replay-inject": replay_inject, "replay-reset": replay_reset, "audit-verify": audit_verify,
}
NEEDS_EPISODE = {"replay-fetch", "replay-inject"}


def main():
    p = argparse.ArgumentParser(prog="sentinel")
    p.add_argument("command", choices=sorted(COMMANDS))
    p.add_argument("--episode", help="replay episode id (see data/replay/episodes.yaml)")
    a = p.parse_args()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if a.command in NEEDS_EPISODE:
        if not a.episode:
            p.error(f"{a.command} needs --episode")
        asyncio.run(COMMANDS[a.command](a.episode))
    else:
        asyncio.run(COMMANDS[a.command]())


if __name__ == "__main__":
    main()
