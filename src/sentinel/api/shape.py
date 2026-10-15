"""Presentation layer: turns service results into exactly the shapes the SENTINEL terminal (frontend/src/api/types.ts) reads.
Pure functions, no I/O (except `risk_message`, which reads the hourly history it needs for the series). Nothing here invents data:
a value that has not been computed is null or absent, and the frontend types say so."""
from __future__ import annotations

from datetime import date, datetime, timezone

from .common import ApiError

SEVERITY = {"critical": "critical", "high": "warning", "medium": "warning", "warning": "warning", "info": "info"}
REFERENCE_SHOCK = {"equity": -0.10, "rates": 100.0, "credit_spread": 100.0}      # for the stressed-loss columns of /portfolio/exposure


def iso_day(d) -> str:
    """'2026-03-02' -> '2026-03-02T00:00:00Z'"""
    if isinstance(d, (datetime, date)):
        d = d.isoformat()[:10]
    return f"{d}T00:00:00Z"


# ---------------------------------------------------------------- risk index
def risk_index(cur: dict, hist: list) -> dict:
    if cur.get("status") != "ready" or cur.get("value") is None:
        raise ApiError(409, "insufficient_history",
                       f"The Global Risk Index is a percentile against the trailing history of hourly values; only {cur.get('baselinePoints', 0)} "
                       "hourly points exist so far. Run `make risk-backfill` or let the scheduler accumulate history.")
    return {"value": cur["value"], "regime": cur["regime"], "updatedAt": cur["asOf"],
            "series": [{"ts": h["ts"], "value": h["value"]} for h in hist if h.get("value") is not None],
            "raw": cur["raw"], "nSignals": cur["nSignals"], "components": cur["components"], "thresholds": cur["thresholds"],
            "windowHours": cur["windowHours"]}


# ---------------------------------------------------------------- portfolio
def exposure(ctx, loss_of) -> dict:
    """byCountry / bySector exposure (market value) and stressed loss under REFERENCE_SHOCK, plus a counterparty -> sector graph.
    `loss_of(holding)` returns that holding's loss (positive = loss) under the reference shock."""
    from ..portfolio.pricing import value
    st = ctx.state
    by = {"country": {}, "sector": {}}
    nodes_c, nodes_s, edges = {}, {}, {}
    for h in ctx.book:
        mv, loss = float(value(h, st)), float(loss_of(h))
        for k, key in (("country", h["country"]), ("sector", h["sector"])):
            e = by[k].setdefault(key, [0.0, 0.0])
            e[0] += abs(mv)
            e[1] += loss
        nodes_c[h["counterparty"]] = nodes_c.get(h["counterparty"], 0.0) + abs(float(h["notional"]))
        nodes_s[h["sector"]] = nodes_s.get(h["sector"], 0.0) + abs(float(h["notional"]))
        k2 = (h["counterparty"], h["sector"])
        edges[k2] = edges.get(k2, 0.0) + abs(float(h["notional"]))
    rows = lambda d, name: sorted(({name: k, "exposure": v[0], "stressedLoss": v[1]} for k, v in d.items()), key=lambda r: -r["exposure"])
    return {"byCountry": rows(by["country"], "country"), "bySector": rows(by["sector"], "sector"),
            "graph": {"nodes": [{"id": f"cp:{k}", "label": k, "type": "counterparty", "notional": v} for k, v in nodes_c.items()]
                              + [{"id": f"sec:{k}", "label": k, "type": "sector", "notional": v} for k, v in nodes_s.items()],
                      "edges": [{"source": f"cp:{c}", "target": f"sec:{s}", "weight": w} for (c, s), w in edges.items()]},
            "referenceShock": {"equity": REFERENCE_SHOCK["equity"], "ratesBps": REFERENCE_SHOCK["rates"],
                               "creditSpreadBps": REFERENCE_SHOCK["credit_spread"]}}


