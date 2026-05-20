"""Enqueue coupon LLM-extraction requests, one per (library, attraction) pass.

Reads catalog files from data/raw/<platform>/catalog/<lib>.json. For each pass
with non-empty benefit_text or source_phrases, writes a pending request to
data/raw/<platform>/_pending/coupons/<lib>__<slug>.json. A subagent later
fulfils these by writing data/raw/<platform>/coupons/<lib>__<slug>.json — the
location that build/passes.py already reads.
"""
from __future__ import annotations
import json
from pathlib import Path

PROMPT = """You read a library museum-pass benefit description and extract a
structured Coupon record describing what the pass gives the visitor.

Input variables:
- library: {library_id}
- attraction: {attraction_slug}
- benefit_text: verbatim text from the library's pass listing
- source_phrases: list of paragraph-level quotes from the listing page

Output JSON:
{{
  "status": "ok",
  "extracted": {{
    "pass_form": "digital_email" | "physical_circ" | "physical_coupon",
    "coupon": {{
      "capacity": {{"kind": "people"|"vehicle"|"ticket"|"unspecified", "n": int|null}},
      "audience_policies": [
        {{"audience": "Everyone"|"adults"|"children"|"youth"|"seniors"|"family",
          "form": "free"|"percent-off"|"dollar-off"|"per-person-price"|"bogo"|"discount",
          "value": number|null,
          "count": int|null,
          "age_range": {{"min":int,"max":int}}|null,
          "source_phrase": "verbatim quote"}}
      ],
      "summary": "mobile-app one-liner like '50% off' or 'FREE' or '$5 off'",
      "source_phrase_block": "verbatim full benefit block"
    }},
    "restrictions": {{
      "blackout": [{{"month":int,"day":int}}, ...],
      "blackout_recurring": ["sundays","mondays",...],
      "weekdays_only": bool,
      "seasonal": {{"start_month":int,"end_month":int}}|null,
      "advance_booking_required": bool,
      "advance_booking_hours": int|null
    }} | null
  }}
}}

Guidance:
- "Passes admit 4 people for 50% off" => capacity {{people,4}}, audience_policy
  {{Everyone, percent-off, 50}}, summary "50% off".
- "2-for-1 ferry fees" or "buy one get one" => form "bogo".
- "Adults $10/person, children 7-17 $10/person" => two audience_policies,
  form per-person-price, value 10 each.
- "FREE admission" or "no charge" => form "free", value 0.
- "Printable/Digital Coupon Pass" => pass_form "digital_email".
- "must be picked up from the branch" => pass_form "physical_circ" (loanable item).
- If benefit text is ONLY navigation text (e.g. "click on the desired day"),
  return status "failed" with error "no benefit text available".

benefit_text:
\"\"\"
{benefit_text}
\"\"\"

source_phrases:
{source_phrases_joined}
"""


def enqueue_coupon(
    library_id: str,
    attraction_slug: str,
    benefit_text: str,
    source_phrases: list[str],
    platform: str,
    raw_root: Path,
) -> Path:
    pending_dir = raw_root / platform / "_pending" / "coupons"
    pending_dir.mkdir(parents=True, exist_ok=True)
    out = pending_dir / f"{library_id}__{attraction_slug}.json"
    out.write_text(
        json.dumps(
            {
                "status": "pending",
                "target_kind": "coupons",
                "library_id": library_id,
                "attraction_slug": attraction_slug,
                "platform": platform,
                "benefit_text": benefit_text,
                "source_phrases": source_phrases,
                "prompt_template": PROMPT,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out
