"""SEC EDGAR 8-K connector for the index universe.

Uses the official submissions API. The `items` field (e.g. '2.02,9.01') are the 8-K item numbers:
they double as real, structured event labels for training the event classifier.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

from ..universe import UNIVERSE
from .base import Document, PollingConnector

log = logging.getLogger(__name__)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

ITEM_TITLES = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "1.04": "Mine Safety",
    "1.05": "Material Cybersecurity Incidents",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of a Direct Financial Obligation",
    "2.04": "Triggering Events That Accelerate or Increase a Direct Financial Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy a Listing Rule",
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure or Appointment of Directors or Certain Officers",
    "5.03": "Amendments to Articles of Incorporation or Bylaws",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}


def parse_submissions(js: dict, ticker: str, name: str, cik: int, cutoff: datetime) -> list:
    recent = (js.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    docs = []
    for i, form in enumerate(forms):
        if form not in ("8-K", "8-K/A"):
            continue
        accepted = recent["acceptanceDateTime"][i]
        try:
            ts = datetime.fromisoformat(accepted.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            continue
        acc = recent["accessionNumber"][i]
        items = [x.strip() for x in (recent["items"][i] or "").split(",") if x.strip()]
        item_text = "; ".join(f"Item {x}: {ITEM_TITLES.get(x, 'Other')}" for x in items) or "no item listed"
        title = f"{name} ({ticker}) files Form {form}: {item_text}"
        primary = recent["primaryDocument"][i]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{primary}"
        docs.append(Document(
            "news", "sec_edgar", acc, url, ts, title, title,
            author=name,
            meta={"ticker": ticker, "cik": cik, "form": form, "items": items, "accession": acc},
        ))
    return docs


class EdgarFilings(PollingConnector):
    name = "sec_edgar"

    def __init__(self, client: httpx.AsyncClient, poll_seconds: int, lookback_days: int = 3):
        self.client, self.poll_seconds, self.lookback_days = client, poll_seconds, lookback_days
        self._ciks = {}

    async def _resolve(self):
        r = await self.client.get(TICKERS_URL)
        r.raise_for_status()
        by_ticker = {v["ticker"].upper(): v for v in r.json().values()}
        for s in UNIVERSE:
            v = by_ticker.get(s.ticker)
            if v:
                self._ciks[s.ticker] = (int(v["cik_str"]), s.name)
            else:
                log.warning("edgar: no CIK found for %s", s.ticker)

    async def fetch(self) -> list:
        if not self._ciks:
            await self._resolve()
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        docs = []
        for ticker, (cik, name) in self._ciks.items():
            try:
                r = await self.client.get(SUBMISSIONS_URL.format(cik=cik))
                r.raise_for_status()
                docs += parse_submissions(r.json(), ticker, name, cik, cutoff)
            except Exception as e:
                log.warning("edgar %s failed: %s", ticker, e)
            await asyncio.sleep(0.2)  # stay well below SEC's 10 requests/second limit
        return docs
