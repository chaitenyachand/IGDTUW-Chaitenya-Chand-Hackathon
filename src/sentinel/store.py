"""Database access: pool, document inserts with near-dup detection, source health, config."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import asyncpg

from .ingest.base import Document, simhash, to_signed, to_unsigned
from .ingest.dedupe import NearDuplicateIndex

log = logging.getLogger(__name__)

INSERT_DOC = """
INSERT INTO documents (id, source_type, source_name, mode, url, canonical_url, published_at,
                       language, title, text, author, raw_hash, simhash, dup_of, meta)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb)
ON CONFLICT DO NOTHING
RETURNING id
"""


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=5)


async def load_recent_into_index(pool, index: NearDuplicateIndex, hours: int = 48) -> int:
    rows = await pool.fetch(
        "SELECT id, simhash, published_at FROM documents "
        "WHERE simhash IS NOT NULL AND published_at > $1",
        datetime.now(timezone.utc) - timedelta(hours=hours),
    )
    for r in rows:
        index.add(to_unsigned(r["simhash"]), r["id"], r["published_at"])
    return len(rows)


async def insert_documents(pool, docs: list, index: NearDuplicateIndex) -> list:
    """Insert documents; returns [(document, dup_of_id_or_None)] for rows actually inserted."""
    inserted = []
    async with pool.acquire() as con:
        for d in docs:
            sh = simhash(f"{d.title} {d.text}")
            dup = index.find(sh) if sh else None
            new_id = await con.fetchval(
                INSERT_DOC, d.id, d.source_type, d.source_name, d.mode, d.url, d.canonical_url,
                d.published_at, d.language, d.title, d.text, d.author, d.raw_hash,
                to_signed(sh) if sh else None, dup, json.dumps(d.meta, default=str),
            )
            if new_id:
                inserted.append((d, dup))
                if sh:
                    index.add(sh, d.id, d.published_at)
    index.prune()
    return inserted


async def record_success(pool, name: str, n_items: int):
    await pool.execute(
        """INSERT INTO source_health (source_name, enabled, status, last_success, items_last_run, items_total, updated_at)
           VALUES ($1, TRUE, 'ok', now(), $2::int, $2::int, now())
           ON CONFLICT (source_name) DO UPDATE SET enabled = TRUE, status = 'ok', last_success = now(),
             items_last_run = $2::int, items_total = source_health.items_total + $2::int, updated_at = now()""",
        name, n_items,
    )


async def record_error(pool, name: str, msg: str):
    await pool.execute(
        """INSERT INTO source_health (source_name, status, last_error, last_error_msg, error_count, updated_at)
           VALUES ($1, 'error', now(), $2, 1, now())
           ON CONFLICT (source_name) DO UPDATE SET status = 'error', last_error = now(),
             last_error_msg = $2, error_count = source_health.error_count + 1, updated_at = now()""",
        name, msg[:500],
    )


async def set_disabled(pool, name: str, reason: str):
    await pool.execute(
        """INSERT INTO source_health (source_name, enabled, status, last_error_msg, updated_at)
           VALUES ($1, FALSE, 'disabled', $2, now())
           ON CONFLICT (source_name) DO UPDATE SET enabled = FALSE, status = 'disabled',
             last_error_msg = $2, updated_at = now()""",
        name, reason,
    )


async def get_config(pool, key: str):
    v = await pool.fetchval("SELECT value FROM app_config WHERE key = $1", key)
    return json.loads(v) if v is not None else None


async def set_config(pool, key: str, value):
    await pool.execute(
        """INSERT INTO app_config (key, value, updated_at) VALUES ($1, $2::jsonb, now())
           ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = now()""",
        key, json.dumps(value),
    )
