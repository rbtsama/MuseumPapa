"""Scrape every LibCal library's pass listing + per-pass detail page.

Generalized from the BPL-only ``backup/bpl_*`` + ``backup/scrape_catalog_libcal.py``.
Covers 5 libraries on the LibCal platform:

  - bpl        (https://bpl.libcal.com)        — 12-hex pass ids
  - cambridge  (https://cambridgepl.libcal.com) — slug-style pass ids
  - brookline  (https://brooklinelibrary.libcal.com) — short-code + 12-hex mix
  - braintree  (https://thayerpubliclibrary.libcal.com) — 12-hex pass ids
  - milton     (https://miltonlibrary.libcal.com) — 12-hex pass ids

For each library:
  1. Fetch ``https://<domain>/passes/`` → list source-side pass ids.
  2. Fetch each ``https://<domain>/passes/<pass_id>`` → extract title,
     pass-type from title-suffix + body hints, body text (for benefit
     normalization), and ``springyPage.museum`` hex (used for availability
     calls — slug-style URLs need the hex separately).
  3. Map source-side pass_id → canonical ``benefit_id`` slug via the hand-
     curated table in ``config/platform_pass_ids/{bpl,libcal}.json``.
     Unmapped passes derive a slug from the museum name.

Output: one file per library at ``data/raw/libcal/index/<lib_id>.json``,
matching ``data/raw/assabet/index/<lib_id>.json`` shape so downstream code
can iterate platforms uniformly.
"""

from __future__ import annotations

import html as html_mod
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from malibbene.common import http, status
from malibbene.common.normalize import normalize

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "data" / "raw" / "libcal" / "index"
SEEDS_PATH = REPO_ROOT / "config" / "library_seeds.json"
LIBCAL_MAP_PATH = REPO_ROOT / "config" / "platform_pass_ids" / "libcal.json"
BPL_MAP_PATH = REPO_ROOT / "config" / "platform_pass_ids" / "bpl.json"

# Listing page: anchors of the form href="/passes/<id>". The id can be 12-hex
# (BPL / Braintree / Milton), a slug (Cambridge), or a short code (Brookline).
PASS_LINK_RE = re.compile(r'href="/passes/([0-9a-zA-Z_-]+)"[^>]*>([^<]{3,200})</a>')
TITLE_RE = re.compile(r'<h1[^>]*id="s-lc-public-pt"[^>]*>(.*?)</h1>', re.DOTALL | re.IGNORECASE)
# springyPage.museum holds the hex museum-id used for availability calls when
# the pass URL is a slug.
SPRINGY_MUSEUM_RE = re.compile(
    r"springyPage\s*=\s*\{[^}]*?museum:\s*'([0-9a-fA-F]+)'", re.DOTALL
)
PAREN_RE = re.compile(r"\(([^()]+)\)\s*$")
ADDRESS_RE = re.compile(
    r's-lc-pass-address[^>]*>(.*?)<(?:/p>|a\s)', re.DOTALL | re.IGNORECASE
)
WEBSITE_RE = re.compile(
    r'<a\s+[^>]*href="(https?://[^"]+)"[^>]*class="s-lc-museum-link"', re.IGNORECASE
)
FOOTER_RE = re.compile(r'<(?:div[^>]*s-lc-public-footer|footer)\b', re.IGNORECASE)
P_TAG_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
WS_RE = re.compile(r"\s+")

# Body-text classification hints (LibCal pages vary by library)
DIGITAL_SUFFIX_RE = re.compile(
    r"\((e-coupon|e-ticket|downloadable|digital|digital coupon pass|promo code|coupon code)\)",
    re.IGNORECASE,
)
PHYSICAL_SUFFIX_RE = re.compile(r"\((physical|physical pass)\)", re.IGNORECASE)
AVAIL_DIGITAL_RE = re.compile(r"downloadable\s+via\s+email", re.IGNORECASE)
AVAIL_PHYSICAL_RE = re.compile(r"must\s+be\s+picked\s+up\s+at\s+the\s+library", re.IGNORECASE)
RETURNABLE_RE = re.compile(r"\b(returnable|must be returned|must.*be returned to)\b", re.IGNORECASE)
DISPOSABLE_RE = re.compile(
    r"\b(disposable|does not need to be returned|do not need to return)\b",
    re.IGNORECASE,
)
DIGITAL_BODY_RE = re.compile(
    r"\b(?:downloadable\s+via\s+email|e-?voucher|e-?coupon|e-?ticket|promo\s+code|"
    r"coupon\s+code|digital\s+(?:coupon|pass)|electronic\s+(?:pass|coupon))\b",
    re.IGNORECASE,
)
SKIP_P_HINT_RE = re.compile(
    r"\b(?:Map|Open\s+map\s+for|Directions\s+to|United\s+States|MA\s+\d{5}|"
    r"cookies?\s+(?:are|in\s+your))\b",
    re.IGNORECASE,
)


