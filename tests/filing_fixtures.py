"""TEST-ONLY SEC submissions blocks in the real `filings.recent` shape, so parsing and labelling run without the network."""
from __future__ import annotations

import numpy as np
import pandas as pd

ITEM_SETS = ["2.02,9.01", "1.01,9.01", "5.02", "8.01", "1.05", "2.04,9.01", "7.01,9.01", "4.02", "3.01", "2.01,9.01"]


def submissions_block(ticker: str, n: int = 40, seed: int = 0, start="2008-01-02", end="2026-08-30") -> dict:
    rng = np.random.default_rng(seed + sum(map(ord, ticker)))
    days = pd.bdate_range(start, end)
    pick = np.sort(rng.choice(len(days), size=n, replace=False))
    forms, acc, when, items = [], [], [], []
    for k, i in enumerate(pick):
        d = days[i]
        hour, minute = int(rng.choice([12, 13, 14, 20, 21, 22])), int(rng.integers(0, 60))
        forms.append("8-K" if rng.random() > 0.05 else "10-Q")
        acc.append(f"{ticker}-{k:04d}-{d:%Y%m%d}")
        when.append(f"{d:%Y-%m-%d}T{hour:02d}:{minute:02d}:00.000Z")
        items.append(str(rng.choice(ITEM_SETS)))
    return {"form": forms, "accessionNumber": acc, "acceptanceDateTime": when, "items": items}
