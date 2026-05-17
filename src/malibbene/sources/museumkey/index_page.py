"""Scrape every MuseumKey library's by-museum catalog page.

Ported from ``backup/scrape_catalog_museumkey.py``. MuseumKey is a small,
hand-rolled museum-pass platform used by 2 libraries in this dataset (Cohasset
Paul Pratt, Hingham Public). Each library has a ``code`` + ``branchID`` that
together identify its by-museum index:

    https://www2.museumkey.com/ui/byMuseum/?code=<code>&branchID=<branchID>

The page renders all museums server-side. Each museum has:
  - Name in ``class="museumButtonName"`` (v1 theme, Cohasset) or
    ``class="mk2ButtonName"`` + nested ``<p>`` (MK2 theme, Hingham)
  - ``musID=<int>`` in surrounding links — position relative to the name
    differs by theme (v1: prior link; MK2: forward "Check Dates" link)
  - Detail block in ``<div id="detail<musID>">`` with address + benefits text

The benefits text is what feeds ``normalize`` for the discount label.

**No availability scraper**: MuseumKey's calendar lookup requires login
(library card barcode) — we deliberately don't scrape it. Cells in the
final matrix will have pass benefits but no day-by-day availability for
these 2 libraries. This is documented in BRD §A.3.

Output: one file per library at ``data/raw/museumkey/index/<lib_id>.json``,
shape matches assabet/libcal index output for downstream uniformity.
"""

from __future__ import annotations

import html as html_mod
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from malibbene.common import http, status
from malibbene.common.normalize import normalize

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "data" / "raw" / "museumkey" / "index"
MUSEUMKEY_MAP_PATH = REPO_ROOT / "config" / "platform_pass_ids" / "museumkey.json"

NAME_RE_V1 = re.compile(r'class="museumButtonName"[^>]*>\s*([^<]+?)\s*</', re.DOTALL)
NAME_RE_MK2 = re.compile(
    r'class="mk2ButtonName"[^>]*>\s*<p[^>]*>\s*([^<]+?)\s*</p>', re.DOTALL
)
MUSID_RE = re.compile(r"musID=(\d+)")
DETAIL_START_RE = re.compile(r'<div class="row collapse" id="detail(\d+)"')
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
WS_RE = re.compile(r"\s+")

RETURNABLE_RE = re.compile(
    r"\b(returnable|must be returned|return.*to the library|to the (?:circulation|library))\b",
    re.IGNORECASE,
)
DISPOSABLE_RE = re.compile(
    r"\b(disposable|coupon|does not need to be returned|do not need to return|one[-\s]time use)\b",
    re.IGNORECASE,
)
DIGITAL_BODY_RE = re.compile(
    r"\b(?:downloadable\s+via\s+email|e-?voucher|e-?coupon|e-?ticket|promo\s+code|"
    r"coupon\s+code|digital\s+(?:coupon|pass)|electronic\s+(?:pass|coupon)|"
    r"emailed?\s+to\s+you)\b",
    re.IGNORECASE,
)


def _clean_text(raw: str) -> str:
    if not raw:
        return ""
    text = SCRIPT_RE.sub(" ", raw)
    text = TAG_RE.sub(" ", text)
    text = html_mod.unescape(text)
    return WS_RE.sub(" ", text).strip()


def _derive_slug_from_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "unknown"


def classify_pass_type(body: str) -> tuple[str, str]:
    if RETURNABLE_RE.search(body) and not DISPOSABLE_RE.search(body):
        return "physical-circ", "(body: returnable)"
    if DISPOSABLE_RE.search(body):
        return "physical-coupon", "(body: coupon/disposable)"
    if DIGITAL_BODY_RE.search(body):
        return "digital", "(body: digital/email)"
    return "unknown", ""


def scrape_library(
    lib_id: str, code: str, branch_id: int, name_to_benefit: dict[str, str]
) -> tuple[str, dict]:
    url = f"https://www2.museumkey.com/ui/byMuseum/?code={code}&branchID={branch_id}"
    summary = status.StatusSummary()

    try:
        page = http.fetch(url)
    except Exception as e:
        return lib_id, {
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "url": url,
            "meta": {
                "fetch_status": status.failed(type(e).__name__),
                "status_summary": summary.to_dict(),
            },
            "passes": [],
        }

    v1_names = list(NAME_RE_V1.finditer(page))
    if v1_names:
        names = v1_names
        musids: list[str] = []
        for nm in names:
            prefix = page[: nm.start()]
            m = list(MUSID_RE.finditer(prefix))
            musids.append(m[-1].group(1) if m else "")
    else:
        names = list(NAME_RE_MK2.finditer(page))
        musids = []
        for nm in names:
            ahead = page[nm.end():]
            m_fwd = MUSID_RE.search(ahead)
            musids.append(m_fwd.group(1) if m_fwd else "")

    # Build detail blocks keyed by musID — slice each block from its start
    # position to the next block's start (avoids brittle </div></div> bounds).
    detail_starts = [(m.start(), m.group(1)) for m in DETAIL_START_RE.finditer(page)]
    detail_by_id: dict[str, str] = {}
    for i, (pos, musid) in enumerate(detail_starts):
        end = detail_starts[i + 1][0] if i + 1 < len(detail_starts) else len(page)
        detail_by_id[musid] = page[pos:end]

    passes: list[dict] = []
    for nm, musid in zip(names, musids):
        name = _clean_text(nm.group(1))
        if not name or not musid:
            continue
        slug = name_to_benefit.get(name.lower()) or _derive_slug_from_name(name)
        body_html = detail_by_id.get(musid, "")
        body = _clean_text(body_html)
        ptype, ptype_raw = classify_pass_type(body)
        label, label_class = normalize(body)
        record_status = status.OK if body else status.failed("parse:no_body")
        passes.append(
            {
                "slug": slug,
                "musid": musid,
                "url": f"{url}#detail{musid}",
                "museum_name": name,
                "pass_type": ptype,
                "pass_type_raw": ptype_raw,
                "benefits_text": body,
                "label": label,
                "label_class": label_class,
                "status": record_status,
            }
        )
        summary.add(record_status)

    return lib_id, {
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "url": url,
        "meta": {"fetch_status": status.OK, "status_summary": summary.to_dict()},
        "passes": passes,
    }


def load_museumkey_targets() -> list[tuple[str, str, int, dict[str, str]]]:
    cfg = json.loads(MUSEUMKEY_MAP_PATH.read_text(encoding="utf-8"))
    libs = cfg.get("libraries", {})
    name_to_benefit: dict[str, str] = cfg.get("name_to_benefit", {})
    out: list[tuple[str, str, int, dict[str, str]]] = []
    for lib_id, params in libs.items():
        out.append((lib_id, params["code"], int(params["branchID"]), name_to_benefit))
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = load_museumkey_targets()
    print(f"Scraping {len(targets)} MuseumKey libraries...", file=sys.stderr)
    total_ok = 0
    for lib_id, code, branch_id, name_map in targets:
        _, data = scrape_library(lib_id, code, branch_id, name_map)
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
    print(f"Total ok passes across MuseumKey libraries: {total_ok}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
