"""HTTP fetch with retry, UA, and 24h disk cache.

Default backend is stdlib urllib (works for all Assabet pages and BPL LibCal
endpoints). For JS-rendered pages, pass ``render_js=True`` — that route lazily
imports :mod:`malibbene.common.browser` and uses Playwright.

Cache layout: ``data/.cache/<sha1(url)>.html`` (gitignored). Pass ``force=True``
to bypass the cache for a single fetch.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path

# Real Chrome UA — many municipal library sites (WP-Engine / Cloudflare) block
# requests with non-browser UA strings, returning 403/503 even before retry logic
# can help. With a real UA + small global delay we get past most of them.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / ".cache"
CACHE_TTL_SECONDS = 24 * 3600

# Per-host polite delay (not global) so a single slow host doesn't block parallel work.
_MIN_INTERVAL_S = 0.5
_last_fetch_at: dict[str, float] = {}


def _polite_wait(url: str) -> None:
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    now = time.time()
    delta = now - _last_fetch_at.get(host, 0.0)
    if delta < _MIN_INTERVAL_S:
        time.sleep(_MIN_INTERVAL_S - delta)
    _last_fetch_at[host] = time.time()


def _cache_path(url: str) -> Path:
    sha = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{sha}.html"


def _read_cache(url: str) -> str | None:
    p = _cache_path(url)
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > CACHE_TTL_SECONDS:
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def _write_cache(url: str, body: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(url).write_text(body, encoding="utf-8")


def _fetch_urllib(url: str, *, headers: dict[str, str] | None, timeout: int) -> str:
    req_headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",  # avoid gzip — we don't decompress
        "Connection": "keep-alive",
    }
    if headers:
        req_headers.update(headers)
    _polite_wait(url)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch(
    url: str,
    *,
    render_js: bool = False,
    force: bool = False,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 3,
) -> str:
    """Fetch ``url`` and return body text.

    Raises the last exception encountered if all ``retries`` attempts fail.
    """
    if not force:
        cached = _read_cache(url)
        if cached is not None:
            return cached

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            if render_js:
                from malibbene.common import browser

                body = browser.fetch_rendered(url, timeout=timeout)
            else:
                body = _fetch_urllib(url, headers=headers, timeout=timeout)
            _write_cache(url, body)
            return body
        except urllib.error.HTTPError as e:
            # Rate-limit / throttling (429, 503) and other server errors need
            # a longer backoff than transient connection errors — Cloudflare's
            # rate-limit window on Assabet subdomains is often 30-60s.
            last_err = e
            if e.code in (429, 503) or 500 <= e.code < 600:
                # 3s, 8s, 20s — short budget so the crawl finishes within ~10min
                # per lib worst case. Persistent 503 means we'll just skip and
                # move on rather than blocking the whole job.
                time.sleep(min(3 * (2**attempt) + 1, 20))
            else:
                # 4xx other than 429: not retriable (404 etc.).
                break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            time.sleep(2**attempt)
        except Exception as e:
            last_err = e
            break

    assert last_err is not None
    raise last_err


def fetch_and_save_html(url: str, out_path: Path, **fetch_kwargs) -> Path:
    """fetch URL, write HTML to disk prefixed with source_url marker. Overwrites on re-fetch."""
    html = fetch(url, **fetch_kwargs)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    marker = f"<!-- source_url: {url} -->\n"
    out_path.write_text(marker + html, encoding="utf-8")
    return out_path
