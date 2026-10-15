"""Pricing against closed-form values, Shapley efficiency, historical vs parametric VaR, credit migration."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from sentinel.portfolio.pricing import MarketState, annuity, apply_shocks, bond_price, total, value
from sentinel.stress import credit
from sentinel.stress.engine import GROUPS, shapley, var_es

ASOF = date(2026, 10, 9)
ST = MarketState(ASOF, (4.0, 4.0, 4.2, 4.4, 4.6), 1.2, 4.0, 5000.0, 1.10, 1.30, 70.0)


def h(kind, terms, **kw):
    base = {"id": "x", "asset_type": kind, "counterparty": "c", "ticker": None, "sector": "Financials", "country": "US",
            "notional": 100e6, "rating": "A", "maturity": ASOF + timedelta(days=int(5 * 365.25)), "terms": terms}
    return {**base, **kw}


def test_bond_closed_form():
    assert bond_price(5.0, 10, 5.0) == pytest.approx(100.0, abs=1e-9)         # priced at par when yield == coupon
    assert bond_price(0.0, 10, 4.0) == pytest.approx(100 / (1.02 ** 20))      # zero coupon, semi-annual compounding
    assert bond_price(5, 10, 6) < 100 < bond_price(5, 10, 4)


def test_bond_dv01_matches_bump():
    b = h("Bond", {"coupon": 5.0})
    base = value(b, ST)
    up = value(b, apply_shocks(ST, {"rates_2y": 1, "rates_5y": 1, "rates_10y": 1, "rates_30y": 1}))
    assert up < base and 3e3 < base - up < 8e4        # ~ 100m x duration(~4) x 1bp


def test_swap_fx_equity_commodity_closed_forms():
    yrs = (h("Bond", {})["maturity"] - ASOF).days / 365.25
    par = ST.y(yrs)
    swap = h("Derivative", {"instrument": "irs_pay_fixed", "fixed": par})
    assert value(swap, ST) == pytest.approx(0.0, abs=1e-6)                      # at-the-money swap is worth zero
    up = value(swap, apply_shocks(ST, {"rates_2y": 10, "rates_5y": 10, "rates_10y": 10, "rates_30y": 10}))
    assert up == pytest.approx(100e6 * annuity(par + 0.10, yrs) * 0.10 / 100, rel=1e-9)   # pay-fixed gains when rates rise
    assert value(h("Derivative", {"instrument": "fx_forward", "currency": "EUR", "strike": 1.0}), ST) == pytest.approx(100e6 * 0.10)
    assert value(h("Derivative", {"instrument": "equity_trs", "beta": 1.2, "strike": 4000.0}), ST) == pytest.approx(100e6 * 1.2 * 0.25)
    assert value(h("Derivative", {"instrument": "commodity_swap", "strike": 50.0}), ST) == pytest.approx(100e6 * 0.4)


def test_loan_at_market_margin_is_par():
    from sentinel.portfolio.pricing import spread_pct
    assert value(h("Loan", {"margin": spread_pct("A", ST)}), ST) == pytest.approx(100e6)
    assert value(h("Loan", {"margin": spread_pct("A", ST)}), apply_shocks(ST, {"spread_ig": 100})) < 100e6


def book():
    from sentinel.portfolio.pricing import spread_pct
    return [h("Bond", {"coupon": 5.0}), h("Loan", {"margin": 1.0}), h("Derivative", {"instrument": "irs_pay_fixed", "fixed": 4.0}),
            h("Derivative", {"instrument": "equity_trs", "beta": 1.0, "strike": 5000.0}, notional=50e6),
            h("Derivative", {"instrument": "fx_forward", "currency": "GBP", "strike": 1.3}, notional=30e6)]


def test_shapley_is_order_independent_and_efficient():
    b = book()
    detail = {"equity": -0.1, "rates_2y": 50, "rates_5y": 50, "rates_10y": 50, "rates_30y": 50, "spread_ig": 80, "gbpusd": -0.05}
    attr = shapley(b, ST, detail)
    full = total(b, apply_shocks(ST, detail)) - total(b, ST)
    assert sum(a["delta"] for a in attr) == pytest.approx(full, rel=1e-9)         # attributions add up to the total P&L
    again = shapley(b, ST, dict(reversed(list(detail.items()))))
    assert {a["factor"]: round(a["delta"], 4) for a in attr} == {a["factor"]: round(a["delta"], 4) for a in again}
    assert {a["factor"] for a in attr} == {"equity", "rates", "credit_spread", "fx"}


def test_historical_var_matches_parametric_on_gaussian_factors():
    rng = np.random.default_rng(3)
    cols = [c for g in GROUPS.values() for c in g]
    scale = {"equity": 0.01, "eurusd": 0.004, "gbpusd": 0.004, "oil": 0.015}
    hist = pd.DataFrame({c: rng.normal(0, scale.get(c, 3.0), 3000) for c in cols})
    b = book()
    hv, es = var_es(b, ST, hist, 0.99)
    base = total(b, ST)
    pnl = np.array([total(b, apply_shocks(ST, r)) - base for r in hist.to_dict("records")])
    parametric = 2.3263 * pnl.std() - pnl.mean()                                   # normal 99% quantile
    assert hv == pytest.approx(parametric, rel=0.12)
    assert es >= hv > 0


def test_migration_matrix_and_expected_loss():
    assert np.allclose(credit.MIGRATION.sum(axis=1), 1.0)
    m = credit.stressed_matrix(3.0, 2.0)
    assert np.allclose(m.sum(axis=1), 1.0) and (m >= 0).all()
    assert all(m[i, -1] >= credit.MIGRATION[i, -1] for i in range(7))
    wide = apply_shocks(ST, {"spread_ig": 150, "spread_hy": 400})
    el = credit.expected_loss(book(), ST, wide)
    assert el["after"] > el["before"] > 0 and el["exposure"] == 200e6
    same = credit.expected_loss(book(), ST, ST)
    assert same["delta"] == pytest.approx(0.0)
