from unittest.mock import patch

from malibbene.sources.attractions import prices


def test_fetch_one_saves_admission_html(tmp_path):
    html = "<html>" + "Adult $30, Child (3-11) $25. Members free. " * 30 + "</html>"
    with patch.object(prices, "fetch", return_value=html):
        result = prices.fetch_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    p = tmp_path / "mos.html"
    assert p.exists()
    assert "Adult $30" in p.read_text(encoding="utf-8")


def test_fetch_one_tries_multiple_paths(tmp_path):
    """If /admission 404s, fall back to /tickets, /visit."""
    calls = []
    def fake_fetch(url, **kw):
        calls.append(url)
        if "/admission" in url or "/tickets" in url:
            raise Exception("404")
        return "<p>Adult $30</p>" + "x" * 1000

    with patch.object(prices, "fetch", side_effect=fake_fetch):
        result = prices.fetch_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    assert len(calls) >= 3


def test_fetch_one_marks_failed_when_all_paths_fail(tmp_path):
    with patch.object(prices, "fetch", side_effect=Exception("502")):
        result = prices.fetch_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"].startswith("failed")
    assert not (tmp_path / "mos.html").exists()


def test_fetch_one_falls_back_to_render_js_on_short_body(tmp_path):
    """If static fetch returns near-empty, retry with render_js=True."""
    calls = []
    def fake_fetch(url, render_js=False, force=False, **kw):
        calls.append((url, render_js))
        if not render_js:
            return "<html></html>"  # short body
        return "<html>" + "Adult $30 " * 100 + "</html>"

    with patch.object(prices, "fetch", side_effect=fake_fetch):
        result = prices.fetch_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    # At least one render_js=True call must have happened
    assert any(rj for (_, rj) in calls)


def test_fetch_one_failed_when_js_render_also_short(tmp_path):
    def fake_fetch(url, render_js=False, force=False, **kw):
        return "<html></html>"

    with patch.object(prices, "fetch", side_effect=fake_fetch):
        result = prices.fetch_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"].startswith("failed")