# ---------------------------------------------------------------- adaptive index
def constituents(rows: list) -> list:
    return [{"ticker": r["ticker"], "name": r["name"], "sector": r["sector"], "benchmarkWeight": r["benchmarkWeight"],
             "currentWeight": r["weight"], "sentiment": r["meanSentiment"], "integrity": r["meanIntegrity"], "price": r["price"],
             "activeWeight": r["activeWeight"], "signalScore": r["signalScore"], "signalCount": r["signalCount"]} for r in rows]


def weights(points: list, tickers: list) -> dict:
    return {"tickers": list(tickers), "points": [{"ts": p["ts"], "weights": p["weights"]} for p in points]}


def rebalance(ev: dict) -> dict:
    return {"id": ev["id"], "ts": ev["ts"], "triggerSignalId": ev["triggerSignalId"], "triggerHeadline": ev["triggerHeadline"],
            "status": ev["status"], "moves": [{"ticker": m["ticker"], "from": m["from"], "to": m["to"]} for m in ev["moves"]],
            "turnover": ev.get("turnover"), "decidedAt": ev.get("decidedAt")}


def _perf(m: dict) -> dict:
    return {"totalReturn": m["totalReturn"], "trackingError": m.get("trackingError", 0.0), "turnover": m["totalTurnover"],
            "maxDrawdown": m["maxDrawdown"], "informationRatio": m.get("informationRatio")}


def performance(res: dict) -> dict:
    if res.get("status") == "no_prices":
        raise ApiError(409, "no_prices", res["message"])
    mt = res["metrics"]
    return {"series": [{"ts": iso_day(r["date"]), "benchmark": r["benchmark"], "tilted": r["sentinel"], "naive": r["naive"]}
                       for r in res["series"]],
            "stats": {"benchmark": _perf(mt["benchmark"]), "tilted": _perf(mt["sentinel"]), "naive": _perf(mt["naive"])},
            "status": res["status"], "window": res.get("window"), "assumptions": res.get("assumptions"),
            "signalsUsed": res.get("signalsUsed")}


def index_config(cfg: dict) -> dict:
    """Backend config -> the terminal's IndexConfig (turnoverCap is called maxTurnover there); extra tuning knobs ride along."""
    out = {"mode": cfg["mode"], "maxWeight": cfg["maxWeight"], "minWeight": cfg["minWeight"], "maxTurnover": cfg["turnoverCap"],
           "sentimentThreshold": cfg["sentimentThreshold"], "requireCorroboration": cfg["requireCorroboration"], "decay": cfg["decay"]}
    out.update({k: cfg[k] for k in ("kappa", "deadband", "integrityThreshold", "defaultHalfLifeDays", "normalizer", "zFloor",
                                    "costBps", "lookbackDays")})
    return out


def index_config_patch(body: dict) -> dict:
    """Terminal / API names -> backend config keys."""
    p = dict(body)
    if "maxTurnover" in p:
        p["turnoverCap"] = p.pop("maxTurnover")
    return p


# ---------------------------------------------------------------- stress
def alert(a: dict) -> dict:
    return {"id": a["id"], "ts": a["ts"], "severity": SEVERITY.get(a["severity"], "warning"), "title": a["title"],
            "message": a["message"], "signalId": a.get("signalId")}


def reverse_rows(rows: list) -> list:
    return [{"eventType": r["eventType"], "loss": r["loss"], "lossPct": r["lossPct"], "onWatchlist": r["onWatchlist"]} for r in rows]


# ---------------------------------------------------------------- audit and demo
def audit_entry(e: dict) -> dict:
    return {**e, "actor": "user" if e["actor"] in ("user", "api") else "system"}


def audit_verify(v: dict) -> dict:
    fb = v.get("firstBroken")
    return {"intact": v["ok"], "checked": v["entries"], "brokenAtId": fb["id"] if fb else None, "headHash": v.get("headHash"),
            "firstBroken": fb}


