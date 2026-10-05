"""Social-noise tests. Texts are REAL Bluesky posts collected on 2026-10-05 (truncated as stored),
except where marked 'synthetic'. Matcher metadata is produced by the real ingestion matcher."""
import pytest

from sentinel.ingest.bluesky import build_matcher, parse_commit
from sentinel.nlp.features import compute_features

M = build_matcher()


def post(text):
    meta = {"match": M(text) or {"reason": "macro"}}
    return {"id": "x", "source_type": "social", "source_name": "bluesky", "url": "https://bsky.app/x",
            "title": text[:140], "text": text, "meta": meta}


BLOCKED = [
    "\U0001F6A8 $ARQQW Willcocks Patrick, a Officer, filed a notice of intent to sell 588 shares of common stock, valued at approximately $13,985.40, on 1",
    "Trading Halted for $TEMC Corgi TEM 2x Daily ETF | at 15:12:12.220 ET on Non NASDAQ | Volatility Trading Pause | 2026-10-05",
    "\U0001F534 $ESEA \u2014 Aslidis Anastasios, Chief Financial Officer SOLD: 4,000 shares @ $71.31 Total: $285K Filed Sep 30, 2026",
    "\u2705 WIN: NQ LONG +0.51% (+$3,180 / 1 NQ contract) NQ 5-Min ORB Get future BUY/SELL signals the moment they fire.",
    "Where is all the money the treasury collected from tariffs and $$$ they kept from going to other agencies?",
    "(cont) my default is talking shop or going \u201chell yeah\u201d. generally i have to actively shift into a different mindset",
    "Can't wait to fight the plague with these morons in charge while also fighting the war with Iran and inflation skyrocketing",  # lightly edited
    "nsfw thread: kinks are mostly inflation and weight gain",  # synthetic
]


@pytest.mark.parametrize("text", BLOCKED)
def test_social_noise_blocked(text):
    f = compute_features(post(text))
    assert not f.relevant, (f.relevance, f.features)


def test_real_market_commentary_still_passes():
    t = "$spx is 10 points away from an all time closing high. Higher rates, higher oil, higher debt. None of those matter"
    f = compute_features(post(t))
    assert f.relevant and not f.features["automated"], (f.relevance, f.features)


def test_universe_cashtag_stays_relevant_even_if_automated():
    f = compute_features(post("$BA insider SOLD: 4,000 shares @ $180.10 Total: $720K"))
    assert f.relevant and f.features["automated"] and f.entities[0]["ticker"] == "BA"


def test_default_pattern_is_precise():
    from sentinel.nlp.lexicon import event_hits
    assert "Credit Event" not in event_hits("my default is talking shop")
    assert "Credit Event" in event_hits("Sovereign default fears grow as bond yields jump")
    assert "Credit Event" in event_hits("Acme defaults on loan payments")


def commit(text, labels=None, reply=False):
    rec = {"text": text, "langs": ["en"]}
    if labels:
        rec["labels"] = {"values": [{"val": v} for v in labels]}
    if reply:
        rec["reply"] = {"root": {}, "parent": {}}
    return {"did": "did:plc:abc", "time_us": 1_790_000_000_000_000, "kind": "commit",
            "commit": {"operation": "create", "collection": "app.bsky.feed.post", "rkey": "r1", "record": rec}}


def test_bluesky_drops_adult_labels_and_noncashtag_replies():
    assert parse_commit(commit("Big move in $TSLA today after delivery numbers", labels=["porn"]), M) is None
    assert parse_commit(commit("Inflation and rate hike fears are back in the stock market", reply=True), M) is None
    assert parse_commit(commit("Big move in $TSLA today after delivery numbers", reply=True), M) is not None
    assert parse_commit(commit("nsfw post about inflation and the stock market"), M) is None
