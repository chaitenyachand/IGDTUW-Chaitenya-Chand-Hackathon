"""Noise filters for social text: adult content, gibberish, and automated / promotional posts."""
from __future__ import annotations

import re

ADULT_RX = re.compile(r"\b(?:nsfw|kinks?|fetish|porn|onlyfans|erotic|lewd|hentai)\b", re.I)
ADULT_LABELS = {"porn", "sexual", "nudity", "graphic-media"}   # Bluesky self-labels

AUTOMATED_RX = re.compile("|".join([
    r"filed a notice of intent to sell", r"trading halted for", r"volatility trading pause",
    r"get future buy/sell signals", r"signals the moment they fire", r"\bsold:\s?[\d,]+ shares",
    r"\bbought:\s?[\d,]+ shares", r"\b(?:win|loss):\s+\w+\s+(?:long|short)\b", r"link in bio",
    r"\bfree (?:signals|alerts)\b",
    r"\(insider\) reported", r"insider (?:selling|buying) \d+ insiders?", r"\bliquidated on\b",
    r"initial filing analysis", r"\b(?:buy|sell)(?:_on_confirmation)?\s+\$\w+.*@\s*\d\d:\d\d",
    r"\[\w+\]\s*@\s*\d\d:\d\d:\d\dz",
]), re.I)

_SYMBOLS = set("$*[]<>\\+()/,;%^&=|~#@{}")


def is_adult(text: str) -> bool:
    return bool(ADULT_RX.search(text))


def is_automated(text: str) -> bool:
    return bool(AUTOMATED_RX.search(text))


def is_gibberish(text: str) -> bool:
    t = text.strip()
    if len(t) < 15 or "http" in t.lower():
        return False
    if len(t.split()) <= 2:
        return True                      # one long token with no words, e.g. random characters
    return sum(c in _SYMBOLS for c in t) / len(t) > 0.3
