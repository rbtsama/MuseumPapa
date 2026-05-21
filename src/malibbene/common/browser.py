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


# Real desktop-Chrome UA. Playwright's default UA contains "HeadlessChrome",
# which some WAFs (SiteDistrict, Cloudflare bot rules) sniff and block. We
# override it with a plausible desktop string so we look like a normal browser.
_RENDER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def fetch_rendered(
    url: str,
    *,
    timeout: int = 30,
    wait_until: str = "domcontentloaded",
    settle_ms: int = 2500,
    user_agent: str | None = None,
) -> str:
    """Render ``url`` in headless Chromium and return the page's HTML.

    Parameters
    ----------
    timeout:
        Navigation timeout in seconds.
    wait_until:
        Playwright load state to wait for. Defaults to ``"domcontentloaded"``
        rather than ``"networkidle"`` — many municipal/museum sites keep a
        chat widget or analytics socket open forever, so ``networkidle`` never
        fires and the nav times out even though the content is fully there.
    settle_ms:
        Extra wait after the load state, to let JS widgets (hours tables,
        eligibility blurbs) hydrate before we snapshot ``page.content()``.
    user_agent:
        Override the UA string. Defaults to a real desktop-Chrome UA so we
        don't advertise "HeadlessChrome" to bot filters.

    Raises :class:`RuntimeError` with install hint if Playwright is missing.
    """
    try:
        from playwright.sync_api import sync_playwright
        from playwright.sync_api import TimeoutError as PWTimeout
    except ImportError as e:
        raise RuntimeError(INSTALL_HINT) from e

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                user_agent=user_agent or _RENDER_UA,
                viewport={"width": 1366, "height": 2200},
                locale="en-US",
            )
            page = context.new_page()
            # A goto timeout does NOT mean we have no content — many sites keep a
            # socket open so the requested wait_until never fires even though the
            # DOM is fully populated. So we swallow the nav timeout and still
            # snapshot whatever rendered. We only fail hard if nothing loaded.
            try:
                page.goto(url, timeout=timeout * 1000, wait_until=wait_until)
            except PWTimeout:
                pass
            # Scroll the page in steps to trigger lazy-loaded / intersection-
            # observer content (eligibility blurbs, hours tables) to hydrate.
            try:
                for _ in range(4):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(600)
            except Exception:
                pass
            if settle_ms:
                page.wait_for_timeout(settle_ms)
            html = page.content()
            if not html or len(html) < 200:
                raise RuntimeError(f"rendered page empty for {url}")
            return html
        finally:
            browser.close()
