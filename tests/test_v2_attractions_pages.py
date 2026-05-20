from unittest.mock import patch
from pathlib import Path
from malibbene.sources_v2.attractions.pages import fetch_attraction_page

def test_fetch_attraction_writes_html_and_meta(tmp_path):
    html = "<html><head><title>MFA</title><meta property='og:image' content='http://x/y.jpg'></head><body>about</body></html>"
    with patch("malibbene.sources_v2.attractions.pages.fetch", return_value=html):
        result = fetch_attraction_page(
            slug="mfa", url="https://mfa.org/",
            raw_root=tmp_path,
        )
    page = tmp_path / "attractions" / "pages" / "mfa.html"
    meta = tmp_path / "attractions" / "pages" / "mfa.meta.json"
    assert page.exists() and meta.exists()
    import json
    m = json.loads(meta.read_text())
    assert m["og_image"] == "http://x/y.jpg"
    assert m["url"] == "https://mfa.org/"
