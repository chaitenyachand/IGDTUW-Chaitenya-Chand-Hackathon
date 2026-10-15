"""Kernel estimate of the expected market move for a headline from its historical analogs (PRECEDENT)."""
from __future__ import annotations

import numpy as np

FLOOR, LAM = 0.30, 0.05      # similarity below FLOOR carries no weight; LAM is the weight of the 'ordinary day' prior


def expected_move(analogs: list, a0: float) -> float:
    """analogs: [(similarity, |5-day SPY move|)]. A headline that resembles no major event reverts to the ordinary-day
    move a0; one that closely resembles an event (e.g. an invasion) is pulled towards what followed it."""
    w = [max(s - FLOOR, 0.0) ** 2 for s, _ in analogs]
    num = sum(wi * a for wi, (_, a) in zip(w, analogs)) + LAM * a0
    return float(num / (sum(w) + LAM))


def percentile_impact(value: float, ref_sorted) -> float:
    """1-10 score: 1 + 9 x the percentile of `value` within the reference distribution of historical moves."""
    ref = np.asarray(ref_sorted)
    return round(1.0 + 9.0 * float(np.searchsorted(ref, value, side="right")) / max(len(ref), 1), 2)
