from pathlib import Path
from unittest.mock import patch
from malibbene.common.http import fetch_and_save_html

def test_fetch_and_save_writes_html_with_url_marker(tmp_path):
    html = "<html><body>hello</body></html>"
    with patch("malibbene.common.http.fetch", return_value=html):
        out_path = fetch_and_save_html(url="http://example.com/x", out_path=tmp_path/"x.html")
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "<!-- source_url: http://example.com/x -->" in content
    assert "hello" in content
