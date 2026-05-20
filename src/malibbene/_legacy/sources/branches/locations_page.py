"""Snapshot multi-branch library locations pages to data/raw/branches/.

Extraction (parse branch list -> name/address/hours) is intentionally NOT done
here -- that's a subagent task. This module only fetches HTML reliably so the
subagent has a deterministic input. See feedback-no-api-call: Python never
calls an LLM API; LLM work is dispatched as subagents that read these HTML
files via Read/Write tools.
"""
from __future__ import annotations

import json
from pathlib import Path

from malibbene.common.http import fetch

REPO_ROOT = Path(__file__).resolve().parents[4]
SEEDS_PATH = REPO_ROOT / "config" / "branch_seeds.json"
OUT_DIR = REPO_ROOT / "data" / "raw" / "branches"


def fetch_all() -> list[dict]:
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))["multi_branch_libs"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for entry in seeds:
        lib_id = entry["lib_id"]
        url = entry["locations_url"]
        try:
            html = fetch(url)
        except Exception as e:
            results.append({"lib_id": lib_id, "status": f"failed:{e}", "url": url})
            continue
        out = OUT_DIR / f"{lib_id}.html"
        out.write_text(html, encoding="utf-8")
        results.append({"lib_id": lib_id, "status": "ok", "bytes": len(html), "url": url})
    return results
