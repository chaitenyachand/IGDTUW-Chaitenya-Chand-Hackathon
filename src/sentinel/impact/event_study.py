"""Event study: abnormal returns around SEC 8-K filings, from real prices (market model against SPY)."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..nlp.lexicon import EDGAR_ITEM_EVENT

PRIORITY = ["Credit Event", "Cyber", "Merger/Acquisition", "Regulatory", "Earnings"]
ET = ZoneInfo("America/New_York")


def classify_items(items: list) -> str:
    types = {EDGAR_ITEM_EVENT[i] for i in items if i in EDGAR_ITEM_EVENT}
    return next((p for p in PRIORITY if p in types), "Other 8-K")


def parse_filings(arr: dict, ticker: str) -> list:
    """Rows from one SEC submissions array block (works for 'recent' and for the older archive files)."""
    out = []
    forms = arr.get("form") or []
    for i, form in enumerate(forms):
        if form not in ("8-K", "8-K/A"):
            continue
        try:
            filed = datetime.fromisoformat(arr["acceptanceDateTime"][i].replace("Z", "+00:00"))
        except (KeyError, ValueError, IndexError):
            continue
        items = [x.strip() for x in ((arr.get("items") or [""] * len(forms))[i] or "").split(",") if x.strip()]
        out.append({"id": arr["accessionNumber"][i], "ticker": ticker, "filed_at": filed, "form": form,
                    "items": items, "event_type": classify_items(items)})
    return out


def reaction_day(filed_at: datetime) -> pd.Timestamp:
    """Filings after the 4pm ET close (or on weekends) can only be priced in the next session."""
    et = filed_at.astimezone(ET)
    d = et.date()
    if et.hour >= 16 or et.weekday() >= 5:
        d = d + timedelta(days=1)
    return pd.Timestamp(d)


def event_study(stock: pd.Series, market: pd.Series, reaction, est_window: int = 250, gap: int = 30,
                min_obs: int = 120, car_days: int = 3):
    """Cumulative abnormal return over `car_days` from a market model fitted on the window ending `gap` days before."""
    df = pd.concat([stock.pct_change(), market.pct_change()], axis=1, keys=["s", "m"]).dropna()
    reaction = pd.Timestamp(reaction)
    pos = int(df.index.searchsorted(reaction))
    if pos - gap - min_obs < 0 or pos + car_days > len(df) or (df.index[pos] - reaction).days > 6:
        return None
    est = df.iloc[max(0, pos - gap - est_window): pos - gap]
    if len(est) < min_obs:
        return None
    beta, alpha = np.polyfit(est["m"].values, est["s"].values, 1)
    win = df.iloc[pos: pos + car_days]
    ar = win["s"] - (alpha + beta * win["m"])
    pre = df["s"].iloc[max(0, pos - 60): pos]
    return {"car3": float(ar.sum()), "ar1": float(ar.iloc[0]), "beta": float(beta), "vol60": float(pre.std()),
            "prior_abs": float(abs(df["s"].iloc[pos - 1]))}
