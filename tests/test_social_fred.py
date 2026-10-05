from sentinel.ingest.bluesky import build_matcher, parse_commit
from sentinel.ingest.reddit import parse_listing
from sentinel.market.fred import parse_observations

M = build_matcher()


def test_matcher_cases():
    assert M("Loading up on $NVDA before earnings")["reason"] == "cashtag"
    assert M("Boeing shares fall after new lawsuit")["reason"] == "name+finance"
    assert M("I ate an apple for lunch today and it was great") is None
    assert M("The Fed signals another rate hike as inflation persists")["reason"] == "macro"
    assert M("$A $B $C $D $E $F pump it") is None  # cashtag spam


def commit(text, langs=("en",), op="create"):
    return {"did": "did:plc:abc", "time_us": 1_790_000_000_000_000, "kind": "commit",
            "commit": {"operation": op, "collection": "app.bsky.feed.post", "rkey": "r1",
                       "record": {"text": text, "langs": list(langs), "createdAt": "2020-01-01T00:00:00Z"}}}


def test_parse_commit_filters_and_uses_observed_time():
    d = parse_commit(commit("Big move in $TSLA today after the delivery numbers"), M)
    assert d and d.source_type == "social" and d.meta["match"]["tickers"] == ["TSLA"]
    assert d.published_at.year == 2026          # observed time, not the spoofable createdAt
    assert parse_commit(commit("Big move in $TSLA today after the delivery numbers", langs=("ja",)), M) is None
    assert parse_commit(commit("Big move in $TSLA today after the delivery numbers", op="delete"), M) is None
    assert parse_commit(commit("short"), M) is None


def test_reddit_listing():
    data = {"data": {"children": [
        {"data": {"name": "t3_1", "title": "NVDA earnings preview", "selftext": "Long text", "permalink": "/r/stocks/1/",
                  "created_utc": 1790000000, "author": "u", "score": 10, "num_comments": 3, "stickied": False}},
        {"data": {"name": "t3_2", "title": "Pinned", "stickied": True, "created_utc": 1}}]}}
    docs = parse_listing(data, "stocks")
    assert len(docs) == 1 and docs[0].meta["subreddit"] == "stocks"


def test_fred_skips_missing_values():
    rows = parse_observations("DGS10", {"observations": [
        {"date": "2026-10-01", "value": "4.12"}, {"date": "2026-10-02", "value": "."}]})
    assert rows == [("DGS10", rows[0][1], 4.12)]
