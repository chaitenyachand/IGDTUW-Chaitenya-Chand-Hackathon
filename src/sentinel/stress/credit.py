"""Expected credit loss from rating migration under a stress scenario (design section 8.2).

ASSUMPTIONS (documented in the README, replace before any external use):
  * MIGRATION is an ILLUSTRATIVE one-year transition matrix of the same order of magnitude as published long-run averages for
    global corporates (rows sum to 1, last column is default). It is not a copy of a licensed rating-agency table.
  * A stress scales the probability of moving to a WORSE rating (including default) by how much the matching spread index
    widens (IG OAS for AAA..BBB, HY OAS for BB..CCC), capped at MAX_SCALE; the staying probability absorbs the change.
  * Expected loss = exposure x P(default within one year) x LGD, on loans and bonds only (exposure = notional, assumed fully
    drawn). Derivatives are excluded: their loss depends on counterparty exposure, which this book does not model.
"""
from __future__ import annotations

import numpy as np

from ..portfolio.pricing import IG_RATINGS

RATINGS = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "D"]
MIGRATION = np.array([
    # AAA     AA      A       BBB     BB      B       CCC     D
    [0.9100, 0.0780, 0.0090, 0.0020, 0.0005, 0.0003, 0.0001, 0.0001],   # AAA
    [0.0060, 0.9060, 0.0780, 0.0070, 0.0015, 0.0010, 0.0003, 0.0002],   # AA
    [0.0005, 0.0200, 0.9100, 0.0600, 0.0060, 0.0025, 0.0005, 0.0005],   # A
    [0.0003, 0.0020, 0.0400, 0.9050, 0.0380, 0.0100, 0.0030, 0.0017],   # BBB
    [0.0001, 0.0004, 0.0030, 0.0600, 0.8400, 0.0750, 0.0130, 0.0085],   # BB
    [0.0000, 0.0003, 0.0010, 0.0040, 0.0600, 0.8300, 0.0550, 0.0497],   # B
    [0.0000, 0.0000, 0.0020, 0.0040, 0.0100, 0.1000, 0.6200, 0.2640],   # CCC
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],                           # D
])
LGD = {"Loan": 0.45, "Bond": 0.60}
MAX_SCALE = 8.0
ASSUMPTION = ("illustrative one-year migration matrix; downgrade and default probabilities scale with the spread widening "
              "of the matching index; loans and bonds only; LGD 45% (loans) and 60% (bonds)")


def stressed_matrix(scale_ig: float, scale_hy: float) -> np.ndarray:
    m = MIGRATION.copy()
    for i, r in enumerate(RATINGS[:-1]):
        k = float(np.clip(scale_ig if r in IG_RATINGS else scale_hy, 1.0, MAX_SCALE))
        worse = m[i, i + 1:] * k
        stay_room = m[i, i] + m[i, i + 1:].sum() - worse.sum()
        if stay_room < 0:                                    # cannot move more mass than the row holds
            worse *= (m[i, i] + m[i, i + 1:].sum()) / worse.sum()
            stay_room = 0.0
        m[i, i + 1:] = worse
        m[i, i] = stay_room
    return m


def pd_by_rating(matrix: np.ndarray) -> dict:
    return {r: float(matrix[i, -1]) for i, r in enumerate(RATINGS)}


def downgrade_prob_by_rating(matrix: np.ndarray) -> dict:
    return {r: float(matrix[i, i + 1:].sum()) for i, r in enumerate(RATINGS[:-1])}


def expected_loss(book: list, st_before, st_after) -> dict:
    """Expected one-year credit loss of the book under the base and the stressed market state."""
    scale_ig = st_after.ig_oas / max(st_before.ig_oas, 1e-9)
    scale_hy = st_after.hy_oas / max(st_before.hy_oas, 1e-9)
    base, stressed = MIGRATION, stressed_matrix(scale_ig, scale_hy)
    pd0, pd1 = pd_by_rating(base), pd_by_rating(stressed)
    dg0, dg1 = downgrade_prob_by_rating(base), downgrade_prob_by_rating(stressed)
    el0 = el1 = exposure = 0.0
    dgw0 = dgw1 = 0.0
    for h in book:
        lgd = LGD.get(h["asset_type"])
        if lgd is None or h["rating"] not in pd0:
            continue
        ead = abs(h["notional"])
        exposure += ead
        el0 += ead * pd0[h["rating"]] * lgd
        el1 += ead * pd1[h["rating"]] * lgd
        dgw0 += ead * dg0.get(h["rating"], 0.0)
        dgw1 += ead * dg1.get(h["rating"], 0.0)
    return {"horizonYears": 1, "exposure": float(exposure), "before": float(el0), "after": float(el1), "delta": float(el1 - el0),
            "downgradeProbBefore": float(dgw0 / exposure) if exposure else 0.0,
            "downgradeProbAfter": float(dgw1 / exposure) if exposure else 0.0,
            "spreadScale": {"ig": float(scale_ig), "hy": float(scale_hy)},
            "pdByRating": [{"rating": r, "before": pd0[r], "after": pd1[r]} for r in RATINGS[:-1]],
            "assumption": ASSUMPTION}


def sentence(el: dict) -> str:
    return (f"Expected one-year credit loss on loans and bonds moves from ${el['before']/1e6:,.1f}m to ${el['after']/1e6:,.1f}m "
            f"({el['delta']/1e6:+,.1f}m) under the illustrative migration assumption.")
