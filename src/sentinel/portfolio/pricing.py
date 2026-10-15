"""Revaluation of the synthetic wholesale banking book under any market state (bonds, loans, swaps, FX, equity TRS, commodity)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

import numpy as np

IG_RATINGS = {"AAA", "AA", "A", "BBB"}
# multipliers on the index OAS (IG index for AAA..BBB, HY index for BB..CCC): documented modelling assumption
RATING_MULT = {"AAA": 0.50, "AA": 0.60, "A": 0.85, "BBB": 1.25, "BB": 0.70, "B": 1.30, "CCC": 2.50}
TENORS = [0.25, 2.0, 5.0, 10.0, 30.0]
CURVE_SERIES = {0.25: "DGS3MO", 2.0: "DGS2", 5.0: "DGS5", 10.0: "DGS10", 30.0: "DGS30"}


class MarketDataMissing(RuntimeError):
    pass


@dataclass(frozen=True)
class MarketState:
    asof: date
    curve: tuple          # yields in percent at TENORS
    ig_oas: float         # percent
    hy_oas: float         # percent
    spx: float
    eurusd: float
    gbpusd: float
    oil: float

    def y(self, t: float) -> float:
        return float(np.interp(t, TENORS, self.curve))


def years_to(maturity: date, asof: date) -> float:
    return max((maturity - asof).days / 365.25, 0.1)


def spread_pct(rating: str, st: MarketState) -> float:
    base = st.ig_oas if rating in IG_RATINGS else st.hy_oas
    return base * RATING_MULT.get(rating, 1.0)


def annuity(rate_pct: float, years: float, freq: int = 2) -> float:
    r = max(rate_pct, 1e-6) / 100.0 / freq
    n = years * freq
    return (1 - (1 + r) ** (-n)) / r / freq


def bond_price(coupon_pct: float, years: float, yld_pct: float, freq: int = 2) -> float:
    r, n = yld_pct / 100.0 / freq, int(round(years * freq))
    n = max(n, 1)
    c = coupon_pct / freq
    if abs(r) < 1e-9:
        return c * n + 100.0
    return c * (1 - (1 + r) ** (-n)) / r + 100.0 * (1 + r) ** (-n)


def value(h: dict, st: MarketState) -> float:
    """Market value in USD of one holding (positive = asset to the bank, negative = liability)."""
    t = h["terms"]
    N = h["notional"]
    yrs = years_to(h["maturity"], st.asof)
    kind = h["asset_type"]
    if kind == "Bond":
        y = st.y(yrs) + spread_pct(h["rating"], st)
        return N * bond_price(t["coupon"], yrs, y) / 100.0
    if kind == "Loan":      # floating rate: value moves with the discount margin, not with the risk-free curve
        dm = spread_pct(h["rating"], st)
        return N * (1.0 + (t["margin"] - dm) / 100.0 * annuity(st.y(yrs), yrs))
    sub = t["instrument"]
    if sub == "irs_pay_fixed":
        par = st.y(yrs)
        return N * annuity(par, yrs) * (par - t["fixed"]) / 100.0
    if sub == "fx_forward":
        spot = st.eurusd if t["currency"] == "EUR" else st.gbpusd
        return N * (spot / t["strike"] - 1.0)
    if sub == "equity_trs":
        return N * t["beta"] * (st.spx / t["strike"] - 1.0)
    if sub == "commodity_swap":
        return N * (st.oil / t["strike"] - 1.0)
    raise ValueError(f"unknown instrument {sub}")


def total(book: list, st: MarketState) -> float:
    return float(sum(value(h, st) for h in book))


FACTORS = ["equity", "rates_2y", "rates_5y", "rates_10y", "rates_30y", "spread_ig", "spread_hy", "eurusd", "gbpusd", "oil"]


def apply_shocks(st: MarketState, sh: dict) -> MarketState:
    """sh: equity/eurusd/gbpusd/oil as fractions; rates_* and spread_* in basis points."""
    curve = list(st.curve)
    shifts = {0.25: sh.get("rates_2y", 0.0), 2.0: sh.get("rates_2y", 0.0), 5.0: sh.get("rates_5y", 0.0),
              10.0: sh.get("rates_10y", 0.0), 30.0: sh.get("rates_30y", 0.0)}
    curve = tuple(c + shifts[t] / 100.0 for c, t in zip(curve, TENORS))
    return replace(st, curve=curve,
                   ig_oas=max(st.ig_oas + sh.get("spread_ig", 0.0) / 100.0, 0.05),
                   hy_oas=max(st.hy_oas + sh.get("spread_hy", 0.0) / 100.0, 0.30),
                   spx=st.spx * (1 + sh.get("equity", 0.0)), eurusd=st.eurusd * (1 + sh.get("eurusd", 0.0)),
                   gbpusd=st.gbpusd * (1 + sh.get("gbpusd", 0.0)), oil=st.oil * (1 + sh.get("oil", 0.0)))
