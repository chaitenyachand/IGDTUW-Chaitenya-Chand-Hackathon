"""Stress Lab engine: calibrated and manual shocks, full revaluation, historical VaR / Expected Shortfall,
order-independent (Shapley) attribution, scenario library from real events, reverse stress test and rule helpers."""
from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import factorial

import numpy as np
import pandas as pd

from ..market.series import load_macro, load_prices
from ..portfolio.pricing import CURVE_SERIES, FACTORS, MarketDataMissing, MarketState, TENORS, apply_shocks, total, value

DUR_LQD, DUR_HYG = 8.3, 3.8           # approximate effective durations of the bond ETFs used as spread proxies
PASS_IG, PASS_HY = 1.0, 0.6           # share of a Treasury yield move assumed to pass into the ETF yield
GROUPS = {"equity": ["equity"], "rates": ["rates_2y", "rates_5y", "rates_10y", "rates_30y"],
          "credit_spread": ["spread_ig", "spread_hy"], "fx": ["eurusd", "gbpusd"], "commodities": ["oil"]}
SECTOR_ETF = {"Information Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV", "Industrials": "XLI",
              "Utilities": "XLU", "Consumer Staples": "XLP", "Consumer Discretionary": "XLY", "Communication Services": "XLC"}
MACRO_IDS = list(CURVE_SERIES.values()) + ["BAMLC0A0CM", "BAMLH0A0HYM2", "DEXUSEU", "DEXUSUK", "DCOILWTICO", "DTWEXBGS"]


@dataclass
class Context:
    state: MarketState
    book: list
    hist: pd.DataFrame
    fx_beta: dict          # eurusd / gbpusd per unit USD-index move
    hy_ig_ratio: float
    sector_beta: dict


async def load_state(pool) -> MarketState:
    macro = await load_macro(pool, MACRO_IDS, "2020-01-01")
    prices = await load_prices(pool, ["SPY"], "2020-01-01")
    need = list(CURVE_SERIES.values()) + ["BAMLC0A0CM", "BAMLH0A0HYM2", "DEXUSEU", "DEXUSUK", "DCOILWTICO"]
    missing = [c for c in need if c not in macro or macro[c].dropna().empty] + ([] if "SPY" in prices else ["SPY"])
    if missing:
        raise MarketDataMissing(f"missing market data {missing}: run `make fred` and `make prices` first")
    last = lambda c: float(macro[c].dropna().iloc[-1])
    return MarketState(prices.index[-1].date(), tuple(last(CURVE_SERIES[t]) for t in TENORS), last("BAMLC0A0CM"),
                       last("BAMLH0A0HYM2"), float(prices["SPY"].dropna().iloc[-1]), last("DEXUSEU"), last("DEXUSUK"),
                       last("DCOILWTICO"))


async def load_hist(pool, days: int = 500) -> pd.DataFrame:
    macro = await load_macro(pool, MACRO_IDS, "2018-01-01")
    spy = (await load_prices(pool, ["SPY"], "2018-01-01"))["SPY"]
    df = pd.DataFrame({"equity": spy.pct_change(), "rates_2y": macro["DGS2"].diff() * 100, "rates_5y": macro["DGS5"].diff() * 100,
                       "rates_10y": macro["DGS10"].diff() * 100, "rates_30y": macro["DGS30"].diff() * 100,
                       "spread_ig": macro["BAMLC0A0CM"].diff() * 100, "spread_hy": macro["BAMLH0A0HYM2"].diff() * 100,
                       "eurusd": macro["DEXUSEU"].pct_change(), "gbpusd": macro["DEXUSUK"].pct_change(),
                       "oil": macro["DCOILWTICO"].pct_change()}).dropna()
    df = df[np.isfinite(df).all(axis=1)]
    if len(df) < 60:
        raise MarketDataMissing("fewer than 60 days of aligned factor history: run `make fred` and `make prices`")
    return df.tail(days)


