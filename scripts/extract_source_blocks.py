"""Phase B (controller-side prep) · source-block extraction.

The Claude Code controller dispatches one general-purpose subagent per entity
(isolation boundary). This script does the deterministic prep the controller
needs so each subagent stays cheap and isolated:

  1. strip_all()  — for every entity that has HTML, strip each HTML file to
     readable paragraphs and concatenate into one text file under
     data/raw/attractions/_stripped/<slug>.txt  (or libraries/_stripped/<id>.txt)
     with a "=== <relpath> ===" + "source_url: <url>" header per file. This is
     the "readable-text dump" the §7 prompt refers to; the subagent Reads it.
  2. write_null_stubs() — entities with zero reachable HTML get an honest
     all-null _source_blocks/<id>.json (never invented).
  3. manifest() — print the dispatch list (one row per entity to extract) as
     JSON for the controller.

Run:  python scripts/extract_source_blocks.py [strip|stubs|manifest|all]
"""
from __future__ import annotations

import html as _html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTR_JSON = ROOT / "data" / "structured" / "attractions.json"
LIB_JSON = ROOT / "data" / "structured" / "libraries.json"
A_RAW = ROOT / "data" / "raw" / "attractions"
L_RAW = ROOT / "data" / "raw" / "libraries"

PER_PAGE_CAP = 16000  # chars of readable text kept per HTML file

_SRC_MARKER_RE = re.compile(r"<!--\s*source_url:\s*(\S+)\s*-->")
_DROP_RE = re.compile(r"<(script|style|noscript|svg|head)\b.*?</\1>", re.I | re.S)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_BLOCK_RE = re.compile(r"</(p|div|section|li|h[1-6]|tr|article|header|footer|br)>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(raw: str) -> tuple[str | None, str]:
    """Return (source_url, readable_text). Preserves paragraph boundaries."""
    m = _SRC_MARKER_RE.search(raw[:300])
    src = m.group(1) if m else None
    body = _DROP_RE.sub(" ", raw)
    body = _COMMENT_RE.sub(" ", body)
    body = _BLOCK_RE.sub("\n", body)
    body = _TAG_RE.sub(" ", body)
    body = _html.unescape(body)
    # collapse intra-line whitespace, keep newlines as paragraph separators
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in body.split("\n")]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    text = "\n".join(out).strip()
    if len(text) > PER_PAGE_CAP:
        text = text[:PER_PAGE_CAP] + "\n…[truncated]"
    return src, text


def _entity_html_files(kind: str, ident: str) -> list[Path]:
    if kind == "attraction":
        files = []
        hp = A_RAW / "pages" / f"{ident}.html"
        if hp.exists():
            files.append(hp)
        files += sorted((A_RAW / "subpages").glob(f"{ident}__*.html"))
        return files
    else:
        p = L_RAW / "_pages" / f"{ident}.html"
        return [p] if p.exists() else []


def _stripped_path(kind: str, ident: str) -> Path:
    base = (A_RAW if kind == "attraction" else L_RAW) / "_stripped"
    return base / f"{ident}.txt"


def _entities() -> list[dict]:
    attrs = json.loads(ATTR_JSON.read_text(encoding="utf-8"))["attractions"]
    libs = json.loads(LIB_JSON.read_text(encoding="utf-8"))["libraries"]
    out = []
    for a in attrs:
        out.append({"kind": "attraction", "id": a["slug"], "name": a["name"],
                    "base_url": a.get("website")})
    for l in libs:
        out.append({"kind": "library", "id": l["id"], "name": l["name"],
                    "base_url": l.get("card_page")})
    return out


