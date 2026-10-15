"""The terminal's API types (frontend/src/api/types.ts) as a tiny schema language, so the backend can be checked against exactly
what the frontend reads. Extra keys are allowed (the frontend ignores them); missing keys, wrong types and bad enum values are errors."""
from __future__ import annotations


class Opt:                                   # value or null
    def __init__(self, s): self.s = s


class L:                                     # list of s
    def __init__(self, s): self.s = s


class Rec:                                   # object with arbitrary keys, all values s
    def __init__(self, s): self.s = s


class E:                                     # enum
    def __init__(self, *v): self.v = set(v)


class Part:                                  # object whose listed keys may be missing (TS optional properties)
    def __init__(self, d): self.d = d


S, N, B = "str", "num", "bool"


def check(v, s, path="$") -> list:
    err = []
    if isinstance(s, Opt):
        return [] if v is None else check(v, s.s, path)
    if s == S:
        return [] if isinstance(v, str) else [f"{path}: expected string, got {type(v).__name__} {v!r:.40}"]
    if s == N:
        return [] if isinstance(v, (int, float)) and not isinstance(v, bool) else [f"{path}: expected number, got {type(v).__name__} {v!r:.40}"]
    if s == B:
        return [] if isinstance(v, bool) else [f"{path}: expected boolean, got {type(v).__name__} {v!r:.40}"]
    if s is object:
        return []
    if isinstance(s, E):
        return [] if v in s.v else [f"{path}: {v!r} not in {sorted(s.v)}"]
    if isinstance(s, L):
        if not isinstance(v, list):
            return [f"{path}: expected array, got {type(v).__name__}"]
        for i, x in enumerate(v[:50]):
            err += check(x, s.s, f"{path}[{i}]")
        return err
    if isinstance(s, Rec):
        if not isinstance(v, dict):
            return [f"{path}: expected object, got {type(v).__name__}"]
        for k, x in v.items():
            err += check(x, s.s, f"{path}.{k}")
        return err
    if isinstance(s, Part):
        if not isinstance(v, dict):
            return [f"{path}: expected object, got {type(v).__name__}"]
        for k, sub in s.d.items():
            if k in v:
                err += check(v[k], sub, f"{path}.{k}")
        return err
    if isinstance(s, dict):
        if not isinstance(v, dict):
            return [f"{path}: expected object, got {type(v).__name__}"]
        for k, sub in s.items():
            if k not in v:
                err.append(f"{path}.{k}: missing")
            else:
                err += check(v[k], sub, f"{path}.{k}")
        return err
    raise TypeError(s)


EVENT = E("Geopolitical", "Macroeconomic", "Credit Event", "Merger/Acquisition", "Product Launch", "Regulatory", "Supply Chain",
          "Cyber", "Natural Disaster", "Market Commentary", "Earnings")
ASSET = E("equity_index", "energy", "financials", "technology", "health_care", "industrials", "utilities", "staples", "discretionary",
          "communication", "banks", "long_treasury", "mid_treasury", "high_yield", "inv_grade", "dollar", "oil", "gold", "volatility")
SOURCE = E("live", "replay", "backfill", "synthetic")
PT = {"day": N, "ret": N}

META = {"source": SOURCE, "asOf": S}
ENVELOPE = {"data": object, "meta": META}

SIGNAL = {"id": S, "ts": S, "mode": E("live", "replay", "backfill"), "entity": S, "ticker": Opt(S), "headline": S, "text": S,
          "sourceType": E("news", "social"), "sourceName": S, "url": S, "sentiment": N, "eventType": EVENT,
          "secondaryEventType": Opt(EVENT), "impact": Opt(N), "bookImpact": Opt(N), "confidence": N, "halfLifeDays": Opt(N),
          "integrity": {"score": N, "corroboratedBy": L(S), "flags": L(E("single_source", "burst", "bot_likely", "divergence"))},
          "explanation": L({"token": S, "weight": N}), "affectedHoldings": L({"holdingId": S, "estLoss": N})}
RISK = {"value": N, "regime": E("Calm", "Elevated", "Stressed"), "updatedAt": S, "series": L({"ts": S, "value": N})}
PRECEDENT = {"signalId": S, "status": E("pending", "ready", "insufficient_data"), "n": N, "dateRange": {"from": S, "to": S},
             "horizonDays": N,
             "analogs": L({"eventId": S, "title": S, "date": S, "similarity": N, "region": Opt(S), "maxDrawdown": N,
                           "recoveryDays": Opt(N), "paths": Rec(L(PT))}),
             "series": Rec({"n": N, "median": L(PT), "band": L({"day": N, "p10": N, "p90": N})}),
             "halfLifeDays": Opt(N), "shocks": L({"assetClass": ASSET, "median": N, "p10": N, "p90": N, "n": N})}
HOLDING = {"id": S, "assetType": E("Loan", "Bond", "Derivative"), "counterparty": S, "sector": S, "country": S, "notional": N,
           "marketValue": N, "rating": S, "maturity": S}
CONSTITUENT = {"ticker": S, "name": S, "sector": S, "benchmarkWeight": N, "currentWeight": N, "sentiment": Opt(N),
               "integrity": Opt(N), "price": Opt(N)}
