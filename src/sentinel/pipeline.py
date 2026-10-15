"""What happens to a signal after the NLP models have scored it (design section 14, steps 4 to 8).

    enrich (sync, cheap)  -> impact, half-life, book impact from the SEC event model and PRECEDENT analogs
    after  (post-commit)  -> precedent_ready, Module A recompute, Module B rules, Global Risk Index, audit entry

Live, replay and backfill signals run through exactly this code. The only difference is the clock: a replayed signal is
processed "as of" its own publication time, so nothing downstream ever sees the future (design principle 4).
Every step is isolated: a failure in one is logged and never stops scoring.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from .audit import ledger
from .config import settings
from .events import publish, publish_many
from .impact.scoring import ImpactEngine
from .index import service as index_service
from .portfolio.pricing import MarketDataMissing
from .precedent.engine import Library
from .precedent.service import precedent_for_signal
from .risk import index as risk_index
from .stress import service as stress_service
from .universe import UNIVERSE

log = logging.getLogger(__name__)
INDEX_TICKERS = {s.ticker for s in UNIVERSE}
RETRY_LOAD_SECONDS = 600
SIGNAL_DROP = ("entities", "sentimentProbs", "modelVersion")


def signal_message(sig: dict) -> dict:
    """The signal as published on the WebSocket (the API shape, without internal fields)."""
    return {k: v for k, v in sig.items() if k not in SIGNAL_DROP}


def _ts(sig: dict) -> datetime:
    return datetime.fromisoformat(sig["ts"])


class Pipeline:
    def __init__(self, pool, redis, impact: ImpactEngine | None = None, audit_min_impact: float | None = None,
                 impact_path: str = "models/impact_v1.joblib"):
        self.pool, self.redis, self.impact, self.impact_path = pool, redis, impact, impact_path
        self.stress = stress_service.RuntimeHolder(pool)
        self.audit_min_impact = settings.audit_min_impact if audit_min_impact is None else audit_min_impact
        self._lib: Library | None = None
        self._last_try = 0.0

    @classmethod
    async def create(cls, pool, redis, impact_path: str = "models/impact_v1.joblib", **kw):
        p = cls(pool, redis, None, impact_path=impact_path, **kw)
        await p.refresh(force=True)
        return p

    async def refresh(self, force: bool = False):
        """Load (or periodically reload) the impact engine. Without market data impact stays null: it is never invented."""
        if self.impact is not None:
            await self.impact.refresh_if_stale(self.pool)
            return
        if not force and time.time() - self._last_try < RETRY_LOAD_SECONDS:
            return
        self._last_try = time.time()
        try:
            self.impact = await ImpactEngine.load(self.pool, self.impact_path)
            log.info("impact engine loaded: %s", self.impact.version)
        except MarketDataMissing as e:
            log.warning("impact scoring disabled until market data exists: %s", e)
        except Exception:
            log.exception("impact engine failed to load")

    # ---- step 3/4: synchronous enrichment, before the signal is stored and published ----
    def enrich(self, sig: dict, emb) -> dict:
        if self.impact is None:
            sig["impactBasis"] = "no_market_data"
            return sig
        try:
            sig.update(self.impact.enrich(sig, emb))
            sig["modelVersion"] = f"{sig['modelVersion']}|{self.impact.version}"
        except Exception:
            log.exception("impact enrichment failed for %s", sig.get("id"))
            sig["impactBasis"] = "error"
        return sig

    # ---- steps 5 to 8: after the signals are committed and published ----
    async def after(self, sigs: list):
        groups: dict = {}
        for s in sigs:
            groups.setdefault(s.get("mode", "live"), []).append(s)
        for source, group in groups.items():
            if source == "backfill":                      # derived state for backfilled history is built by its own jobs
                continue
            now = max(_ts(s) for s in group) if source == "replay" else datetime.now(timezone.utc)
            for name, step in (("precedent", self._precedent), ("index", self._index), ("stress", self._stress),
                               ("risk", self._risk), ("audit", self._audit)):
                try:
                    await step(group, source, now)
                except Exception:
                    log.exception("pipeline step '%s' failed (%s, %d signals)", name, source, len(group))

    async def library(self) -> Library:
        if self.impact is not None:
            return self.impact.lib
        if self._lib is None:
            self._lib = await Library.load(self.pool)
        return self._lib

    async def _precedent(self, sigs, source, now):
        lib = await self.library()
        items = []
        for s in sigs:
            try:
                res, _ = await precedent_for_signal(self.pool, lib, s["id"])
            except KeyError:
                continue
            items.append(("precedent_ready", {"signalId": s["id"], "status": res["status"], "n": res["n"],
                                              "halfLifeDays": res["halfLifeDays"]}, source))
        await publish_many(self.redis, items)

    async def _index(self, sigs, source, now):
        cand = [s for s in sigs if s.get("ticker") in INDEX_TICKERS]
        if not cand:
            return
        trig = max(cand, key=lambda s: ((s.get("impact") or 0.0), abs(s["sentiment"])))
        await index_service.recompute(self.pool, self.redis, now=now, source=source,
                                      trigger={"id": trig["id"], "headline": trig["headline"]})

    async def _stress(self, sigs, source, now):
        for s in sigs:
            await stress_service.evaluate_rules(self.pool, self.redis, self.stress, s, source=source,
                                                now=_ts(s) if source == "replay" else None)

    async def _risk(self, sigs, source, now):
        await risk_index.update_and_publish(self.pool, self.redis, source, now)

    async def _audit(self, sigs, source, now):
        for s in sigs:
            if s.get("impact") is not None and s["impact"] >= self.audit_min_impact:
                await ledger.append(
                    self.pool, "pipeline", "signal",
                    f"{s['eventType']} signal on {s['entity']}: impact {s['impact']:.1f}",
                    {"signalId": s["id"], "entity": s["entity"], "eventType": s["eventType"], "impact": s["impact"],
                     "bookImpact": s.get("bookImpact"), "sentiment": s["sentiment"], "integrity": s["integrity"]["score"],
                     "impactBasis": s.get("impactBasis"), "source": source, "signalTs": s["ts"]})
