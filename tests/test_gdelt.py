import io
import zipfile

from sentinel.ingest.gdelt import parse_gkg_line, parse_gkg_zip


def row(themes="ECON_STOCKMARKET,10;WB_696_PUBLIC_SECTOR,20", title="Stocks slide as oil jumps", translation=""):
    cols = [""] * 27
    cols[0], cols[1], cols[2], cols[3], cols[4] = "20261003121500-1", "20261003121500", "1", "reuters.com", "https://reuters.com/a"
    cols[8] = themes
    cols[14] = "Federal Reserve,5;Exxon Mobil,90"
    cols[15] = "-3.2,1.1,4.3,5.4,20.0,1.0,350"
    cols[25] = translation
    cols[26] = f"<PAGE_TITLE>{title}</PAGE_TITLE><PAGE_AUTHORS>x</PAGE_AUTHORS>"
    return cols


def test_relevant_record_parsed():
    d = parse_gkg_line(row())
    assert d.title == "Stocks slide as oil jumps"
    assert d.source_type == "news" and d.source_name == "gdelt"
    assert d.meta["tone"] == -3.2 and d.meta["negative"] == 4.3 and d.meta["word_count"] == 350
    assert "ECON_STOCKMARKET" in d.meta["themes"] and "WB_696_PUBLIC_SECTOR" not in d.meta["themes"]
    assert d.meta["organizations"] == ["Federal Reserve", "Exxon Mobil"]
    assert d.published_at.year == 2026 and d.published_at.tzinfo is not None


def test_irrelevant_translated_or_untitled_dropped():
    assert parse_gkg_line(row(themes="SPORTS,1")) is None
    assert parse_gkg_line(row(translation="srclc:deu")) is None
    assert parse_gkg_line(row(title="")) is None
    assert parse_gkg_line(["too", "short"]) is None


def test_zip_parsing_and_cap():
    body = "\n".join("\t".join(row(title=f"Story {i}")) for i in range(5)).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.gkg.csv", body)
    assert len(parse_gkg_zip(buf.getvalue())) == 5
    assert len(parse_gkg_zip(buf.getvalue(), max_records=2)) == 2