def demo_scenario(e: dict) -> dict:
    return {"id": e["id"], "title": e["title"], "description": e["description"], "eventDate": e["start"][:10],
            "eventType": e["eventType"], "available": e["available"], "documents": e["documents"], "start": e["start"],
            "end": e["end"], "fetchCommand": e.get("fetchCommand")}


# ---------------------------------------------------------------- model lab
def _get(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict) or k not in d or d[k] is None:
            return default
        d = d[k]
    return d


def model_metrics(m: dict) -> dict:
    """Assemble the Model Lab payload from stored evaluation jobs. Anything whose job has not run is null / empty."""
    test = m.get("heldOutTest") or {}
    cal = m.get("calibration") or {}
    ev_cal = cal.get("event") or {}
    conf = ev_cal.get("confusion") or {}
    labels = conf.get("labels") or _get(test, "event", "classes", default=[])
    matrix = conf.get("matrix") or []
    if len(matrix) != len(labels):
        matrix = []                                          # a matrix appears only when the calibration job produced one that fits
    imp = m.get("impact") if isinstance(m.get("impact"), dict) else {}
    pv = m.get("precedentValidation") or {}
    bt = m.get("signalBacktest") or {}
    quint = _get(bt, "bySentiment", "quintiles", default=[]) if bt.get("status") == "ready" else []
    lat = m.get("latency") or {}
    ds = m.get("driftSeries") or {}
    card = m.get("modelCard") or {}
    art_t = next((c.get("trainedAt") for c in card.get("components", []) if c.get("trainedAt")), None)
    return {
        "modelVersion": m.get("modelVersion"),
        "trainedAt": art_t,
        "sentiment": {"f1": _get(test, "sentiment", "macro_f1"), "accuracy": _get(test, "sentiment", "accuracy")},
        "event": {"macroF1": _get(test, "event", "learned", "macro_f1"), "labels": labels, "confusion": matrix},
        "impact": {"spearman": imp.get("spearman"), "mae": imp.get("mae")},
        "calibration": {"ece": ev_cal.get("ece"),
                        "bins": [{"predicted": c["meanConfidence"], "observed": c["accuracy"], "n": c["n"]} for c in ev_cal.get("curve", [])]},
        "backtest": {"quintiles": [{"quintile": q["quintile"], "meanForwardReturn": q["meanCar3"], "n": q["n"]} for q in quint]},
        "drift": {"threshold": ds.get("threshold", 0.25), "series": ds.get("series", [])},
        "latency": {"p50Ms": None if lat.get("p50Sec") is None else lat["p50Sec"] * 1000.0,
                    "p95Ms": None if lat.get("p95Sec") is None else lat["p95Sec"] * 1000.0,
                    "histogram": [{"bucketMs": h["bucketMs"], "count": h["count"]} for h in lat.get("histogram", [])]},
        "precedentValidation": {"maeVsNaive": pv.get("maeVsNaive"), "directionalHitRate": pv.get("directionalHitRate"),
                                "bandCoverage": pv.get("bandCoverage")},
        "card": {"trainingData": card.get("trainingData", []), "knownLimitations": card.get("knownLimitations", [])},
        "pipeline": m.get("pipeline"), "components": card.get("components", []),
    }


# ---------------------------------------------------------------- websocket
async def ws_data(pool, msg_type: str, data: dict, source: str) -> dict | None:
    """The data member of a pushed message in the shape the terminal expects, or None when the message must not be sent."""
    if msg_type == "rebalance":
        return rebalance(data)
    if msg_type == "alert":
        return alert(data)
    if msg_type == "risk_index":
        if data.get("value") is None or data.get("status") not in (None, "ready"):
            return None
        from ..risk import index as risk_idx
        return {"value": data["value"], "regime": data["regime"], "updatedAt": data["asOf"],
                "series": [{"ts": h["ts"], "value": h["value"]} for h in await risk_idx.history(pool, source, 72) if h["value"] is not None]}
    return data
