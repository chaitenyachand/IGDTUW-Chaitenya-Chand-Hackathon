"""Lazily loaded, periodically refreshed engines shared by the API routes."""
from __future__ import annotations

import asyncio
import time

from ..precedent.engine import Library
from ..stress.service import RuntimeHolder

LIB_REFRESH = 900


class LibraryCache:
    def __init__(self, pool):
        self.pool, self.lib, self.at, self._lock = pool, None, 0.0, asyncio.Lock()

    async def get(self) -> Library:
        async with self._lock:
            if self.lib is None or time.time() - self.at > LIB_REFRESH:
                self.lib, self.at = await Library.load(self.pool), time.time()
            return self.lib


def attach(app, pool):
    app.state.library = LibraryCache(pool)
    app.state.stress = RuntimeHolder(pool)
