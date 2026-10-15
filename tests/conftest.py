import asyncio
import os

import pytest

DSN = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema():
    """Bring the test database up to the current schema once per session (migrations are idempotent)."""
    if not DSN:
        yield
        return
    from sentinel import store
    from tests.dbutil import apply_migrations

    async def run():
        pool = await store.create_pool(DSN)
        await apply_migrations(pool)
        await pool.close()
    asyncio.run(run())
    yield
