from datetime import datetime, timezone

from sentinel.ingest.edgar import parse_submissions
from sentinel.ingest.rss import parse_feed

SUB = {"filings": {"recent": {
    "form": ["8-K", "10-Q", "8-K"],
    "acceptanceDateTime": ["2026-10-02T20:15:03.000Z", "2026-10-01T10:00:00.000Z", "2026-01-01T10:00:00.000Z"],
    "accessionNumber": ["0000320193-26-000001", "0000320193-26-000002", "0000320193-26-000003"],
    "items": ["2.02,9.01", "", "1.03"],
    "primaryDocument": ["a.htm", "b.htm", "c.htm"],
}}}


def test_edgar_keeps_recent_8k_with_item_titles():
    cutoff = datetime(2026, 9, 30, tzinfo=timezone.utc)
    docs = parse_submissions(SUB, "AAPL", "Apple Inc.", 320193, cutoff)
    assert len(docs) == 1
    d = docs[0]
    assert d.meta["items"] == ["2.02", "9.01"]
    assert "Results of Operations" in d.title
    assert d.url.endswith("/320193/000032019326000001/a.htm")


def test_edgar_bankruptcy_item_label():
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
    docs = parse_submissions(SUB, "AAPL", "Apple Inc.", 320193, cutoff)
    assert any("Bankruptcy or Receivership" in d.title for d in docs)


RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Fed holds rates</title><link>https://x.com/a?utm_source=z</link><guid>g1</guid>
<description>&lt;p&gt;Policy makers kept rates unchanged.&lt;/p&gt;</description>
<pubDate>Fri, 02 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title></title><link>https://x.com/b</link></item></channel></rss>"""


def test_rss_parse_skips_untitled_and_cleans_html():
    docs = parse_feed("demo", RSS)
    assert len(docs) == 1
    d = docs[0]
    assert d.source_name == "rss:demo" and d.title == "Fed holds rates"
    assert d.text == "Fed holds rates. Policy makers kept rates unchanged."
    assert d.canonical_url == "https://x.com/a"
    assert d.published_at == datetime(2026, 10, 2, 14, 0, tzinfo=timezone.utc)
