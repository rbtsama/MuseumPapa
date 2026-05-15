"""Test the library page fetcher (HTML saving, not extraction)."""
from unittest.mock import patch

from malibbene.sources.libraries import addresses


def test_fetch_one_saves_html_to_disk(tmp_path):
    fake_html = "<html><body>" + "Visit us at 60 Main Street, Wakefield, MA 01880." * 20 + "</body></html>"
    with patch.object(addresses, "fetch", return_value=fake_html):
        result = addresses.fetch_one("wakefield", "https://wakefieldlibrary.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["lib_id"] == "wakefield"
    assert result["source_url"].startswith("https://wakefieldlibrary.org/")
    p = tmp_path / "wakefield.html"
    assert p.exists()
    assert "60 Main Street" in p.read_text(encoding="utf-8")


def test_fetch_one_tries_multiple_paths(tmp_path):
    """If /visit 404s, fall back to /hours, /contact."""
    calls = []
    def fake_fetch(url, **kw):
        calls.append(url)
        if "/visit" in url or "/hours" in url:
            raise Exception("404")
        return "<html>" + "address content here " * 50 + "</html>"

    with patch.object(addresses, "fetch", side_effect=fake_fetch):
        result = addresses.fetch_one("wakefield", "https://wakefieldlibrary.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    # tried at least 3 paths before success
    assert len(calls) >= 3


def test_fetch_one_marks_failed_when_all_paths_fail(tmp_path):
    with patch.object(addresses, "fetch", side_effect=Exception("network")):
        result = addresses.fetch_one("wakefield", "https://wakefieldlibrary.org/", out_dir=tmp_path)

    assert result["status"].startswith("failed")
    assert not (tmp_path / "wakefield.html").exists()


def test_fetch_one_treats_tiny_response_as_failure(tmp_path):
    """A near-empty body (e.g., JS-only shell) should not count as ok."""
    with patch.object(addresses, "fetch", return_value="<html></html>"):
        result = addresses.fetch_one("wakefield", "https://wakefieldlibrary.org/", out_dir=tmp_path)

    assert result["status"].startswith("failed")
