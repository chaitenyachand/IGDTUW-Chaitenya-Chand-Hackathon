"""Module A math: per-ticker signal score, tilt, and the constraints (caps, deadband, turnover cap). Pure functions.

S_i(t) = sum_k sentiment_k x integrity_k x confidence_k x 2^(-age_k / halfLife_k) / normalizer
w_i    = benchmark_i x exp(kappa x z_i), z = cross-sectionally standardised S, then caps -> deadband -> turnover cap.

Effective bounds per name are [min(minWeight, bench_i), max(maxWeight, bench_i)], so a zero signal reproduces the
benchmark exactly even when a large benchmark weight sits above the cap.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np

DEFAULT_CONFIG = {
    "mode": "auto",                  # auto: apply at once | approval: park as pending until approved or rejected
    "kappa": 0.35,                   # tilt strength
    "minWeight": 0.02, "maxWeight": 0.15,
    "deadband": 0.0025,              # ignore per-name weight moves smaller than this
    "turnoverCap": 0.05,             # maximum one-way turnover per rebalance
    "integrityThreshold": 0.5,       # signals below this integrity score are ignored
    "requireCorroboration": False,   # when true, a signal needs at least one independent corroborating source
    "sentimentThreshold": 0.0,       # signals with |sentiment| below this are ignored
    "decay": True,                   # false: signals do not lose weight with age (they still leave the lookback window)
    "defaultHalfLifeDays": 2.0,      # used when a signal has no PRECEDENT half-life
    "normalizer": 1.0,
    "zFloor": 0.05,                  # standard deviation floor: when every signal is tiny, z stays small
    "costBps": 5.0,                  # transaction-cost assumption for the performance comparison
    "lookbackDays": 14.0,
}
MODES = ("auto", "approval")


def validate_config(cfg: dict, n: int) -> dict:
    """Return a cleaned config or raise ValueError."""
    out = {**DEFAULT_CONFIG, **{k: v for k, v in cfg.items() if k in DEFAULT_CONFIG}}
    if out["mode"] not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    for k in ("kappa", "deadband", "normalizer", "zFloor", "costBps", "lookbackDays", "defaultHalfLifeDays"):
        out[k] = float(out[k])
        if out[k] < 0:
            raise ValueError(f"{k} must be >= 0")
    if out["normalizer"] <= 0 or out["defaultHalfLifeDays"] <= 0 or out["lookbackDays"] <= 0:
        raise ValueError("normalizer, defaultHalfLifeDays and lookbackDays must be > 0")
    out["minWeight"], out["maxWeight"] = float(out["minWeight"]), float(out["maxWeight"])
    if not (0.0 <= out["minWeight"] < out["maxWeight"] <= 1.0):
        raise ValueError("need 0 <= minWeight < maxWeight <= 1")
    if n * out["minWeight"] > 1.0 + 1e-12 or n * out["maxWeight"] < 1.0 - 1e-12:
        raise ValueError(f"caps are infeasible for {n} constituents")
    out["turnoverCap"] = float(out["turnoverCap"])
    if not (0.0 < out["turnoverCap"] <= 1.0):
        raise ValueError("turnoverCap must be in (0, 1]")
    out["integrityThreshold"] = float(out["integrityThreshold"])
    if not (0.0 <= out["integrityThreshold"] <= 1.0):
        raise ValueError("integrityThreshold must be in [0, 1]")
    out["requireCorroboration"] = bool(out["requireCorroboration"])
    out["decay"] = bool(out["decay"])
    out["sentimentThreshold"] = float(out["sentimentThreshold"])
    if not (0.0 <= out["sentimentThreshold"] <= 1.0):
        raise ValueError("sentimentThreshold must be in [0, 1]")
    return out


def bounds(bench: np.ndarray, cfg: dict):
    return np.minimum(cfg["minWeight"], bench), np.maximum(cfg["maxWeight"], bench)


def signal_scores(signals: list, now: datetime, cfg: dict, tickers: list) -> tuple:
    """-> (scores array aligned with `tickers`, counts array). `signals`: dicts with ts, ticker, sentiment, confidence,
    halfLifeDays and integrity {score, corroboratedBy}. Signals dated after `now` are ignored (point-in-time)."""
    pos = {t: i for i, t in enumerate(tickers)}
    s, cnt = np.zeros(len(tickers)), np.zeros(len(tickers), dtype=int)
    for g in signals:
        i = pos.get(g.get("ticker"))
        if i is None:
            continue
        integ = g["integrity"]
        if integ["score"] < cfg["integrityThreshold"]:
            continue
        if cfg["requireCorroboration"] and not integ.get("corroboratedBy"):
            continue
        if abs(g["sentiment"]) < cfg["sentimentThreshold"]:
            continue
        age = (now - g["ts"]).total_seconds() / 86400.0
        if age < 0:
            continue
        hl = g.get("halfLifeDays") or cfg["defaultHalfLifeDays"]
        fade = 2.0 ** (-age / hl) if cfg["decay"] else 1.0
        s[i] += g["sentiment"] * integ["score"] * g["confidence"] * fade
        cnt[i] += 1
    return s / cfg["normalizer"], cnt


def zscores(scores: np.ndarray, floor: float) -> np.ndarray:
    sd = max(float(np.std(scores)), floor)
    return (scores - float(np.mean(scores))) / sd


def project(w: np.ndarray, lo: np.ndarray, hi: np.ndarray, free: np.ndarray | None = None) -> np.ndarray:
    """Shift `w` by a common amount (only on `free` names) and clip to [lo, hi] so that it sums to exactly 1."""
    free = np.ones(len(w), dtype=bool) if free is None else free

    def total(lam):
        return float(np.sum(np.clip(w - lam * free, lo, hi)))
    a, b = -2.0, 2.0
    if total(a) < 1.0 or total(b) > 1.0:                   # the free names cannot absorb the difference: use all names
        if free.all():
            return np.clip(w, lo, hi) / max(float(np.clip(w, lo, hi).sum()), 1e-12)
        return project(w, lo, hi, None)
    for _ in range(80):
        m = (a + b) / 2
        if total(m) > 1.0:
            a = m
        else:
            b = m
    return np.clip(w - ((a + b) / 2) * free, lo, hi)


def tilt_target(bench: np.ndarray, z: np.ndarray, cfg: dict) -> np.ndarray:
    raw = bench * np.exp(cfg["kappa"] * z)
    raw = raw / raw.sum()
    lo, hi = bounds(bench, cfg)
    return project(raw, lo, hi)


def constrain(current: np.ndarray, target: np.ndarray, bench: np.ndarray, cfg: dict) -> np.ndarray:
    """Deadband then turnover cap. Returns `current` unchanged when no name moves by at least the deadband."""
    lo, hi = bounds(bench, cfg)
    moved = np.abs(target - current) >= cfg["deadband"]
    if not moved.any():
        return current.copy()
    cand = project(np.where(moved, target, current), lo, hi, moved)
    turn = 0.5 * float(np.abs(cand - current).sum())
    if turn > cfg["turnoverCap"]:
        cand = current + (cand - current) * (cfg["turnoverCap"] / turn)
    return cand


def turnover(a: np.ndarray, b: np.ndarray) -> float:
    return 0.5 * float(np.abs(np.asarray(a) - np.asarray(b)).sum())


def naive_target(bench: np.ndarray, signals: list, now: datetime, cfg: dict, tickers: list, hours: float = 24.0) -> np.ndarray:
    """The whipsaw baseline: mean sentiment of the last 24h per ticker, no integrity filter, no decay, no deadband,
    no turnover cap (caps still apply so the comparison is not about leverage)."""
    pos = {t: i for i, t in enumerate(tickers)}
    tot, cnt = np.zeros(len(tickers)), np.zeros(len(tickers))
    for g in signals:
        i = pos.get(g.get("ticker"))
        if i is None:
            continue
        age_h = (now - g["ts"]).total_seconds() / 3600.0
        if 0 <= age_h <= hours:
            tot[i] += g["sentiment"]
            cnt[i] += 1
    sc = np.divide(tot, cnt, out=np.zeros_like(tot), where=cnt > 0)
    z = zscores(sc, 1e-6) if np.any(cnt) else np.zeros(len(tickers))
    return tilt_target(bench, z, cfg)
