from pathlib import Path
from .llm_extract import write_extraction_request

PROMPT = """Read this museum's visit / ticketing / FAQ section.

Extract reservation policy:
- required: "none" | "timed_entry" | "walk_in_ok"
- booking_url: link if any
- lead_time_hours: minimum advance booking time in hours (int) or null
- pass_holder_path: "promo_code_in_general_checkout" | "dedicated_pass_sku" | "dedicated_pass_holders_url" | "library_only" | "unknown"
- pass_holder_url: link for pass holders if any
- source_phrase: verbatim quote supporting your answer

Output JSON only.

HTML:
{html}
"""

def enqueue(slug: str, html_path: Path, raw_root: Path) -> Path:
    return write_extraction_request(
        target_kind="reservation", slug=slug, html_path=html_path,
        out_dir=raw_root/"attractions"/"_pending",
        prompt_template=PROMPT,
    )
