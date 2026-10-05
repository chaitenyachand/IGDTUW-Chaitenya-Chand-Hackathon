from sentinel.ingest.base import canonical_url, hamming, normalize_text, simhash, to_signed, to_unsigned
from sentinel.ingest.dedupe import NearDuplicateIndex


def test_normalize_text_strips_html_and_entities():
    assert normalize_text("<p>Fed &amp; markets   <b>rally</b></p>") == "Fed & markets rally"
    assert normalize_text(None) == ""


def test_canonical_url_strips_tracking_and_www():
    u = "HTTPS://www.Example.com/news/story/?utm_source=x&id=7&fbclid=abc#top"
    assert canonical_url(u) == "https://example.com/news/story?id=7"


def test_simhash_similar_vs_different():
    a = "Oil prices surge after OPEC announces surprise production cut, energy stocks rally"
    b = "Oil prices surge after OPEC announces a surprise production cut, energy stocks rally"
    c = "Apple unveils new iPhone with improved camera and longer battery life this fall"
    assert hamming(simhash(a), simhash(b)) < hamming(simhash(a), simhash(c))
    assert hamming(simhash(a), simhash(c)) > 10


def test_signed_roundtrip():
    for x in (0, 1, (1 << 63) - 1, 1 << 63, (1 << 64) - 1):
        assert to_unsigned(to_signed(x)) == x


def test_near_duplicate_index_finds_within_distance_only():
    idx = NearDuplicateIndex(max_distance=3)
    base = simhash("Fed holds rates steady and signals two cuts later this year")
    idx.add(base, "doc1")
    near = base ^ 0b101            # 2 bits flipped
    far = base ^ ((1 << 20) - 1)   # 20 bits flipped
    assert idx.find(near) == "doc1"
    assert idx.find(far) is None
    assert idx.find(0) is None
    assert len(idx) == 1
