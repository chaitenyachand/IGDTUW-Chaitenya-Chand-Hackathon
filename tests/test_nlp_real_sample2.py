"""Second round of real items from the 2026-10-05/06 collection (what the first gate let through)."""
import pytest

from sentinel.ingest.bluesky import build_matcher
from sentinel.nlp.features import compute_features
from sentinel.nlp.filters import is_gibberish

M = build_matcher()


def social(text):
    return {"id": "x", "source_type": "social", "source_name": "bluesky", "url": "https://bsky.app/x",
            "title": text[:140], "text": text, "meta": {"match": M(text) or {"reason": "macro"}}}


def news(title, source="gdelt", url="https://example.com/a"):
    return {"id": "x", "source_type": "news", "source_name": source, "url": url, "title": title,
            "text": title, "meta": {}}


BOT_OR_GIBBERISH = [
    "Insider selling 3 insiders at Nebius Group N.V. ($NBIS) sold $12.3M in shares over 7 days.",
    "BUY $FRMM (FRMM.O) [StrategicCollaboration] @ 12:07:06Z",
    "BUY_ON_CONFIRMATION $APUS (APUS.A) [StrategicCollaboration] @ 12:00:02Z",
    "b$7cOosJ*[<V$YRu\\qv+M]O2/FD9(,$t",
    "\U0001F6A8 $SFNC LANIGAN SUSAN S (Insider) reported special transactions (Non-P/S).",
    "$63.6K $BTC SHORT liquidated on Binance @ $85,473. the market collected tuition fast on that one.",
    "\U0001F6A8 $SWRD Initial Filing Analysis Error",
]


@pytest.mark.parametrize("text", BOT_OR_GIBBERISH)
def test_bots_and_gibberish_blocked(text):
    f = compute_features(social(text))
    assert not f.relevant, (f.relevance, f.features)


def test_gibberish_detector_does_not_fire_on_normal_text():
    assert is_gibberish("b$7cOosJ*[<V$YRu\\qv+M]O2/FD9(,$t")
    assert not is_gibberish("Nvidia looks to take out its record high close")
    assert not is_gibberish("$tsla is up 2.5% $spcx is up 6.2% today")
    assert not is_gibberish("https://example.com/a-long-link-with-no-spaces-at-all-1234567")


MARGINAL_NEWS_BLOCKED = [
    ("Moss Unveils New 'Back To Work' Collection for Men", "gdelt"),
    ("Muscat to unveil four prime seafront locations at Urban October 2026", "gdelt"),
    ("Large cyclone approaches Latvia from the northwest, bringing more unsettled weather", "gdelt"),
    ("Legislation would allow nonprofits to accept electronic payments for raffle tickets", "gdelt"),
    ("Alleged crime gang leader Daniel Kinahan appears before court in Dublin", "gdelt"),
    ("Tag: estonia", "rss:guardian_business"),
]


@pytest.mark.parametrize("title,src", MARGINAL_NEWS_BLOCKED)
def test_single_soft_event_news_blocked(title, src):
    f = compute_features(news(title, src))
    assert not f.relevant, (f.relevance, f.features)


MARKET_NEWS_KEPT = [
    ("Nvidia doubles down on selling to both sides of the AI race", "rss:yahoo_finance"),
    ("Wall Street rewards Microsoft's AI pivot. A longtime skeptic says it's just the beginning", "rss:cnbc_finance"),
    ("Nvidia looks to take out its record high close \u2014 plus, don't worry about Intel's dip", "rss:cnbc_finance"),
    ("EU regulator plans broader crypto market oversight", "gdelt"),
    ("Bangladeshi national killed in Houthi missile attack on Saudi Aramco facility", "gdelt"),
    ("S&P/TSX composite down nearly 100 points, U.S. stock markets mixed", "gdelt"),
]


@pytest.mark.parametrize("title,src", MARKET_NEWS_KEPT)
def test_market_news_kept(title, src):
    f = compute_features(news(title, src))
    assert f.relevant, (f.relevance, f.features)
