from pathlib import Path
from .llm_extract import write_extraction_request

PROMPT = """Extract general admission prices per audience from this museum's website.

Output JSON: {
  "prices": [
    {"audience": "adult"|"child"|"senior"|"youth"|"student"|"military"|"educator"|"family",
     "price": number or null (USD), "age_range": {"min":int,"max":int} or null,
     "source_phrase": verbatim}
  ]
}

HTML:
{html}
"""

def enqueue(slug: str, html_path: Path, raw_root: Path) -> Path:
    return write_extraction_request("prices", slug, html_path,
                                     raw_root/"attractions"/"_pending", PROMPT)
