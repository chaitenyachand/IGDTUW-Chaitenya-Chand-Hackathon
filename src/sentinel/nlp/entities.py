"""Entity linking: map text to the index universe (companies) and macro institutions."""
from __future__ import annotations

import re

from ..universe import UNIVERSE
from .lexicon import MARKET_RX

# Names that are also everyday words need a finance/tech cue in the text before we link them.
AMBIGUOUS = {"apple", "amazon", "goldman", "caterpillar", "alphabet"}
CUE_RX = re.compile(
    r"\b(?:stock|stocks|shares|earnings|iphone|ipad|app store|aws|cloud|prime|bank|banking|wall street|analysts?|"
    r"investors?|ceo|profit|revenue|nasdaq|market|quarter|antitrust|lawsuit|tariff|equipment|machinery|mining|"
    r"dividend|valuation|billion|million)\b", re.I)

INSTITUTIONS = {
    "Federal Reserve": r"federal reserve|\bthe Fed\b|\bFOMC\b",
    "European Central Bank": r"european central bank|(?-i:\bECB\b)",
    "Bank of England": r"bank of england|(?-i:\bBoE\b)",
    "Bank of Japan": r"bank of japan|(?-i:\bBoJ\b)",
    "Reserve Bank of India": r"reserve bank of india|(?-i:\bRBI\b)",
    "IMF": r"international monetary fund|(?-i:\bIMF\b)",
    "World Bank": r"world bank",
    "OPEC": r"(?-i:\bOPEC\b)\+?",
    "US Treasury": r"u\.?s\.? treasury|treasury department",
}
_INST_RX = {k: re.compile(v, re.I) for k, v in INSTITUTIONS.items()}

_COMPANY_RX = {}
for s in UNIVERSE:
    alts = sorted({a for a in s.aliases} | {s.name.rstrip(".")}, key=len, reverse=True)
    _COMPANY_RX[s.ticker] = re.compile(r"(?<![\w])(?:" + "|".join(map(re.escape, alts)) + r")(?![\w])", re.I)
_BY_TICKER = {s.ticker: s for s in UNIVERSE}


_URL_RX = re.compile(
    r"(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|io|co|uk|gov|edu|google|ly|me|tv)(?:/\S*)?", re.I)


def strip_urls(text: str) -> str:
    return _URL_RX.sub(" ", text)


def link_entities(text: str, source_name: str = "", meta: dict | None = None) -> list:
    meta = meta or {}
    text = strip_urls(text)
    found: dict = {}

    def add(key, name, ticker, kind, conf, evidence):
        if key not in found or conf > found[key]["confidence"]:
            found[key] = {"name": name, "ticker": ticker, "kind": kind, "confidence": conf, "evidence": evidence}

    # 1. structured evidence from the source itself
    t = meta.get("ticker")
    if t in _BY_TICKER:
        add(t, _BY_TICKER[t].name, t, "company", 1.0, "source_ticker")
    for tk in (meta.get("match") or {}).get("tickers", []):
        if tk in _BY_TICKER:
            add(tk, _BY_TICKER[tk].name, tk, "company", 0.9, "cashtag")
        else:
            add(tk, None, tk, "company", 0.6, "cashtag_external")

    # 2. GDELT organisation list, then free text
    orgs = " ; ".join(meta.get("organizations") or [])
    for tk, rx in _COMPANY_RX.items():
        if orgs and rx.search(orgs):
            add(tk, _BY_TICKER[tk].name, tk, "company", 0.8, "gdelt_organizations")
        m = rx.search(text)
        if m:
            if m.group(0).lower() in AMBIGUOUS and not CUE_RX.search(text):
                continue
            add(tk, _BY_TICKER[tk].name, tk, "company", 0.75, "text_match")

    # 3. macro institutions
    for name, rx in _INST_RX.items():
        if rx.search(text):
            add(name, name, None, "institution", 0.8, "text_match")

    return sorted(found.values(), key=lambda e: -e["confidence"])