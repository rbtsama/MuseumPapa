"""Verify ``http.fetch`` retry behavior for rate-limit responses.

We monkey-patch ``time.sleep`` to capture sleep durations and
``_fetch_urllib`` to force specific exceptions, so the test runs
in milliseconds with no real network."""

import urllib.error

import pytest

from malibbene.common import http


@pytest.fixture
def patch_no_cache(monkeypatch, tmp_path):
    """Point cache at an empty tmpdir so each test starts fresh."""
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)


def _make_http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://x/", code=code, msg="boom", hdrs=None, fp=None  # type: ignore[arg-type]
    )


def test_429_uses_long_backoff(monkeypatch, patch_no_cache):
    sleeps: list[float] = []
    monkeypatch.setattr(http.time, "sleep", lambda s: sleeps.append(s))

    def always_429(url, **kw):
        raise _make_http_error(429)

    monkeypatch.setattr(http, "_fetch_urllib", always_429)

    with pytest.raises(urllib.error.HTTPError):
        http.fetch("http://x/", retries=3, force=True)

    # 5s, 15s, 45s exponential at base 3
    assert sleeps == [5, 15, 45]


def test_503_retried_with_long_backoff(monkeypatch, patch_no_cache):
    sleeps: list[float] = []
    monkeypatch.setattr(http.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(http, "_fetch_urllib", lambda url, **kw: (_ for _ in ()).throw(_make_http_error(503)))

    with pytest.raises(urllib.error.HTTPError):
        http.fetch("http://x/", retries=3, force=True)
    assert sleeps == [5, 15, 45]


def test_404_not_retried(monkeypatch, patch_no_cache):
    sleeps: list[float] = []
    monkeypatch.setattr(http.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(http, "_fetch_urllib", lambda url, **kw: (_ for _ in ()).throw(_make_http_error(404)))

    with pytest.raises(urllib.error.HTTPError):
        http.fetch("http://x/", retries=3, force=True)
    # 404 should break immediately — no retries, no sleep.
    assert sleeps == []


def test_timeout_short_backoff(monkeypatch, patch_no_cache):
    sleeps: list[float] = []
    monkeypatch.setattr(http.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(http, "_fetch_urllib", lambda url, **kw: (_ for _ in ()).throw(TimeoutError("slow")))

    with pytest.raises(TimeoutError):
        http.fetch("http://x/", retries=3, force=True)
    # Short backoff path: 1s, 2s, 4s
    assert sleeps == [1, 2, 4]


def test_recovers_after_one_429(monkeypatch, patch_no_cache):
    calls = {"n": 0}
    monkeypatch.setattr(http.time, "sleep", lambda s: None)

    def flaky(url, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _make_http_error(429)
        return "OK body"

    monkeypatch.setattr(http, "_fetch_urllib", flaky)
    body = http.fetch("http://x/", retries=3, force=True)
    assert body == "OK body"
    assert calls["n"] == 2  # first failed, second succeeded
