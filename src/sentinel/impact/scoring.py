"""Impact, half-life and book impact for a signal. Everything is derived from stored real history; nulls are kept null."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..market.series import abs_window_returns, load_prices
from ..portfolio.pricing import MarketDataMissing, apply_shocks, total, value
from ..precedent.engine import Library, aggregate, half_life_days, spy_abs_move
from ..stress.engine import Context, aggregate_values, event_values, load_context, shocks_from_values
from ..taxonomy import EVENT_TYPES
from ..universe import UNIVERSE
from .kernel import expected_move, percentile_impact
from .model import impact_from_pred, predict_abs_car

UNIVERSE_TICKERS = {s.ticker for s in UNIVERSE}
REFRESH_SECONDS = 600


class ImpactEngine:
    def __init__(self, lib: Library, art, prices, ctx: Context | None, spy_ref, a0: float):
        self.lib, self.art, self.prices, self.ctx, self.spy_ref, self.a0 = lib, art, prices, ctx, spy_ref, a0
        self.loss_ref = self._library_losses()
        self.loaded_at = time.time()

    @classmethod
    async def load(cls, pool, path: str = "models/impact_v1.joblib"):
        import joblib
        lib = await Library.load(pool)
        art = joblib.load(path) if os.path.exists(path) else None
        px = await load_prices(pool, sorted(UNIVERSE_TICKERS) + ["SPY", "^VIX"], "1999-01-01")
        if "SPY" not in px:
            raise MarketDataMissing("no SPY prices: run `make prices`")
        spy_ref = np.sort(abs_window_returns(px["SPY"], 5))
        try:
            ctx = await load_context(pool)
        except MarketDataMissing:
            ctx = None
        return cls(lib, art, px, ctx, spy_ref, float(np.median(spy_ref)))

    @property
    def version(self) -> str:
        m = (self.art or {}).get("version", "kernel-only")
        t = ((self.art or {}).get("trained_at") or "")[:10]
        return f"lib{len(self.lib)}-{m}-{t}-book{int(self.ctx is not None)}"

    @property
    def vix_now(self):
        return self.vix_at(None)

    def vix_at(self, asof):
        """VIX close strictly before the day of `asof` (point-in-time); latest when asof is None."""
        s = self.prices["^VIX"].dropna() if "^VIX" in self.prices else None
        if s is None or not len(s):
            return None
        if asof is not None:
            s = s[s.index < pd.Timestamp(asof.date())]
        return float(s.iloc[-1]) if len(s) else None

    def _library_losses(self) -> np.ndarray:
        if self.ctx is None:
            return np.array([])
        base = total(self.ctx.book, self.ctx.state)
        losses = []
        for ev in self.lib.events:
            v = event_values(ev)
            if v["equity"] is None or v["dgs10"] is None:
                continue
            losses.append(base - total(self.ctx.book, apply_shocks(self.ctx.state, shocks_from_values(v, self.ctx))))
        return np.sort(np.array([x for x in losses if x > 0]))

    def company_features(self, ticker: str, asof=None):
        if ticker not in self.prices or "SPY" not in self.prices:
            return None
        px = self.prices[[ticker, "SPY"]]
        if asof is not None:                                   # point-in-time: only history before the signal's day
            px = px[px.index < pd.Timestamp(asof.date())]
        r = px.pct_change().dropna()
        if len(r) < 260:
            return None
        beta = float(np.polyfit(r["SPY"].values[-250:], r[ticker].values[-250:], 1)[0])
        return {"vol60": float(r[ticker].values[-60:].std()), "prior_abs": float(abs(r[ticker].values[-1])), "beta": beta}

    def enrich(self, sig: dict, emb) -> dict:
        out = {"impact": None, "impactBasis": None, "halfLifeDays": None, "bookImpact": None, "affectedHoldings": []}
        et = sig["eventType"]
        ticker = sig.get("ticker")
        asof = datetime.fromisoformat(sig["ts"]) if sig.get("ts") else datetime.now(timezone.utc)
        vix = self.vix_at(asof)
        analogs = (self.lib.match(np.asarray(emb, dtype=float), et if et in EVENT_TYPES else None, vix, before=asof.date())
                   if len(self.lib) else [])
        agg = aggregate(analogs) if analogs else None
        pred = None
        if ticker in UNIVERSE_TICKERS and self.art and self.art.get("model") is not None:
            f = self.company_features(ticker, asof)
            if f:
                pred = predict_abs_car(self.art, et, f["vol60"], vix, f["prior_abs"], f["beta"])
                out["impact"], out["impactBasis"] = impact_from_pred(self.art, pred), "company_model"
        if out["impact"] is None and analogs:
            a = [(s, spy_abs_move(ev)) for s, ev in analogs if spy_abs_move(ev) is not None]
            if a:
                out["impact"] = percentile_impact(expected_move(a, self.a0), self.spy_ref)
                out["impactBasis"] = "precedent_kernel"
        if agg:
            out["halfLifeDays"] = half_life_days(agg["series"])
        if out["impact"] is None:
            out["impactBasis"] = "no_library" if not len(self.lib) else "no_analogs"
        if self.ctx is not None and out["impact"] is not None:
            out.update(self._book_impact(sig, agg, pred, out["impact"]))
        return out

    def _book_impact(self, sig: dict, agg, pred, impact: float) -> dict:
        ctx = self.ctx
        ticker = sig.get("ticker")
        if ticker in UNIVERSE_TICKERS and pred is not None:        # company event: exposure to this counterparty
            held = [h for h in ctx.book if h["ticker"] == ticker]
            gross: dict = {}
            for h in ctx.book:
                gross[h["counterparty"]] = gross.get(h["counterparty"], 0.0) + abs(h["notional"])
            if not held:
                return {"bookImpact": 1.0, "affectedHoldings": []}
            mine = gross[held[0]["counterparty"]]
            pct = float(np.mean([mine >= g for g in gross.values()]))
            sign = 1.0 if sig["sentiment"] < 0 else 0.0                 # indicative: full pass-through of the predicted move
            aff = sorted(({"holdingId": h["id"], "estLoss": float(abs(value(h, ctx.state)) * pred * sign)} for h in held),
                         key=lambda x: -x["estLoss"])[:5]
            return {"bookImpact": round(1.0 + (impact - 1.0) * pct, 2), "affectedHoldings": aff}
        if agg is None or len(self.loss_ref) == 0:
            return {}
        detail = shocks_from_values(aggregate_values(agg), ctx)
        st2 = apply_shocks(ctx.state, detail)
        loss = total(ctx.book, ctx.state) - total(ctx.book, st2)
        bi = 1.0 if loss <= 0 else percentile_impact(loss, self.loss_ref)
        deltas = sorted(({"holdingId": h["id"], "estLoss": float(value(h, ctx.state) - value(h, st2))} for h in ctx.book),
                        key=lambda x: -x["estLoss"])
        return {"bookImpact": bi, "affectedHoldings": [d for d in deltas if d["estLoss"] > 0][:5]}

    async def refresh_if_stale(self, pool) -> bool:
        if time.time() - self.loaded_at < REFRESH_SECONDS:
            return False
        fresh = await ImpactEngine.load(pool)
        self.__dict__.update(fresh.__dict__)
        return True
