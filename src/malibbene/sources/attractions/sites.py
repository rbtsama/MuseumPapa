"""Fetch each attraction's official website (homepage + visit/hours page).

URL discovery (in priority order):

1. ``config/benefit_seeds.json`` if present (Claude-defined canonical map)
2. Assabet ``index_page`` records — JSON-LD ``url`` field (often missing) plus
   the ``[Visit Website]`` anchor in the panel
3. BPL ``index_page`` — ``website`` field (set on the public detail page)

For each unique museum URL, fetch the homepage; if it loads, additionally try
common ``/visit/``, ``/hours/``, ``/plan-your-visit/`` paths. Save cleaned text
to ``data/raw/attraction_sites/<slug>/{homepage,visit}.txt``.

JS-rendered sites (React/Squarespace/Wix) are auto-detected: when the homepage
text is < 500 chars **and** Playwright is available, we retry with
``render_js=True``. Otherwise we record the empty result with a status note
and Phase 2 can WebSearch the missing pieces.
"""

from __future__ import annotations

import html as html_mod
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from malibbene.common import http, status

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "data" / "raw" / "attraction_sites"
META_PATH = OUT_DIR / "_meta.json"

ASSABET_INDEX_DIR = REPO_ROOT / "data" / "raw" / "assabet" / "index"
BPL_INDEX_PATH = REPO_ROOT / "data" / "raw" / "bpl" / "index.json"

VISIT_PATHS = ["visit/", "hours/", "plan-your-visit/", "plan-a-visit/", "visit"]

SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")
BLANK_LINE_RE = re.compile(r"\n{3,}")
EXT_ANCHOR_RE = re.compile(
    r'<a\s+[^>]*aria-label="Visit\s+([^"]+?)\s+website"[^>]*href="(https?://[^"]+)"',
    re.IGNORECASE,
)
ALT_ANCHOR_RE = re.compile(
    r'<a\s+[^>]*href="(https?://[^"]+)"[^>]*aria-label="Visit\s+([^"]+?)\s+website"',
    re.IGNORECASE,
)


def html_to_text(html_body: str) -> str:
    body = SCRIPT_STYLE_RE.sub(" ", html_body)
    body = TAG_RE.sub("\n", body)
    body = html_mod.unescape(body)
    body = WS_RE.sub(" ", body)
    lines = [ln.strip() for ln in body.splitlines()]
    body = "\n".join(ln for ln in lines if ln)
    body = BLANK_LINE_RE.sub("\n\n", body)
    return body.strip()


def _norm_url(u: str) -> str:
    p = urlparse(u)
    if not p.scheme:
        u = "https://" + u
        p = urlparse(u)
    return f"{p.scheme}://{p.netloc}".rstrip("/") + "/"


def discover_attraction_urls() -> dict[str, dict]:
    """Return ``{slug: {name, url, source}}``.

    Slug here is a transient ASCII slug derived from the museum name; Phase 2
    will reconcile to canonical ``benefit_id`` values.
    """
    out: dict[str, dict] = {}

    def add(name: str, url: str | None, source: str):
        if not name or not url:
            return
        name = html_mod.unescape(name)
        url = _norm_url(url)
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]
        if not slug:
            return
        if slug in out:
            return
        out[slug] = {"name": name, "url": url, "source": source}

    # Assabet — JSON-LD url + the [Visit Website] anchor pattern
    if ASSABET_INDEX_DIR.exists():
        for f in ASSABET_INDEX_DIR.iterdir():
            data = json.loads(f.read_text(encoding="utf-8"))
            for p in data.get("passes", []):
                name = p.get("museum_name")
                add(name, p.get("website"), f"assabet:{f.stem}:jsonld")

    # BPL — website on detail page
    if BPL_INDEX_PATH.exists():
        bpl = json.loads(BPL_INDEX_PATH.read_text(encoding="utf-8"))
        for p in bpl.get("passes", []):
            add(p.get("museum_name"), p.get("website"), f"bpl:{p['pass_id']}")

    # Heuristic Assabet anchor scan — read one page per library raw HTML
    # cache (already populated). Cheaper than another fetch.
    cache_dir = REPO_ROOT / "data" / ".cache"
    if cache_dir.exists():
        for cf in cache_dir.glob("*.html"):
            body = cf.read_text(encoding="utf-8", errors="replace")
            if "assabetinteractive.com" not in body and "<a " not in body:
                continue
            for m in EXT_ANCHOR_RE.finditer(body):
                add(html_mod.unescape(m.group(1)), m.group(2), "assabet:anchor")
            for m in ALT_ANCHOR_RE.finditer(body):
                add(html_mod.unescape(m.group(2)), m.group(1), "assabet:anchor")

    return out


def _fetch_with_fallback(url: str) -> tuple[str, str]:
    try:
        body = http.fetch(url, timeout=20)
    except Exception as e:
        return "", status.failed(type(e).__name__)
    text = html_to_text(body)
    if len(text) < 500:
        # Try Playwright if available
        try:
            body = http.fetch(url, render_js=True, force=True, timeout=45)
            text = html_to_text(body)
            return text, status.OK if len(text) >= 500 else status.EMPTY
        except RuntimeError:
            return text, status.EMPTY
        except Exception as e:
            return text, status.failed(f"render_js:{type(e).__name__}")
    return text, status.OK


def scrape_attraction(slug: str, info: dict) -> tuple[str, dict]:
    out_dir = OUT_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}

    home_text, home_status = _fetch_with_fallback(info["url"])
    results["homepage"] = {"url": info["url"], "status": home_status, "size": len(home_text)}
    if home_text:
        (out_dir / "homepage.txt").write_text(home_text, encoding="utf-8")

    # Only try /visit paths if the homepage worked
    if home_status == status.OK:
        for path in VISIT_PATHS:
            visit_url = info["url"] + path
            try:
                body = http.fetch(visit_url, timeout=20)
            except Exception:
                continue
            text = html_to_text(body)
            if len(text) >= 500:
                (out_dir / "visit.txt").write_text(text, encoding="utf-8")
                results["visit"] = {
                    "url": visit_url,
                    "status": status.OK,
                    "size": len(text),
                }
                break

    return slug, {
        "name": info["name"],
        "source": info["source"],
        "pages": results,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = discover_attraction_urls()
    print(f"Discovered {len(targets)} attraction URLs.", file=sys.stderr)
    if not targets:
        print(
            "WARNING: no URLs found — Assabet/BPL index files may be missing.",
            file=sys.stderr,
        )
        return 1

    meta: dict = {
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "attractions": {},
    }
    summary = status.StatusSummary()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for slug, info in pool.map(lambda kv: scrape_attraction(*kv), targets.items()):
            meta["attractions"][slug] = info
            home = info["pages"].get("homepage", {})
            summary.add(home.get("status", status.failed("no_homepage")))
            print(
                f"  {slug}: {home.get('status', '?')} ({home.get('size', 0)} chars)",
                file=sys.stderr,
            )
    meta["status_summary"] = summary.to_dict()
    META_PATH.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"Done: ok={summary.ok}/{summary.total} (failed={sum(summary.failed.values())}, empty={summary.empty})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
