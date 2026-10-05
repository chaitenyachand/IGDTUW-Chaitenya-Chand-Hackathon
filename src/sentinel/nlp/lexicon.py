"""Transparent lexicons for the v0 rule baseline (relevance cues and weak event labels).

These are NOT the final models. Later phases train and evaluate sentiment / event / impact models on
labelled data; the lexicons bootstrap weak labels and gate obviously irrelevant text.
"""
from __future__ import annotations

import re


def _union(patterns):
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b", re.I)


EVENT_PATTERNS = {
    "Geopolitical": [r"sanctions?", r"sanctioned", r"embargo", r"war", r"invasion", r"invade[sd]?", r"missiles?",
                     r"air ?strikes?", r"cease-?fire", r"troops", r"military", r"nato", r"coup", r"geopolitical",
                     r"blockade", r"tariffs?", r"trade (?:war|talks|deal|dispute)", r"border clash(?:es)?", r"nuclear"],
    "Macroeconomic": [r"inflation", r"interest rates?", r"rate (?:cut|hike)s?", r"central bank", r"federal reserve",
                      r"fomc", r"ecb", r"gdp", r"recession", r"unemployment", r"jobs report", r"payrolls?", r"cpi",
                      r"bond yields?", r"treasury yields?", r"economic growth", r"stimulus", r"budget deficit", r"imf"],
    "Credit Event": [r"bankruptcy", r"chapter 11", r"insolvency", r"default(?:s|ed)?", r"downgrade[sd]?",
                     r"credit rating", r"restructuring", r"debt crisis", r"delist(?:ed|ing)?", r"write-?offs?",
                     r"npas?", r"non-performing", r"missed payment", r"bank run", r"liquidity crunch"],
    "Merger/Acquisition": [r"acquires?", r"acquired", r"acquisitions?", r"mergers?", r"takeover", r"buyout",
                           r"agrees to buy", r"spin-?off", r"divest(?:s|ed|iture)?", r"joint venture", r"ipo"],
    "Regulatory": [r"regulators?", r"regulatory", r"antitrust", r"probe", r"investigation", r"fined?", r"lawsuit",
                   r"sues?", r"sued", r"court", r"ruling", r"sec charges", r"compliance", r"legislation"],
    "Supply Chain": [r"supply chains?", r"shortages?", r"shipping", r"logistics", r"disrupt(?:s|ed|ion|ions)?",
                     r"factory closures?", r"recalls?", r"bottlenecks?", r"port congestion"],
    "Cyber": [r"cyber-?attacks?", r"ransomware", r"data breach", r"hack(?:ed|ers?)?", r"malware", r"ddos"],
    "Natural Disaster": [r"earthquakes?", r"hurricanes?", r"typhoons?", r"floods?", r"flooding", r"wildfires?",
                         r"cyclones?", r"tsunami", r"drought", r"landslides?"],
    "Product Launch": [r"launch(?:es|ed)?", r"unveils?", r"introduces", r"rolls? out", r"debuts?"],
    "Earnings": [r"earnings", r"profits?", r"revenues?", r"quarterly results", r"guidance", r"net income", r"eps",
                 r"beats? estimates", r"misses? estimates"],
}
EVENT_RX = {k: _union(v) for k, v in EVENT_PATTERNS.items()}

MARKET_RX = _union([
    r"stocks?", r"shares (?:fall|fell|rise|rose|jump|jumped|slide|slid|surge|surged|drop|dropped|tumble|tumbled|plunge|plunged|gain|gained)",
    r"share price", r"wall street", r"nasdaq", r"s&p 500", r"dow jones", r"ftse", r"nikkei", r"sensex", r"nifty",
    r"oil", r"crude", r"brent", r"lng", r"natural gas", r"gold prices?", r"bonds?", r"yields?", r"forex",
    r"currency", r"investors?", r"analysts?", r"dividends?", r"valuation", r"markets?", r"commodit(?:y|ies)",
    r"inflows?", r"financing",
])

NEGATIVE_RX = _union([
    r"celebrity", r"fashion week", r"red carpet", r"affair", r"birthday", r"wedding", r"recipe", r"horoscope",
    r"football", r"soccer", r"rugby", r"concert", r"festival", r"fundraiser", r"obituary", r"funeral",
    r"lethal injection", r"death row", r"murder", r"ufo", r"aliens?", r"reptilian", r"rain", r"oldest person",
    r"library", r"claps back", r"album", r"movie", r"box office",
])

MONEY_RX = re.compile(
    r"(?:[$£€₹]\s?\d|\brs\.?\s?\d|\b(?:usd|eur|gbp|inr)\s?\d|\d[\d,.]*\s?(?:bn|billion|million|mn|crore|cr|lakh|trillion)\b)",
    re.I,
)

# SEC 8-K item number -> event label (real, structured labels; 9.01/7.01/8.01 carry no event meaning)
EDGAR_ITEM_EVENT = {
    "1.03": "Credit Event", "2.04": "Credit Event", "2.06": "Credit Event", "3.01": "Credit Event",
    "4.02": "Regulatory", "1.01": "Merger/Acquisition", "2.01": "Merger/Acquisition",
    "5.01": "Merger/Acquisition", "1.05": "Cyber", "2.02": "Earnings",
}


def distinct_hits(rx: re.Pattern, text: str) -> set:
    return {m.group(0).lower() for m in rx.finditer(text)}


def event_hits(text: str) -> dict:
    out = {}
    for label, rx in EVENT_RX.items():
        hits = distinct_hits(rx, text)
        if hits:
            out[label] = sorted(hits)
    return out