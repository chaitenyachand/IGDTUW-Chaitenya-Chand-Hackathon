"""NLP v0 tests. Headlines and URLs below are REAL items collected by the ingestion service on 2026-10-05."""
import pytest

from sentinel.nlp.clean import clean_title
from sentinel.nlp.entities import link_entities
from sentinel.nlp.features import compute_features

REAL = [  # (title, url)
    ("Tokyo Rain for 37 Days Sets New Record | Metropolis Japan", "https://metropolisjapan.com/tokyo-rain-37-days/"),
    ("Boots & Bling Line Dancing fundraiser set for Oct. 9 - North Fort Myers Neighbor",
     "https://www.northfortmyersneighbor.com/news/swfl-news/2026/10/boots-bling/"),
    ("Ken Weeks: Australia's oldest person marks 113th birthday | The Advertiser - Cessnock",
     "https://www.cessnockadvertiser.com.au/story/9362710/ken-weeks/"),
    ("Landslide derails train, disrupts main line services - Breaking News", "https://www.dailymirror.lk/latest-news/x/1"),
    ("WSO2 Named a Leader in 2026 Gartner Magic Quadrant for API Management - India Education | Latest Education News | Global Educational News",
     "https://indiaeducationdiary.in/wso2-named-a-leader/"),
    ("West Seattle Blog\u2026 | WEST SEATTLE ART: Community showcase opens at Southwest Library",
     "https://westseattleblog.com/2026/10/west-seattle-art/"),
]


def test_clean_title_real_examples():
    out = [clean_title(t, u) for t, u in REAL]
    assert out[0] == "Tokyo Rain for 37 Days Sets New Record"
    assert out[1] == "Boots & Bling Line Dancing fundraiser set for Oct. 9"
    assert out[2] == "Ken Weeks: Australia's oldest person marks 113th birthday"
    assert out[3] == "Landslide derails train, disrupts main line services"
    assert out[4] == "WSO2 Named a Leader in 2026 Gartner Magic Quadrant for API Management"
    assert out[5] == "WEST SEATTLE ART: Community showcase opens at Southwest Library"


def test_clean_title_leaves_normal_headlines_alone():
    t = "India-US trade talks hit 'plateau': Sitharaman says further give-and-take 'very, very difficult'"
    assert clean_title(t, "https://timesofindia.indiatimes.com/x") == t
    assert clean_title("Stocks slide - oil jumps", "https://reuters.com/a") == "Stocks slide - oil jumps"


def names(text, **kw):
    return {e["ticker"] or e["name"] for e in link_entities(text, **kw)}


def test_entity_linking():
    assert names("Boeing shares fall after new lawsuit") == {"BA"}
    assert names("Apple shares jump after iPhone launch") == {"AAPL"}
    assert names("I ate an apple for lunch today") == set()
    assert names("Goldman Sachs and JPMorgan raise forecasts") == {"GS", "JPM"}
    assert "Federal Reserve" in names("Fed minutes show the Federal Reserve is split")
    assert names("RBI holds repo rate") == {"Reserve Bank of India"}
    assert names("anything", meta={"ticker": "NVDA"}) == {"NVDA"}
    assert names("big day", meta={"match": {"tickers": ["TSLA", "MSFT"]}}) == {"TSLA", "MSFT"}
    assert "XOM" in names("Exxon Mobil", meta={"organizations": ["Exxon Mobil"]})


def row(title, url, source="gdelt", meta=None, text=None):
    return {"id": "x", "source_type": "news", "source_name": source, "url": url, "title": title,
            "text": text or title, "meta": meta or {}}


RELEVANT = [
    ("UK Targets Russian LNG Tankers and Bunkering Ships in New Sanctions", "https://shipandbunker.com/a"),
    ("Broadcom offers Anthropic up to $42 billion in financing", "http://www.northkoreatimes.com/a"),
    ("India-US trade talks hit 'plateau': Sitharaman says further give-and-take 'very, very difficult'", "https://timesofindia.indiatimes.com/a"),
    ("Pilgrim's Europe profit rises to \u00a3268m as poultry growth offsets pork pressure", "https://www.farminguk.com/a"),
    ("Abhyudaya Co-op Bank's Business at Rs 13,691Cr, Cuts NPA levels", "https://www.indiancooperative.com/a"),
    ("NPA Moves To Cut Export Bottlenecks, Targets Forex Inflows", "https://leadership.ng/a"),
]
IRRELEVANT = [
    ("UFO whistleblower claims US troops fought 'reptilian' alien giants", "https://www.perthnow.com.au/a"),
    ("Tokyo Rain for 37 Days Sets New Record | Metropolis Japan", "https://metropolisjapan.com/a"),
    ("'What a fuss': star brushes off affair being revealed", "https://www.begadistrictnews.com.au/a"),
    ("Rihanna claps back at EJ Johnson over Fashion Week claims", "https://www.geelongadvertiser.com.au/a"),
    ("I lost my job and my son. Here's what I learned about grace", "https://news.crossmap.com/a"),
    ("Indiana plans to proceed with Jeffrey Weisheit execution after botched Tennessee lethal injection", "https://wowo.com/a"),
    ("Ken Weeks: Australia's oldest person marks 113th birthday | The Advertiser - Cessnock", "https://www.cessnockadvertiser.com.au/a"),
    ("Boots & Bling Line Dancing fundraiser set for Oct. 9 - North Fort Myers Neighbor", "https://www.northfortmyersneighbor.com/a"),
    ("Today in Austria: A roundup of the latest news on Monday", "https://www.thelocal.at/a"),
]


@pytest.mark.parametrize("title,url", RELEVANT)
def test_relevant_real_headlines_pass_gate(title, url):
    f = compute_features(row(title, url))
    assert f.relevant, (f.relevance, f.features)


@pytest.mark.parametrize("title,url", IRRELEVANT)
def test_irrelevant_real_headlines_blocked(title, url):
    f = compute_features(row(title, url))
    assert not f.relevant, (f.relevance, f.features)


def test_weak_event_labels():
    assert compute_features(row("UK Targets Russian LNG Tankers in New Sanctions", "https://a.com/x")).weak_event == "Geopolitical"
    assert compute_features(row("Acme files for bankruptcy after missed payment", "https://a.com/x")).weak_event == "Credit Event"
    edgar = row("Boeing Co. (BA) files Form 8-K: Item 1.05", "https://sec.gov/x", source="sec_edgar",
                meta={"ticker": "BA", "items": ["1.05", "9.01"]})
    f = compute_features(edgar)
    assert f.weak_event == "Cyber" and f.relevant and f.entities[0]["ticker"] == "BA"


def test_social_cashtag_post_is_relevant():
    r = row("Loading up on $NVDA before earnings", "https://bsky.app/x", source="bluesky",
            meta={"match": {"reason": "cashtag", "tickers": ["NVDA"]}})
    r["source_type"] = "social"
    f = compute_features(r)
    assert f.relevant and f.entities[0]["ticker"] == "NVDA"