def estimate_betas(hist: pd.DataFrame, macro: pd.DataFrame, sector_returns: dict) -> tuple:
    usd = macro["DTWEXBGS"].pct_change().dropna() if "DTWEXBGS" in macro else pd.Series(dtype=float)
    fx = {}
    for k, col in (("eurusd", "eurusd"), ("gbpusd", "gbpusd")):
        j = pd.concat([usd, hist[col]], axis=1, keys=["u", "f"]).dropna()
        fx[k] = float(np.polyfit(j["u"], j["f"], 1)[0]) if len(j) > 60 else -0.6
    ig, hy = hist["spread_ig"].values, hist["spread_hy"].values
    ratio = float(np.polyfit(ig, hy, 1)[0]) if len(ig) > 60 and ig.std() > 0 else 2.0
    return fx, max(ratio, 1.0), sector_returns


async def load_context(pool) -> Context:
    from ..portfolio.generator import SECTOR_BETA_DEFAULT
    state = await load_state(pool)
    hist = await load_hist(pool)
    macro = await load_macro(pool, MACRO_IDS, "2018-01-01")
    px = await load_prices(pool, ["SPY"] + list(SECTOR_ETF.values()), "2021-01-01")
    betas = {}
    for sector, etf in SECTOR_ETF.items():
        if etf in px:
            j = px[[etf, "SPY"]].pct_change().dropna()
            betas[sector] = float(np.polyfit(j["SPY"], j[etf], 1)[0]) if len(j) > 120 else SECTOR_BETA_DEFAULT
    fx, ratio, _ = estimate_betas(hist, macro, betas)
    rows = await pool.fetch("SELECT * FROM portfolio_holdings ORDER BY id")
    if not rows:
        raise MarketDataMissing("no portfolio: run `make portfolio` first")
    book = [{**dict(r), "terms": json.loads(r["terms"]) if isinstance(r["terms"], str) else r["terms"]} for r in rows]
    return Context(state, book, hist, fx, ratio, betas)


def expand_ui_shocks(ui: dict, ctx: Context) -> dict:
    """Frontend factors -> detailed factor shocks. API units: "pct" factors are FRACTIONS (-0.15 = -15%), rates and spreads are bps.
    Volatility is accepted and stored in the run, but the book has no volatility-sensitive instrument, so it does not move value."""
    d = {}
    if ui.get("equity"):
        d["equity"] = ui["equity"]
    if ui.get("rates"):
        d.update({k: ui["rates"] for k in GROUPS["rates"]})
    if ui.get("credit_spread"):
        d["spread_ig"], d["spread_hy"] = ui["credit_spread"], ui["credit_spread"] * ctx.hy_ig_ratio
    if ui.get("fx"):
        d["eurusd"], d["gbpusd"] = ctx.fx_beta["eurusd"] * ui["fx"], ctx.fx_beta["gbpusd"] * ui["fx"]
    if ui.get("commodities"):
        d["oil"] = ui["commodities"]
    return d


def shocks_from_values(v: dict, ctx: Context) -> dict:
    """Realised (or calibrated) market moves -> factor shocks. v: equity, oil, hyg, lqd, uup (fractions), dgs2, dgs10 (bps)."""
    d = {}
    if v.get("equity") is not None:
        d["equity"] = v["equity"]
    r10 = v.get("dgs10")
    if r10 is not None:
        r2 = v.get("dgs2") if v.get("dgs2") is not None else r10
        d.update(rates_2y=r2, rates_10y=r10, rates_5y=r2 + (r10 - r2) * 3 / 8, rates_30y=r10)
        if v.get("lqd") is not None:
            d["spread_ig"] = float(np.clip(-v["lqd"] / DUR_LQD * 1e4 - PASS_IG * r10, -300, 1500))
        if v.get("hyg") is not None:
            d["spread_hy"] = float(np.clip(-v["hyg"] / DUR_HYG * 1e4 - PASS_HY * r10, -500, 3000))
    if v.get("uup") is not None:
        d["eurusd"], d["gbpusd"] = ctx.fx_beta["eurusd"] * v["uup"], ctx.fx_beta["gbpusd"] * v["uup"]
    if v.get("oil") is not None:
        d["oil"] = v["oil"]
    return d


def event_values(ev, idx: int = 4) -> dict:
    g = lambda k: (ev.paths[k][idx][1] if k in ev.paths else None)
    return {"equity": g("equity_index"), "oil": g("oil"), "hyg": g("high_yield"), "lqd": g("inv_grade"), "uup": g("dollar"),
            "dgs2": g("dgs2_bps"), "dgs10": g("dgs10_bps")}


