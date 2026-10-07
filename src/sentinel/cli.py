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
    """Load data/labeling/gold_labels.csv (id prefix, relevant, event, sentiment) into gold_labels."""
    import csv
    pool = await store.create_pool(settings.database_url)
    ok = missing = ambiguous = 0
    with open("data/labeling/gold_labels.csv", newline="") as fh:
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
                """INSERT INTO gold_labels (document_id, relevant, event_type, sentiment) VALUES ($1,$2,$3,$4)
                   ON CONFLICT (document_id) DO UPDATE SET relevant=EXCLUDED.relevant,
                     event_type=EXCLUDED.event_type, sentiment=EXCLUDED.sentiment, labeled_at=now()""",
                ids[0]["id"], r["relevant"].strip() == "1", r["event"].strip(), sent)
            ok += 1
    print(f"imported {ok} labels; {missing} ids not found in the database; {ambiguous} ambiguous prefixes")
    await pool.close()


async def eval_gate():
    """Compare the current relevance gate with the gold labels."""
    from .tools.evaluation import binary_metrics, fmt_metrics
    pool = await store.create_pool(settings.database_url)
    rows = await pool.fetch(
        """SELECT d.source_name, f.relevant AS pred, g.relevant AS gold, f.relevance, f.clean_title
           FROM gold_labels g JOIN doc_features f ON f.document_id = g.document_id
           JOIN documents d ON d.id = g.document_id""")
    if not rows:
        print("no gold labels found: run import-labels first")
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


def main():
    p = argparse.ArgumentParser(prog="sentinel")
    p.add_argument("command", choices=["migrate", "labels-sample", "import-labels", "eval-gate", "seed", "sync-prices", "sync-fred", "check-sources"])
    a = p.parse_args()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run({"migrate": migrate, "labels-sample": labels_sample, "import-labels": import_labels, "eval-gate": eval_gate, "seed": seed, "sync-prices": sync_prices_cmd, "sync-fred": sync_fred_cmd,
                 "check-sources": check_sources}[a.command]())


if __name__ == "__main__":
    main()