def strip_all() -> dict:
    stats = {"stripped": 0, "no_html": 0}
    manifest = []
    for e in _entities():
        files = _entity_html_files(e["kind"], e["id"])
        if not files:
            stats["no_html"] += 1
            continue
        chunks, inspected = [], []
        for f in files:
            raw = f.read_text(encoding="utf-8", errors="replace")
            src, text = strip_html(raw)
            src = src or e.get("base_url") or "(unknown)"
            rel = f.relative_to(A_RAW if e["kind"] == "attraction" else L_RAW)
            relstr = str(rel).replace("\\", "/")
            inspected.append(relstr)
            chunks.append(f"=== {relstr} ===\nsource_url: {src}\n\n{text}")
        sp = _stripped_path(e["kind"], e["id"])
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text("\n\n".join(chunks), encoding="utf-8")
        stats["stripped"] += 1
        manifest.append({**e, "stripped": str(sp.relative_to(ROOT)).replace("\\", "/"),
                         "sources_inspected": inspected})
    (ROOT / "data" / "raw" / "_source_block_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return stats


def write_null_stubs() -> dict:
    """Honest all-null _source_blocks for entities with no reachable HTML."""
    n = 0
    for e in _entities():
        if _entity_html_files(e["kind"], e["id"]):
            continue
        if e["kind"] == "attraction":
            out = A_RAW / "_source_blocks" / f"{e['id']}.json"
            doc = {"slug": e["id"], "extracted_at": None, "sources_inspected": [],
                   "prices": [], "reservation": None, "hours": None,
                   "visitor_eligibility": None,
                   "_note": "no reachable public HTML during Phase A crawl"}
        else:
            out = L_RAW / "_source_blocks" / f"{e['id']}.json"
            doc = {"library_id": e["id"], "extracted_at": None,
                   "sources_inspected": [], "card_eligibility": None,
                   "_note": "no reachable public HTML during Phase A crawl"}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        n += 1
    return {"null_stubs": n}


# --- §7 verbatim prompt template (instructions block reproduced exactly) -------

_S7 = """You are extracting verifiable evidence passages from an official museum / library website for an audit dataset. Your output must let a human reviewer verify each structured fact against the original page text.

Entity: {NAME} (slug: {ID})
Type: {TYPE}

For each HTML file below, the text content is already extracted to readable paragraphs and shown after a "=== <filename> ===" header.

For each FIELD in the FIELDS list, do the following:

1. Find the passage on any of the inspected pages that establishes that fact. Prefer the deepest / most-specific page (e.g. /admission/ over the homepage).
2. Return the FULL paragraph (or up to 3 consecutive paragraphs) verbatim — do NOT paraphrase, do NOT truncate mid-sentence. The passage should be self-explanatory to a reader who has never seen this museum.
3. Also return the single most-specific sentence inside that passage as `source_phrase` (the "anchor" line that pinpoints the value).
4. Record the source URL and the input file path the passage came from.
5. Assign confidence: high / medium / low (see schema).
6. If no relevant passage exists on any inspected page, set the field to null. Do not invent.

{FIELDS}

Output ONLY the JSON. No markdown fence. No prose. Schema:

{SCHEMA}
"""

_FIELDS_ATTR = """FIELDS for an attraction:
- prices: an array, one entry per audience (adult, senior, youth, child, military, member). Each entry has audience, source_phrase, source_block, source_url, source_path, source_confidence.
- reservation: single object — does the visitor need to book a timed slot ahead?
- hours: single object — weekly opening hours.
- visitor_eligibility: single object — any visitor-side requirement (resident-only, members-only, etc.). null if none."""

_FIELDS_LIB = """FIELDS for a library:
- card_eligibility: single object — who is eligible to receive a library card from this library (residency / fee / partnership rules)."""

_SCHEMA_ATTR = """{
  "slug": "<ID>",
  "extracted_at": "2026-05-29T00:00:00Z",
  "sources_inspected": ["pages/<id>.html", "subpages/<id>__<sub>.html"],
  "prices": [
    {"audience": "adult", "source_phrase": "...", "source_block": "...", "source_url": "https://...", "source_path": "subpages/<id>__admission.html", "source_confidence": "high"}
  ],
  "reservation": {"source_phrase": "...", "source_block": "...", "source_url": "https://...", "source_path": "...", "source_confidence": "high"},
  "hours": {"source_phrase": "...", "source_block": "...", "source_url": "https://...", "source_path": "...", "source_confidence": "high"},
  "visitor_eligibility": null
}
Confidence ladder: high = passage uses the exact numbers/words of the structured value; medium = clearly about the field but no literal value; low = partial mention only; null = no passage found on any page (honest, do not invent, never emit empty string "")."""

_SCHEMA_LIB = """{
  "library_id": "<ID>",
  "extracted_at": "2026-05-29T00:00:00Z",
  "sources_inspected": ["_pages/<id>.html"],
  "card_eligibility": {"source_phrase": "...", "source_block": "...", "source_url": "https://...", "source_path": "_pages/<id>.html", "source_confidence": "high"}
}
Confidence ladder: high = passage uses the exact numbers/words of the structured value; medium = clearly about the field but no literal value; low = partial mention only; null = no passage found on any page (honest, do not invent, never emit empty string "")."""


def gen_prompts() -> dict:
    man = json.loads((ROOT / "data" / "raw" / "_source_block_manifest.json").read_text(encoding="utf-8"))
    pdir = ROOT / "data" / "raw" / "_prompts"
    pdir.mkdir(parents=True, exist_ok=True)
    for e in man:
        is_attr = e["kind"] == "attraction"
        body = _S7.format(
            NAME=e["name"], ID=e["id"], TYPE="attraction" if is_attr else "library",
            FIELDS=_FIELDS_ATTR if is_attr else _FIELDS_LIB,
            SCHEMA=(_SCHEMA_ATTR if is_attr else _SCHEMA_LIB).replace("<ID>", e["id"]),
        )
        out_rel = (f"data/raw/attractions/_source_blocks/{e['id']}.json" if is_attr
                   else f"data/raw/libraries/_source_blocks/{e['id']}.json")
        wrapper = (
            f"You are a Phase-B extraction subagent. Your entire task is below. Do exactly this and nothing else.\n\n"
            f"STEP 1. Read the readable-text dump for this entity:\n"
            f"  F:/pj/MuseumPapa/{e['stripped']}\n"
            f"It contains each inspected page's text after a `=== <filename> ===` header with its `source_url:` line.\n"
            f"`sources_inspected` for your JSON = {json.dumps(e['sources_inspected'])}\n\n"
            f"STEP 2. Follow these instructions EXACTLY (do not rewrite them):\n"
            f"------------------------------------------------------------\n{body}\n"
            f"------------------------------------------------------------\n\n"
            f"STEP 3. Write your JSON (UTF-8, valid JSON, the schema above) to:\n"
            f"  F:/pj/MuseumPapa/{out_rel}\n"
            f"Use `extracted_at`: \"2026-05-29T00:00:00Z\". `source_path` must be one of the sources_inspected paths.\n\n"
            f"STEP 4. Output ONLY the JSON object as your final message — no markdown fence, no prose.\n"
        )
        (pdir / f"{e['kind']}__{e['id']}.txt").write_text(wrapper, encoding="utf-8")
    return {"prompts": len(man)}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "prompts":
        print("prompts:", json.dumps(gen_prompts())); return
    if cmd in ("strip", "all"):
        print("strip:", json.dumps(strip_all()))
    if cmd in ("stubs", "all"):
        print("stubs:", json.dumps(write_null_stubs()))
    if cmd in ("manifest", "all"):
        man = json.loads((ROOT / "data" / "raw" / "_source_block_manifest.json").read_text(encoding="utf-8"))
        print(f"manifest: {len(man)} entities to dispatch")


if __name__ == "__main__":
    main()