def aggregate_values(agg: dict) -> dict:
    med = {s["assetClass"]: s["median"] for s in agg["shocks"]}
    fs = agg["factorShocks"]
    return {"equity": med.get("equity_index"), "oil": med.get("oil"), "hyg": med.get("high_yield"), "lqd": med.get("inv_grade"),
            "uup": med.get("dollar"), "dgs2": fs.get("dgs2_bps", {}).get("median"), "dgs10": fs.get("dgs10_bps", {}).get("median")}


def var_es(book: list, st: MarketState, hist: pd.DataFrame, level: float = 0.99) -> tuple:
    base = total(book, st)
    pnl = np.array([total(book, apply_shocks(st, row)) - base for row in hist.to_dict("records")])
    cut = np.percentile(pnl, (1 - level) * 100)
    return float(max(-cut, 0.0)), float(max(-pnl[pnl <= cut].mean(), 0.0))


def shapley(book: list, st: MarketState, detail: dict) -> list:
    base = total(book, st)
    groups = [g for g, cols in GROUPS.items() if any(abs(detail.get(c, 0.0)) > 0 for c in cols)]
    n = len(groups)
    if n == 0:
        return []
    cache = {}

    def v(sub: tuple) -> float:
        if sub not in cache:
            sh = {c: detail[c] for g in sub for c in GROUPS[g] if c in detail}
            cache[sub] = total(book, apply_shocks(st, sh)) - base
        return cache[sub]
    out = []
    for g in groups:
        others = [x for x in groups if x != g]
        phi = 0.0
        for r in range(len(others) + 1):
            for S in itertools.combinations(others, r):
                w = factorial(r) * factorial(n - r - 1) / factorial(n)
                phi += w * (v(tuple(sorted(S + (g,)))) - v(tuple(sorted(S))))
        out.append({"factor": g, "delta": float(phi)})
    return sorted(out, key=lambda x: x["delta"])


def _group_deltas(book, st, st2, key) -> list:
    agg = defaultdict(float)
    for h in book:
        agg[h[key]] += value(h, st2) - value(h, st)
    return sorted(({key: k, "delta": float(v)} for k, v in agg.items()), key=lambda x: x["delta"])


def narrative(name: str, before: float, after: float, drivers: list, sectors: list, var_b: float, var_a: float) -> str:
    d = (after - before) / abs(before) * 100 if before else 0.0
    parts = [f"Under '{name}' the book moves from ${before/1e6:,.0f}m to ${after/1e6:,.0f}m ({d:+.2f}%)."]
    if drivers:
        top = drivers[0] if abs(drivers[0]["delta"]) >= abs(drivers[-1]["delta"]) else drivers[-1]
        parts.append(f"Largest driver: {top['factor'].replace('_', ' ')} ({top['delta']/1e6:+,.1f}m).")
    if sectors:
        s = sectors[0]
        parts.append(f"Most affected sector: {s['sector']} ({s['delta']/1e6:+,.1f}m).")
    parts.append(f"1-day 99% VaR moves from ${var_b/1e6:,.1f}m to ${var_a/1e6:,.1f}m.")
    return " ".join(parts)


def run_stress(ctx: Context, detail: dict, scenario_id: str | None, mode: str, name: str = "manual shock",
               signal_id: str | None = None, var_before: tuple | None = None) -> dict:
    st, book = ctx.state, ctx.book
    st2 = apply_shocks(st, detail)
    before, after = total(book, st), total(book, st2)
    vb, eb = var_before or var_es(book, st, ctx.hist)
    va, ea = var_es(book, st2, ctx.hist)
    by_cls = []
    for cls in ("Loan", "Bond", "Derivative"):
        sub = [h for h in book if h["asset_type"] == cls]
        by_cls.append({"assetClass": cls, "before": total(sub, st), "after": total(sub, st2)})
    drivers = shapley(book, st, detail)
    sectors = _group_deltas(book, st, st2, "sector")
    return {"scenarioId": scenario_id or "manual", "mode": mode, "triggeredBySignalId": signal_id,
            "ts": datetime.now(timezone.utc).isoformat(), "valueBefore": before, "valueAfter": after,
            "varBefore": vb, "varAfter": va, "esBefore": eb, "esAfter": ea, "byFactor": drivers, "byAssetClass": by_cls,
            "bySector": sectors, "byCountry": _group_deltas(book, st, st2, "country"),
            "narrative": narrative(name, before, after, drivers, sectors, vb, va)}


