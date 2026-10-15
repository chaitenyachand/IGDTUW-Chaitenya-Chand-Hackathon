"""Price and macro series access, and event-window helpers. Everything is computed from stored real data."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd


def _start(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


async def load_prices(pool, symbols, start: str = "1999-01-01") -> pd.DataFrame:
    rows = await pool.fetch(
        "SELECT symbol, ts, COALESCE(adj_close, close) AS v FROM prices WHERE symbol = ANY($1) AND ts >= $2 ORDER BY ts",
        list(symbols), _start(start))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([(r["symbol"], r["ts"].date(), r["v"]) for r in rows], columns=["symbol", "d", "v"])
    out = df.pivot(index="d", columns="symbol", values="v")
    out.index = pd.to_datetime(out.index)
    return out.sort_index()


async def load_macro(pool, series_ids, start: str = "1999-01-01") -> pd.DataFrame:
    rows = await pool.fetch("SELECT series_id, ts, value FROM macro_series WHERE series_id = ANY($1) AND ts >= $2 ORDER BY ts",
                            list(series_ids), _start(start))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([(r["series_id"], r["ts"].date(), r["value"]) for r in rows], columns=["series", "d", "v"])
    out = df.pivot(index="d", columns="series", values="v")
    out.index = pd.to_datetime(out.index)
    return out.sort_index()


def forward_path(s: pd.Series, reaction, horizon: int = 30, max_gap_days: int = 6):
    """Cumulative return from the close before the reaction day: [(k, ret)], k = 0..horizon. None if data is missing."""
    s = s.dropna()
    reaction = pd.Timestamp(reaction)
    if s.empty:
        return None
    pos = int(s.index.searchsorted(reaction))
    if pos < 1 or pos + horizon >= len(s):
        return None
    if (s.index[pos] - reaction).days > max_gap_days or (reaction - s.index[pos - 1]).days > 10:
        return None
    base = float(s.iloc[pos - 1])
    return [(k, float(s.iloc[pos + k] / base - 1.0)) for k in range(horizon + 1)]


def level_path(s: pd.Series, reaction, horizon: int = 30, scale: float = 1.0, max_gap_days: int = 6):
    """Change in a level series (yield %, VIX points) from the day before the reaction day, times `scale`."""
    s = s.dropna()
    reaction = pd.Timestamp(reaction)
    if s.empty:
        return None
    pos = int(s.index.searchsorted(reaction))
    if pos < 1 or pos + horizon >= len(s):
        return None
    if (s.index[pos] - reaction).days > max_gap_days:
        return None
    base = float(s.iloc[pos - 1])
    return [(k, float((s.iloc[pos + k] - base) * scale)) for k in range(horizon + 1)]


def path_stats(path):
    """(max drawdown = lowest cumulative return, days until it first recovers to >= 0 after the trough or None)."""
    rets = [r for _, r in path]
    k_min = int(np.argmin(rets))
    rec = next((k for k in range(k_min + 1, len(rets)) if rets[k] >= 0), None)
    return float(min(rets)), rec


def abs_window_returns(s: pd.Series, days: int = 5) -> np.ndarray:
    """|cumulative return| over every rolling `days`-day window: the unconditional reference distribution."""
    s = s.dropna()
    return np.abs((s.shift(-days) / s - 1.0).dropna().values)
