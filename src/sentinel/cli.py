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
    p.add_argument("command", choices=["migrate", "seed", "sync-prices", "sync-fred", "check-sources"])
    a = p.parse_args()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run({"migrate": migrate, "seed": seed, "sync-prices": sync_prices_cmd, "sync-fred": sync_fred_cmd,
                 "check-sources": check_sources}[a.command]())


if __name__ == "__main__":
    main()
