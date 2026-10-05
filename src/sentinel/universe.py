"""The index universe (15 S&P 100 stocks, sector balanced) and market proxies.

Membership of the S&P 100 changes over time: re-verify against the current list before submission.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Stock:
    ticker: str
    name: str
    sector: str
    aliases: tuple = ()


UNIVERSE = [
    Stock("AAPL", "Apple Inc.", "Information Technology", ("Apple",)),
    Stock("MSFT", "Microsoft Corp.", "Information Technology", ("Microsoft",)),
    Stock("NVDA", "NVIDIA Corp.", "Information Technology", ("Nvidia",)),
    Stock("GOOGL", "Alphabet Inc.", "Communication Services", ("Alphabet", "Google")),
    Stock("AMZN", "Amazon.com Inc.", "Consumer Discretionary", ("Amazon",)),
    Stock("WMT", "Walmart Inc.", "Consumer Staples", ("Walmart",)),
    Stock("JPM", "JPMorgan Chase & Co.", "Financials", ("JPMorgan", "JPMorgan Chase", "JP Morgan")),
    Stock("GS", "Goldman Sachs Group", "Financials", ("Goldman Sachs", "Goldman")),
    Stock("XOM", "Exxon Mobil Corp.", "Energy", ("Exxon", "Exxon Mobil", "ExxonMobil")),
    Stock("CVX", "Chevron Corp.", "Energy", ("Chevron",)),
    Stock("JNJ", "Johnson & Johnson", "Health Care", ("Johnson & Johnson", "J&J")),
    Stock("UNH", "UnitedHealth Group", "Health Care", ("UnitedHealth", "UnitedHealth Group")),
    Stock("BA", "Boeing Co.", "Industrials", ("Boeing",)),
    Stock("CAT", "Caterpillar Inc.", "Industrials", ("Caterpillar",)),
    Stock("NEE", "NextEra Energy", "Utilities", ("NextEra", "NextEra Energy")),
]

# Asset-class proxies used by PRECEDENT and Stress Lab (all fetched from Yahoo Finance).
PROXY_SYMBOLS = {
    "equity_index": "SPY", "energy": "XLE", "financials": "XLF", "technology": "XLK",
    "health_care": "XLV", "industrials": "XLI", "utilities": "XLU", "staples": "XLP",
    "discretionary": "XLY", "communication": "XLC", "banks": "KRE",
    "long_treasury": "TLT", "mid_treasury": "IEF", "high_yield": "HYG", "inv_grade": "LQD",
    "dollar": "UUP", "oil": "USO", "gold": "GLD", "volatility": "^VIX",
}

# Macro / rates series from FRED (free key).
FRED_SERIES = {
    "DGS3MO": "3-month Treasury yield", "DGS2": "2-year Treasury yield",
    "DGS5": "5-year Treasury yield", "DGS10": "10-year Treasury yield",
    "DGS30": "30-year Treasury yield", "T10Y2Y": "10y minus 2y spread",
    "DFF": "Effective fed funds rate", "VIXCLS": "CBOE VIX",
    "BAMLH0A0HYM2": "US high-yield OAS", "BAMLC0A0CM": "US investment-grade OAS",
    "DTWEXBGS": "Broad trade-weighted dollar index", "DCOILWTICO": "WTI crude oil",
}


def all_price_symbols() -> list:
    return [s.ticker for s in UNIVERSE] + list(PROXY_SYMBOLS.values())
