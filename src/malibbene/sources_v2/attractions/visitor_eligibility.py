from pathlib import Path
from .llm_extract import write_extraction_request

PROMPT = """You read the About / Visit / FAQ section of a museum's website.
Extract any RESIDENCY requirements for visitors (NOT for library pass holders).

Output JSON: {
  "residency": "ma_resident" | "town_resident" | "none" | "unknown",
  "scope": optional string like "Salem" or "MA",
  "locals_free": bool,
  "note": optional,
  "source_phrase": verbatim quote that supports your answer
}

HTML content:
{html}
"""

def enqueue(slug: str, html_path: Path, raw_root: Path) -> Path:
    return write_extraction_request(
        target_kind="visitor_eligibility", slug=slug, html_path=html_path,
        out_dir=raw_root/"attractions"/"_pending",
        prompt_template=PROMPT,
    )
