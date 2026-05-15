from unittest.mock import patch

from malibbene.sources.attractions import images


def test_extract_og_image_from_head():
    html = '<html><head><meta property="og:image" content="https://x/h.jpg"></head></html>'
    assert images.extract_og_image(html) == "https://x/h.jpg"


def test_extract_og_image_attribute_reverse_order():
    html = '<meta content="https://x/h.jpg" property="og:image">'
    assert images.extract_og_image(html) == "https://x/h.jpg"


def test_extract_og_image_resolves_relative():
    html = '<meta property="og:image" content="/img/hero.jpg">'
    assert images.extract_og_image(html, base_url="https://www.mos.org/visit") == "https://www.mos.org/img/hero.jpg"


def test_extract_og_image_returns_none_when_missing():
    assert images.extract_og_image("<html><head><title>x</title></head></html>") is None


def test_scrape_one_downloads_image(tmp_path):
    with patch.object(images, "fetch", return_value='<meta property="og:image" content="https://x/h.jpg">'), \
         patch.object(images, "_download_binary", return_value=b"\x89PNG\r\n..."):
        result = images.scrape_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["og_image_url"] == "https://x/h.jpg"
    assert (tmp_path / "mos.jpg").exists()


def test_scrape_one_marks_failed_when_no_og(tmp_path):
    with patch.object(images, "fetch", return_value="<html><body>no og</body></html>"):
        result = images.scrape_one("mos", "https://www.mos.org/", out_dir=tmp_path)
    assert result["status"].startswith("failed")


def test_scrape_one_marks_failed_when_no_website(tmp_path):
    result = images.scrape_one("mos", "", out_dir=tmp_path)
    assert result["status"].startswith("failed")
    result = images.scrape_one("mos", "javascript:void(0)", out_dir=tmp_path)
    assert result["status"].startswith("failed")
