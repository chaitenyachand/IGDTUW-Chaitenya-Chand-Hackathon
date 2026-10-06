from sentinel.tools.labeling import format_line, stratified_sample


def fake(n_gdelt=400, n_bsky=300, n_rss=200, n_edgar=6):
    rows = []
    for src, n in (("gdelt", n_gdelt), ("bluesky", n_bsky), ("rss:cnbc_top", n_rss), ("sec_edgar", n_edgar)):
        for i in range(n):
            rows.append({"id": f"{src[:3]}{i:05d}".ljust(12, "0"), "source_name": src,
                         "title": f"title {src} {i}", "relevant": i % 4 == 0})
    return rows


def test_sample_is_stratified_deterministic_and_balanced():
    rows = fake()
    a, b = stratified_sample(rows, n=300, seed=7), stratified_sample(rows, n=300, seed=7)
    assert [r["id"] for r in a] == [r["id"] for r in b]
    assert len({r["id"] for r in a}) == len(a)
    by = {}
    for r in a:
        g = "rss" if r["source_name"].startswith("rss:") else r["source_name"]
        by.setdefault(g, []).append(r)
    assert len(by["gdelt"]) == 120 and len(by["bluesky"]) == 90 and len(by["rss"]) == 75
    assert len(by["sec_edgar"]) == 6                          # only 6 exist: take them all
    assert sum(r["relevant"] for r in by["gdelt"]) == 60      # half kept by the gate, half blocked


def test_format_line():
    line = format_line({"id": "abcdef1234567890", "source_name": "rss:cnbc_top", "title": "A  title\nwith   breaks"})
    assert line == "abcdef12 | rss | A title with breaks"
