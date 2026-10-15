"""Exposure analytics: where the book's value sits, and what one standard bump of each risk factor does to it."""
from __future__ import annotations

from collections import defaultdict

from .pricing import apply_shocks, total, value

# one-unit bumps: DV01 / CS01 style for rates and spreads, 1% for equity, FX and oil
BUMPS = [("equity", "equity", -0.01, "pct", "-1% equity"), ("rates", "rates_10y", 1.0, "bps", "+1bp 10y yield"),
         ("rates_curve", None, 1.0, "bps", "+1bp parallel curve"), ("credit_spread_ig", "spread_ig", 1.0, "bps", "+1bp IG spread"),
         ("credit_spread_hy", "spread_hy", 1.0, "bps", "+1bp HY spread"), ("eurusd", "eurusd", -0.01, "pct", "-1% EUR/USD"),
         ("gbpusd", "gbpusd", -0.01, "pct", "-1% GBP/USD"), ("oil", "oil", -0.01, "pct", "-1% oil")]


def _group(book: list, st, key) -> list:
    mv, notional = defaultdict(float), defaultdict(float)
    for h in book:
        k = key(h)
        mv[k] += value(h, st)
        notional[k] += abs(h["notional"])
    tot = sum(abs(v) for v in mv.values()) or 1.0
    return sorted(({"key": k, "marketValue": float(mv[k]), "notional": float(notional[k]), "pct": float(abs(mv[k]) / tot)}
                   for k in mv), key=lambda x: -abs(x["marketValue"]))


def factor_sensitivities(book: list, st) -> list:
    base = total(book, st)
    out = []
    for name, col, size, unit, label in BUMPS:
        shock = ({"rates_2y": size, "rates_5y": size, "rates_10y": size, "rates_30y": size} if col is None else {col: size})
        out.append({"factor": name, "bump": label, "unit": unit, "pnl": float(total(book, apply_shocks(st, shock)) - base)})
    return out


def exposure(book: list, st) -> dict:
    return {
        "asof": st.asof.isoformat(), "totalMarketValue": float(total(book, st)),
        "bySector": _group(book, st, lambda h: h["sector"]),
        "byCountry": _group(book, st, lambda h: h["country"]),
        "byRating": _group(book, st, lambda h: h["rating"] or "NR"),
        "byAssetClass": _group(book, st, lambda h: h["asset_type"]),
        "topCounterparties": _group(book, st, lambda h: h["counterparty"])[:10],
        "factorSensitivities": factor_sensitivities(book, st),
    }
