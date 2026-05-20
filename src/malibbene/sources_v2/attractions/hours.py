from pathlib import Path
from .llm_extract import write_extraction_request

PROMPT = """Extract opening hours from this museum's website.

Output JSON: {
  "hours": {
    "monday": "closed" | "10:00-17:00",
    "tuesday": ...,
    "wednesday":..., "thursday":..., "friday":..., "saturday":..., "sunday":...,
  },
  "seasonal": optional {"start_month":int,"end_month":int,"note":string},
  "source_phrase": verbatim
}

HTML:
{html}
"""

def enqueue(slug: str, html_path: Path, raw_root: Path) -> Path:
    return write_extraction_request("hours", slug, html_path,
                                     raw_root/"attractions"/"_pending", PROMPT)