INDEX_CONFIG = {"mode": E("auto", "approval"), "maxWeight": N, "minWeight": N, "maxTurnover": N, "sentimentThreshold": N,
                "requireCorroboration": B, "decay": B}
WEIGHTS = {"tickers": L(S), "points": L({"ts": S, "weights": Rec(N)})}
REBALANCE = {"id": S, "ts": S, "triggerSignalId": Opt(S), "triggerHeadline": Opt(S), "status": E("applied", "pending", "rejected"),
             "moves": L({"ticker": S, "from": N, "to": N})}
PERF = {"totalReturn": N, "trackingError": N, "turnover": N, "maxDrawdown": N, "informationRatio": Opt(N)}
PERFORMANCE = {"series": L({"ts": S, "benchmark": N, "tilted": N, "naive": N}), "stats": {"benchmark": PERF, "tilted": PERF, "naive": PERF}}
SHOCK = {"factor": S, "value": N, "unit": E("pct", "bps")}
SCENARIO = {"id": S, "name": S, "eventType": Opt(EVENT), "description": S, "shocks": L(SHOCK), "armed": B}
RULE = {"id": S, "eventType": EVENT, "minImpact": N, "minIntegrity": Opt(N), "scenarioId": S, "enabled": B, "cooldownMinutes": N}
STRESS = {"scenarioId": S, "mode": E("calibrated", "manual"), "triggeredBySignalId": Opt(S), "ts": S, "valueBefore": N, "valueAfter": N,
          "varBefore": N, "varAfter": N, "esBefore": N, "esAfter": N, "byFactor": L({"factor": S, "delta": N}),
          "byAssetClass": L({"assetClass": E("Loan", "Bond", "Derivative"), "before": N, "after": N}),
          "bySector": L({"sector": S, "delta": N}), "byCountry": L({"country": S, "delta": N}), "narrative": S}
REVERSE = {"eventType": EVENT, "loss": N, "lossPct": N, "onWatchlist": B}
EXPOSURE = {"byCountry": L({"country": S, "exposure": N, "stressedLoss": N}), "bySector": L({"sector": S, "exposure": N, "stressedLoss": N}),
            "graph": {"nodes": L({"id": S, "label": S, "type": E("counterparty", "sector"), "notional": N}),
                      "edges": L({"source": S, "target": S, "weight": N})}}
ALERT = {"id": S, "ts": S, "severity": E("info", "warning", "critical"), "title": S, "message": S, "signalId": Opt(S)}
MODEL = {"modelVersion": Opt(S), "trainedAt": Opt(S), "sentiment": {"f1": Opt(N), "accuracy": Opt(N)},
         "event": {"macroF1": Opt(N), "labels": L(S), "confusion": L(L(N))}, "impact": {"spearman": Opt(N), "mae": Opt(N)},
         "calibration": {"ece": Opt(N), "bins": L({"predicted": N, "observed": N, "n": N})},
         "backtest": {"quintiles": L({"quintile": N, "meanForwardReturn": N, "n": N})},
         "drift": {"threshold": N, "series": L({"ts": S, "psi": N})},
         "latency": {"p50Ms": Opt(N), "p95Ms": Opt(N), "histogram": L({"bucketMs": N, "count": N})},
         "precedentValidation": {"maeVsNaive": Opt(N), "directionalHitRate": Opt(N), "bandCoverage": Opt(N)},
         "card": {"trainingData": L(S), "knownLimitations": L(S)}}
HEALTH = {"status": S, "documents": {"total": N, "lastHour": N, "latestPublishedAt": Opt(S)},
          "sources": L({"name": S, "enabled": B, "status": E("ok", "error", "disabled", "starting"), "lastSuccess": Opt(S),
                        "lastError": Opt(S), "itemsLastRun": N, "itemsTotal": N, "errorCount": N})}
AUDIT = {"id": S, "ts": S, "actor": E("system", "user"), "action": S, "summary": S, "payload": Rec(object), "hash": S, "prevHash": Opt(S)}
VERIFY = {"intact": B, "checked": N, "brokenAtId": Opt(S)}
DEMO = {"id": S, "title": S, "description": S, "eventDate": S, "eventType": EVENT}

# GET path -> schema of `data`
GET = {"/api/signals": L(SIGNAL), "/api/risk-index": RISK, "/api/portfolio": L(HOLDING), "/api/portfolio/exposure": EXPOSURE,
       "/api/index/constituents": L(CONSTITUENT), "/api/index/weights": WEIGHTS, "/api/index/rebalances": L(REBALANCE),
       "/api/index/performance": PERFORMANCE, "/api/index/config": INDEX_CONFIG, "/api/stress/scenarios": L(SCENARIO),
       "/api/stress/rules": L(RULE), "/api/stress/reverse": L(REVERSE), "/api/model/metrics": MODEL, "/api/health": HEALTH,
       "/api/alerts": L(ALERT), "/api/audit": L(AUDIT), "/api/audit/verify": VERIFY, "/api/demo/scenarios": L(DEMO)}
WS = {"signal": SIGNAL, "precedent_ready": {"signalId": S}, "risk_index": RISK, "rebalance": REBALANCE, "stress_run": STRESS, "alert": ALERT}
