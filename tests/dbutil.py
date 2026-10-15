"""Test helpers: apply every migration to the test database (idempotent) and seed market data fixtures."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


async def apply_migrations(pool):
    for f in sorted((ROOT / "db" / "init").glob("*.sql")):
        sql = f.read_text()
        try:
            await pool.execute(sql)
        except Exception as e:                       # plain Postgres without pgvector: the schema stores embeddings as REAL[]
            if "vector" not in str(e).lower():
                raise
            await pool.execute(re.sub(r"CREATE EXTENSION IF NOT EXISTS vector;", "", sql))