def _strip_tags(s: str) -> str:
    return html_mod.unescape(WS_RE.sub(" ", TAG_RE.sub(" ", s))).strip()


def _clean_text(raw: str) -> str:
    text = SCRIPT_RE.sub(" ", raw)
    text = TAG_RE.sub(" ", text)
    text = html_mod.unescape(text)
    return WS_RE.sub(" ", text).strip()


def _derive_slug_from_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "unknown"


def classify_pass_type(title: str, body_text: str) -> tuple[str, str]:
    """Return (pass_type, raw_label). Order: title suffix > body hints."""
    if PHYSICAL_SUFFIX_RE.search(title):
        if RETURNABLE_RE.search(body_text) and not DISPOSABLE_RE.search(body_text):
            return "physical-circ", "(physical)"
        if DISPOSABLE_RE.search(body_text):
            return "physical-coupon", "(physical)"
        return "physical-circ", "(physical)"
    dm = DIGITAL_SUFFIX_RE.search(title)
    if dm:
        return "digital", f"({dm.group(1)})"
    has_digital = bool(AVAIL_DIGITAL_RE.search(body_text) or DIGITAL_BODY_RE.search(body_text))
    has_physical = bool(AVAIL_PHYSICAL_RE.search(body_text) or RETURNABLE_RE.search(body_text))
    if has_digital and not has_physical:
        return "digital", "(body: digital)"
    if has_physical and not has_digital:
        if DISPOSABLE_RE.search(body_text):
            return "physical-coupon", "(body: disposable)"
        return "physical-circ", "(body: returnable)"
    return "unknown", ""


def body_paragraphs(page_html: str) -> list[str]:
    h1 = TITLE_RE.search(page_html)
    start = h1.end() if h1 else 0
    foot = FOOTER_RE.search(page_html, start)
    end = foot.start() if foot else len(page_html)
    body_slice = page_html[start:end]
    out: list[str] = []
    for m in P_TAG_RE.finditer(body_slice):
        t = _clean_text(m.group(1))
        if not t or SKIP_P_HINT_RE.search(t):
            continue
        out.append(t)
    return out


def list_passes(domain: str) -> tuple[list[tuple[str, str]], str]:
    """Fetch the catalog index and return (pass_id, link_text) pairs."""
    url = f"https://{domain}/passes/"
    try:
        body = http.fetch(url)
    except Exception as e:
        return [], status.failed(type(e).__name__)
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in PASS_LINK_RE.finditer(body):
        pid, name = m.group(1), _clean_text(m.group(2))
        if pid in seen or pid == "passes":
            continue
        seen.add(pid)
        pairs.append((pid, name))
    if not pairs:
        return [], status.EMPTY
    return pairs, status.OK


def fetch_detail(domain: str, pass_id: str) -> dict:
    url = f"https://{domain}/passes/{pass_id}"
    try:
        body = http.fetch(url)
    except Exception as e:
        return {"url": url, "pass_id": pass_id, "status": status.failed(type(e).__name__)}
    return parse_detail(pass_id, url, body)


