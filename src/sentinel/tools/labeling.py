"""Build a stratified sample of collected headlines for hand-labelling (the gold set)."""
from __future__ import annotations

import random
from collections import defaultdict

QUOTAS = {"gdelt": 0.40, "bluesky": 0.30, "rss": 0.25, "sec_edgar": 0.05}


def group_of(source_name: str):
    if source_name.startswith("rss:"):
        return "rss"
    return source_name if source_name in QUOTAS else None


def stratified_sample(rows: list, n: int = 300, seed: int = 7) -> list:
    """Per source group: half items the gate keeps, half it blocks (so we see what it misses too)."""
    rng = random.Random(seed)
    by = defaultdict(lambda: {True: [], False: []})
    for r in rows:
        g = group_of(r["source_name"])
        if g:
            by[g][bool(r["relevant"])].append(r)
    out = []
    for g, share in QUOTAS.items():
        want = round(n * share)
        pos, neg = by[g][True][:], by[g][False][:]
        rng.shuffle(pos)
        rng.shuffle(neg)
        k_neg = min(len(neg), want // 2)
        k_pos = min(len(pos), want - k_neg)
        k_neg = min(len(neg), want - k_pos)      # top up if the relevant side is short
        out += pos[:k_pos] + neg[:k_neg]
    rng.shuffle(out)
    return out


def format_line(r: dict) -> str:
    title = " ".join(str(r["title"]).split())[:150]
    return f"{r['id'][:8]} | {r['source_name'].split(':')[0]} | {title}"
