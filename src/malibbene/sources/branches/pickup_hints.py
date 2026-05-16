"""For BPL/Cambridge/Brookline only: re-fetch each pass detail page and slice
out the body section that mentions branches / pickup, save to a flat text file
the subagent can read without HTML noise.

Output: data/raw/branches/_pickup/<lib_id>/<pass_id>.txt   (one per pass)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from malibbene.common.http import fetch

REPO_ROOT = Path(__file__).resolve().parents[4]
INDEX_DIR = REPO_ROOT / "data" / "raw" / "libcal" / "index"
OUT_ROOT = REPO_ROOT / "data" / "raw" / "branches" / "_pickup"
TARGET_LIBS = ("bpl", "cambridge", "brookline")

# LibCal's pass detail page body lives in #s-lc-pass-desc; if that markup ever
# shifts, fall back to stripping all tags from the whole page.
BODY_RE = re.compile(r'<div[^>]*id="s-lc-pass-desc"[^>]*>(.*?)</div>', re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def _slice(html: str) -> str:
    m = BODY_RE.search(html)
    raw = m.group(1) if m else html
    return WS_RE.sub(" ", TAG_RE.sub(" ", raw)).strip()


def harvest() -> list[dict]:
    out: list[dict] = []
    for lib_id in TARGET_LIBS:
        idx_path = INDEX_DIR / f"{lib_id}.json"
        if not idx_path.exists():
            out.append({"lib_id": lib_id, "status": "missing_index"})
            continue
        data = json.loads(idx_path.read_text(encoding="utf-8"))
        lib_out = OUT_ROOT / lib_id
        lib_out.mkdir(parents=True, exist_ok=True)
        for p in data.get("passes", []):
            url = p.get("url")
            pass_id = p.get("slug") or p.get("pass_id")
            if not url or not pass_id:
                continue
            try:
                html = fetch(url)
            except Exception as e:
                out.append({"lib_id": lib_id, "pass": pass_id, "status": f"failed:{e}"})
                continue
            text = _slice(html)
            (lib_out / f"{pass_id}.txt").write_text(text, encoding="utf-8")
            out.append({"lib_id": lib_id, "pass": pass_id, "status": "ok", "chars": len(text)})
    return out