def scenario_ui_shocks(detail: dict, ctx: Context, vix_pts=None, vix_level=None) -> list:
    """Scenario shocks in API units: fractions for "pct", bps for "bps". Volatility is the relative VIX change after the event."""
    vol = (vix_pts / vix_level) if (vix_pts is not None and vix_level) else 0.0
    return [{"factor": "equity", "value": round(detail.get("equity", 0.0), 5), "unit": "pct"},
            {"factor": "rates", "value": round(detail.get("rates_10y", 0.0), 1), "unit": "bps"},
            {"factor": "credit_spread", "value": round(detail.get("spread_ig", 0.0), 1), "unit": "bps"},
            {"factor": "fx", "value": round(detail.get("eurusd", 0.0) / ctx.fx_beta["eurusd"], 5) if ctx.fx_beta["eurusd"] else 0.0, "unit": "pct"},
            {"factor": "commodities", "value": round(detail.get("oil", 0.0), 5), "unit": "pct"},
            {"factor": "volatility", "value": round(vol, 4), "unit": "pct"}]


def build_scenarios(lib, ctx: Context, armed_ids: set) -> list:
    out = []
    for ev in lib.events:
        vals = event_values(ev)
        if vals["equity"] is None or vals["dgs10"] is None:
            continue
        detail = shocks_from_values(vals, ctx)
        vix = ev.paths.get("vix_pts", [[0, None]] * 5)[4][1] if "vix_pts" in ev.paths else None
        out.append({"id": ev.id, "name": ev.title, "eventType": ev.type,
                    "description": f"Applies the realised 5-day market moves after this event ({ev.date.isoformat()}) to today's book.",
                    "shocks": scenario_ui_shocks(detail, ctx, vix, ev.vix), "armed": ev.id in armed_ids})
    return out


def reverse_stress(lib, ctx: Context, watch: set) -> list:
    by_type = defaultdict(list)
    for ev in lib.events:
        by_type[ev.type].append(event_values(ev))
    base = total(ctx.book, ctx.state)
    rows = []
    for et, vs in by_type.items():
        med = {}
        for k in ("equity", "oil", "hyg", "lqd", "uup", "dgs2", "dgs10"):
            xs = [v[k] for v in vs if v.get(k) is not None]
            med[k] = float(np.median(xs)) if xs else None
        if med["equity"] is None or med["dgs10"] is None:
            continue
        loss = base - total(ctx.book, apply_shocks(ctx.state, shocks_from_values(med, ctx)))
        rows.append({"eventType": et, "loss": float(loss), "lossPct": float(loss / abs(base)) if base else 0.0,
                     "onWatchlist": et in watch})
    return sorted(rows, key=lambda r: -r["loss"])


def worst_shock(ctx: Context, target_loss_pct: float) -> dict:
    """Smallest shock (in units of each factor's own 5-day volatility) that loses `target_loss_pct` of the book value."""
    base = total(ctx.book, ctx.state)
    sigma = {c: float(ctx.hist[c].std() * math.sqrt(5)) for c in FACTORS}
    grad = {}
    for c in FACTORS:
        up = total(ctx.book, apply_shocks(ctx.state, {c: sigma[c]}))
        grad[c] = base - up                                   # loss per one-sigma move of factor c
    norm = math.sqrt(sum(g * g for g in grad.values())) or 1.0
    target = target_loss_pct / 100.0 * abs(base)
    lam = target / norm
    for _ in range(6):
        shock = {c: lam * grad[c] / norm * sigma[c] for c in FACTORS}
        loss = base - total(ctx.book, apply_shocks(ctx.state, shock))
        if loss <= 0:
            break
        lam *= target / loss
    shock = {c: lam * grad[c] / norm * sigma[c] for c in FACTORS}
    loss = base - total(ctx.book, apply_shocks(ctx.state, shock))
    return {"targetLossPct": target_loss_pct, "achievedLossPct": float(loss / abs(base) * 100), "shock": shock,
            "sigmaMultiple": {c: float(shock[c] / sigma[c]) if sigma[c] else 0.0 for c in FACTORS}}
