"""Playwright wrapper for JS-rendered pages.

Playwright is an optional dependency — only required when an attraction site
needs a real browser. We lazy-import here so plain urllib scraping works even
on machines without Playwright installed.

Install when needed::

    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

INSTALL_HINT = (
    "Playwright is required for JS-rendered pages. Install with:\n"
    "    pip install playwright\n"
    "    playwright install chromium"
)


def fetch_rendered(url: str, *, timeout: int = 30) -> str:
    """Render ``url`` in headless Chromium and return outerHTML.

    Raises :class:`RuntimeError` with install hint if Playwright is missing.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(INSTALL_HINT) from e

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
            return page.content()
        finally:
            browser.close()