def parse_detail(pass_id: str, url: str, html_body: str) -> dict:
    record: dict = {"pass_id": pass_id, "url": url}

    tm = TITLE_RE.search(html_body)
    record["title_raw"] = _strip_tags(tm.group(1)) if tm else ""
    if record["title_raw"]:
        paren_m = PAREN_RE.search(record["title_raw"])
        if paren_m:
            record["museum_name"] = record["title_raw"][: paren_m.start()].strip()
        else:
            record["museum_name"] = record["title_raw"]

    am = ADDRESS_RE.search(html_body)
    if am:
        record["address"] = _strip_tags(am.group(1))

    wm = WEBSITE_RE.search(html_body)
    if wm:
        record["website"] = wm.group(1)

    paragraphs = body_paragraphs(html_body)
    # Filter the address paragraph if it leaked into <p> blocks.
    if record.get("address"):
        paragraphs = [p for p in paragraphs if p != record["address"]]
    record["benefits_text"] = " ".join(paragraphs)

    pass_type, ptype_raw = classify_pass_type(record.get("title_raw", ""), record["benefits_text"])
    record["pass_type"] = pass_type
    record["pass_type_raw"] = ptype_raw

    sm = SPRINGY_MUSEUM_RE.search(html_body)
    record["museum_hex"] = sm.group(1) if sm else ""

    label, label_class = normalize(record["benefits_text"])
    record["label"] = label
    record["label_class"] = label_class

    if not record.get("museum_name"):
        record["status"] = status.failed("parse:no_title")
    elif not record.get("benefits_text"):
        record["status"] = status.failed("parse:no_description")
    else:
        record["status"] = status.OK
    return record


def scrape_library(
    lib_id: str, domain: str, id_to_slug: dict[str, str]
) -> tuple[str, dict]:
    """Scrape one LibCal library. ``id_to_slug`` maps source pass_id → benefit_id."""
    catalog_url = f"https://{domain}/passes/"
    pairs, listing_status = list_passes(domain)
    summary = status.StatusSummary()
    passes: list[dict] = []

    if not pairs:
        return lib_id, {
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "url": catalog_url,
            "meta": {"fetch_status": listing_status, "status_summary": summary.to_dict()},
            "passes": passes,
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda pid: fetch_detail(domain, pid), [p for p, _ in pairs]))

    for (pid, link_name), record in zip(pairs, results):
        slug = id_to_slug.get(pid) or _derive_slug_from_name(
            record.get("museum_name") or link_name
        )
        record["slug"] = slug
        record["link_name"] = link_name
        record.setdefault("museum_name", link_name)
        passes.append(record)
        summary.add(record.get("status", status.failed("parse:no_status")))

    return lib_id, {
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "url": catalog_url,
        "meta": {"fetch_status": listing_status, "status_summary": summary.to_dict()},
        "passes": passes,
    }


def load_libcal_targets() -> list[tuple[str, str, dict[str, str]]]:
    """Return (lib_id, domain, id_to_slug) for every libcal library in seeds.

    BPL's mapping (config/platform_pass_ids/bpl.json) is benefit_id → hex.
    The other 4 libcal libs (config/platform_pass_ids/libcal.json) store
    libcal_id → benefit_id directly. We unify to the libcal_id → benefit_id
    direction so the scraper can look up by URL pass_id.
    """
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    libcal_libs = [lib for lib in seeds["libraries"] if lib["platform"] == "libcal"]

    libcal_map = json.loads(LIBCAL_MAP_PATH.read_text(encoding="utf-8")).get("libraries", {})
    bpl_map_raw = json.loads(BPL_MAP_PATH.read_text(encoding="utf-8")).get("passes", {})
    bpl_id_to_slug = {hex_id: benefit for benefit, hex_id in bpl_map_raw.items()}

    out: list[tuple[str, str, dict[str, str]]] = []
    for lib in libcal_libs:
        lib_id = lib["id"]
        domain = lib["domain"]
        if lib_id == "bpl":
            id_to_slug = bpl_id_to_slug
        else:
            id_to_slug = libcal_map.get(lib_id, {}).get("passes", {})
        out.append((lib_id, domain, id_to_slug))
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = load_libcal_targets()
    print(f"Scraping {len(targets)} LibCal libraries...", file=sys.stderr)
    total_ok = 0
    for lib_id, domain, id_to_slug in targets:
        _, data = scrape_library(lib_id, domain, id_to_slug)
        (OUT_DIR / f"{lib_id}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        s = data["meta"].get("status_summary", {})
        total_ok += s.get("ok", 0)
        print(
            f"  {lib_id}: {len(data['passes'])} passes "
            f"(ok={s.get('ok', 0)} failed={sum(s.get('failed', {}).values())})",
            file=sys.stderr,
        )
    print(f"Total ok passes across LibCal libraries: {total_ok}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
