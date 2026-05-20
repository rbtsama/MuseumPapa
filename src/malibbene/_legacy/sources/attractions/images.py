"""Scrape og:image meta tag from attraction websites and cache binaries locally.

og:image is the Open Graph image — the picture site owners explicitly provide
for social-media sharing cards. Using it as the hero image respects the site
owner's intent.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

from malibbene.common.http import fetch, UA

_OG_FORWARD = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_REVERSE = re.compile(
    r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
    re.IGNORECASE,
)


def extract_og_image(html: str, *, base_url: str | None = None) -> str | None:
    """Return absolute og:image URL, or None if not found."""
    m = _OG_FORWARD.search(html) or _OG_REVERSE.search(html)
    if not m:
        return None
    url = m.group(1).strip()
    if url.startswith(("http://", "https://")):
        return url
    if base_url:
        return urllib.parse.urljoin(base_url, url)
    return None


def _download_binary(url: str, *, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _ext_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"  # default


def scrape_one(slug: str, website: str, *, out_dir: Path) -> dict:
    """Fetch website, extract og:image, download to out_dir/<slug>.<ext>."""
    if not website.startswith(("http://", "https://")):
        return {"slug": slug, "status": "failed:no_website"}
    try:
        html = fetch(website)
    except Exception as e:
        return {"slug": slug, "status": f"failed:fetch:{e}"}
    img_url = extract_og_image(html, base_url=website)
    if not img_url:
        return {"slug": slug, "status": "failed:no_og_image"}
    try:
        body = _download_binary(img_url)
    except Exception as e:
        return {"slug": slug, "status": f"failed:download:{e}", "og_image_url": img_url}
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = _ext_from_url(img_url)
    local = out_dir / f"{slug}{ext}"
    local.write_bytes(body)
    repo_root = out_dir
    # Walk up to find data/ ancestor for clean relative path
    while repo_root.name != "static" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    rel = local.relative_to(repo_root.parent) if repo_root.name == "static" else local
    return {
        "slug": slug,
        "status": "ok",
        "og_image_url": img_url,
        "local_path": str(rel).replace("\\", "/"),
        "bytes": len(body),
    }
