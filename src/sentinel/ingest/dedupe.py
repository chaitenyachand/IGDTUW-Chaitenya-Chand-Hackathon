"""Near-duplicate index over SimHash values.

Pigeonhole banding: with max Hamming distance d, split the 64 bits into d+1 bands;
two hashes within distance d must share at least one band exactly.
Near-duplicates are NOT dropped: they are stored with dup_of so they count as corroboration.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from .base import hamming


class NearDuplicateIndex:
    def __init__(self, max_distance: int = 3):
        self.max_distance = max_distance
        self.n_bands = max_distance + 1
        width = 64 // self.n_bands
        self._slices = [
            (i * width, 64 if i == self.n_bands - 1 else (i + 1) * width)
            for i in range(self.n_bands)
        ]
        self._buckets = [dict() for _ in range(self.n_bands)]
        self._entries = deque()  # (ts, simhash, doc_id)

    def _keys(self, sh: int):
        for i, (lo, hi) in enumerate(self._slices):
            yield i, (sh >> lo) & ((1 << (hi - lo)) - 1)

    def add(self, sh: int, doc_id: str, ts: Optional[datetime] = None):
        if not sh:
            return
        ts = ts or datetime.now(timezone.utc)
        self._entries.append((ts, sh, doc_id))
        for i, k in self._keys(sh):
            self._buckets[i].setdefault(k, []).append((sh, doc_id))

    def find(self, sh: int) -> Optional[str]:
        if not sh:
            return None
        best, best_d = None, self.max_distance + 1
        for i, k in self._keys(sh):
            for other, doc_id in self._buckets[i].get(k, ()):
                d = hamming(sh, other)
                if d < best_d:
                    best, best_d = doc_id, d
        return best

    def prune(self, keep_hours: int = 48):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=keep_hours)
        while self._entries and self._entries[0][0] < cutoff:
            _, sh, doc_id = self._entries.popleft()
            for i, k in self._keys(sh):
                bucket = self._buckets[i].get(k)
                if bucket:
                    try:
                        bucket.remove((sh, doc_id))
                    except ValueError:
                        pass
                    if not bucket:
                        del self._buckets[i][k]

    def __len__(self):
        return len(self._entries)
