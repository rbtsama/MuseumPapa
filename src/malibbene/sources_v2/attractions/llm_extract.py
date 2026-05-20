"""LLM extraction contract. Python writes pending requests; subagents fulfill them."""
from __future__ import annotations
import json
from pathlib import Path

def write_extraction_request(target_kind: str, slug: str, html_path: Path,
                              out_dir: Path, prompt_template: str) -> Path:
    d = out_dir / target_kind
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{slug}.json"
    f.write_text(json.dumps({
        "status":"pending", "target_kind":target_kind, "slug":slug,
        "html_path": str(html_path), "prompt_template": prompt_template,
    }, indent=2, ensure_ascii=False))
    return f

def load_extraction_result(target_kind: str, slug: str, base_dir: Path) -> dict:
    f = base_dir / target_kind / f"{slug}.json"
    if not f.exists():
        return {"status":"missing"}
    return json.loads(f.read_text())
