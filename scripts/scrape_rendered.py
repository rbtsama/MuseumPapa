"""Playwright-rendered recovery pass for pages plain urllib can't get.

Two recovery jobs, both idempotent and reproducible:

1. WAF-blocked library *card-eligibility* pages
   -----------------------------------------------
   A couple of municipal library "get a library card" pages sit behind a WAF
   (Cloudflare / WP-Engine bot rules) that returns 403 to plain urllib but
   serve fine to a real headless browser. We re-fetch them with
   ``render_js=True``, run the deterministic eligibility classifier on the
   text, and write ``data/raw/<platform>/policies/<lib>.json`` (merging the
   recovered ``card_page`` into whatever pass-page policy already exists).

2. JS-rendered attraction opening hours
   -------------------------------------
   Some museum sites load their hours via a JS widget, so the urllib snapshot
   has all 7 days "unknown". We re-fetch the museum's /visit or /hours page
   with ``render_js=True``, save the rendered HTML to
   ``data/raw/attractions/subpages/<slug>__rendered.html``, then re-run the
   existing ``extract_hours`` logic. We only overwrite the stored hours JSON if
   the rendered version yields MORE known days than the current one — never a
   regression.

HONESTY: if Playwright also can't get a page (headless detection, genuine
403, or the page simply has no hours), we record that honestly. We never
fabricate hours or eligibility.

Run::

    python scripts/scrape_rendered.py            # both jobs
    python scripts/scrape_rendered.py policies   # only job 1
    python scripts/scrape_rendered.py hours      # only job 2
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

SEEDS_PATH = ROOT / "config" / "library_seeds.json"

from malibbene.common.http import fetch  # noqa: E402
from malibbene.common.eligibility_text import (  # noqa: E402
    classify_card_eligibility,
    classify_pass_pickup,
)
from malibbene.sources_v2.assabet.policies import extract_policy_text  # noqa: E402
from malibbene.sources_v2.attractions.extract_hours import extract_hours  # noqa: E402
from malibbene.sources_v2.attractions.extract_visitor_eligibility import (  # noqa: E402
    html_to_text,
)


def _eligibility_source_phrase(text: str) -> str | None:
    """Verbatim ~160-char window around the residency cue, for provenance."""
    import re

    m = re.search(
        r"(massachusetts\s+residents?|residents?\s+of\s+massachusetts"
        r"|residents?\s+of\s+(?:the\s+)?commonwealth"
        r"|resident\s+of\s+(?:the\s+)?commonwealth\s+of\s+massachusetts"
        r"|eligible\s+for\s+a\s+library\s+card\s+if"
        r"|lives?\s+(?:anywhere\s+)?in\s+massachusetts"
        r"|(?:have|with)\s+a\s+massachusetts\s+address"
        r"|[A-Z][a-zA-Z]+\s+residents?\s+(?:is|are)\s+eligible"
        r"|anyone\s+can\s+get\s+one"
        r"|residents?\s+only|live[,\s].{0,40}work|attend\s+school)",
        text,
        re.I,
    )
    if not m:
        return None
    a = max(0, m.start() - 60)
    b = min(len(text), m.end() + 90)
    return text[a:b].strip()

RAW = ROOT / "data" / "raw"


# ---------------------------------------------------------------------------
# Job 1 — WAF-blocked library card-eligibility pages
# ---------------------------------------------------------------------------

# Seed-driven recovery (primary): every seed library flagged
# ``requires_render_js: true`` is rendered with Playwright using its own
# ``card_page`` (and, as a fallback candidate, its ``pass_page``). Flagging a
# new lib = adding ``requires_render_js: true`` + a correct ``card_page`` to its
# seed in config/library_seeds.json, then running this script.
#
# WAF_CARD_PAGES below is an EXTRA fallback candidate map: if a lib's seed
# card_page doesn't render an eligibility cue, any extra candidate URLs listed
# here for that lib_id are also tried. The seed flag is the primary driver — a
# lib does NOT need a WAF_CARD_PAGES entry to be processed.
WAF_CARD_PAGES: dict[str, dict] = {
    "tewksbury": {
        "platform": "assabet",
        "candidates": [
            "https://www.tewksburypl.org/about-us/pages/get-library-card",
            "https://www.tewksburypl.org/about-us/pages/library-card-applications",
        ],
    },
    "arlington": {
        "platform": "assabet",
        "candidates": [
            "https://www.robbinslibrary.org/about/library-card/",
            "https://www.robbinslibrary.org/library-card/",
        ],
    },
}


def _load_render_seeds() -> list[dict]:
    """Seed libraries flagged ``requires_render_js: true`` (the primary driver)."""
    data = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    seeds = data["libraries"] if isinstance(data, dict) else data
    return [s for s in seeds if s.get("requires_render_js")]


def _candidate_urls(seed: dict) -> list[str]:
    """Ordered, de-duplicated candidate URLs for one seed library.

    Priority: seed ``card_page`` first (the real get-a-card page), then any
    extra URLs from WAF_CARD_PAGES for this lib_id, then the seed ``pass_page``
    as a last resort (some pass pages embed the residency rule).
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(u: str | None) -> None:
        if u and u not in seen:
            seen.add(u)
            out.append(u)

    _add(seed.get("card_page"))
    extra = WAF_CARD_PAGES.get(seed["id"], {}).get("candidates", [])
    for u in extra:
        _add(u)
    _add(seed.get("pass_page"))
    return out


# Number of render attempts per candidate URL — some municipal sites render
# only a partial shell on the first hit (lazy hydration) and the full body on
# a retry. We retry until the eligibility cue appears or the budget runs out.
_RENDER_RETRIES = 4


def _is_bad_page(html: str) -> bool:
    """True if the rendered HTML is a 404 / WAF-block / bot-challenge shell
    rather than a real content page."""
    low = html.lower()
    bad = ("page not found", "404 not found", "access denied", "just a moment",
           "checking your browser", "attention required",
           "your access to this page has been blocked", "custom404")
    return any(b in low for b in bad)


def _has_eligibility_cue(html: str) -> bool:
    """True only if the rendered page contains an actual card-eligibility
    statement we can classify — not just the words 'library card' in a nav.

    A page passes when (a) it is not a 404/WAF shell AND (b) the deterministic
    classifier finds a genuine eligibility statement in the flattened body text.
    Anchoring the gate on the classifier (rather than a hand-kept keyword list)
    keeps the gate honest and in lock-step with the only thing that ever sets a
    non-unknown value — if the classifier won't classify it, we don't accept it.
    A few coarse keyword cues are still accepted as a fast path for the common
    idioms so the gate doesn't depend on classifier import ordering.
    """
    if _is_bad_page(html):
        return False
    low = html.lower()
    cues = (
        "resident of massachusetts", "massachusetts resident",
        "residents only", "must present", "eligible to apply",
        "live, work", "live or work", "attend school",
        "live in massachusetts", "lives in massachusetts",
        "live anywhere in massachusetts", "massachusetts address",
        "resident is eligible", "anyone can get one",
        "regardless of where you live in massachusetts",
    )
    if any(c in low for c in cues):
        return True
    # Fall back to the real classifier on the flattened body text.
    text = html_to_text(html)
    return classify_card_eligibility(text).value != "unknown"


def recover_policies() -> list[dict]:
    results: list[dict] = []
    seeds = _load_render_seeds()
    if not seeds:
        print("[policies] no seed libraries flagged requires_render_js:true")
    for seed in seeds:
        lib_id = seed["id"]
        platform = seed["platform"]
        candidates = _candidate_urls(seed)
        out_path = RAW / platform / "policies" / f"{lib_id}.json"
        existing = (
            json.loads(out_path.read_text(encoding="utf-8"))
            if out_path.exists()
            else {"library_id": lib_id}
        )

        recovered_url = None
        card_policy = None
        last_error = "no candidate URLs in seed (card_page/pass_page both null)"
        html = None
        for url in candidates:
            html = None
            for _ in range(_RENDER_RETRIES):
                try:
                    candidate_html = fetch(url, render_js=True, force=True, timeout=45)
                except Exception as e:  # network / launch / nav timeout
                    last_error = f"{type(e).__name__}: {e}"
                    continue
                if _has_eligibility_cue(candidate_html):
                    html = candidate_html
                    break
                last_error = "rendered but no eligibility cue (partial render / WAF block)"
            if html is None:
                continue
            # extract_policy_text keeps only the first 30 text blocks; on
            # nav-heavy municipal pages the eligibility sentence sits below
            # that cut. We classify against the FULL flattened page text (real
            # content, not fabricated) AND persist that same full_text as
            # policy_text — otherwise reclassify_policies.py (which re-derives
            # from the persisted policy_text) would lose the eligibility cue and
            # silently revert the lib to unknown on the next run.
            full_text = html_to_text(html)
            card_policy = {
                "policy_text": full_text,
                "card_eligibility": classify_card_eligibility(full_text).value,
                "pass_pickup": classify_pass_pickup(full_text).value,
                "eligibility_source_phrase": _eligibility_source_phrase(full_text),
            }
            recovered_url = url
            break

        if card_policy is not None:
            existing["card_page_url"] = recovered_url
            existing["card_page"] = card_policy
            existing.setdefault("pass_page_url", existing.get("pass_page_url"))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            results.append({
                "lib": lib_id,
                "status": "recovered",
                "url": recovered_url,
                "card_eligibility": card_policy["card_eligibility"],
                "pass_pickup": card_policy["pass_pickup"],
            })
            print(f"[policies] {lib_id}: RECOVERED via {recovered_url} "
                  f"-> card_eligibility={card_policy['card_eligibility']}")
        else:
            results.append({
                "lib": lib_id,
                "status": "blocked",
                "reason": last_error,
                "tried": candidates,
            })
            print(f"[policies] {lib_id}: STILL BLOCKED ({last_error})")
    return results


# ---------------------------------------------------------------------------
# Job 2 — JS-rendered attraction opening hours
# ---------------------------------------------------------------------------

# slug -> the visit/hours page to render. Explicit so a future operator sees
# exactly which URL each recovery used. The named targets from the brief plus
# every slug whose stored hours are all-unknown.
def _all_unknown_slugs() -> list[str]:
    out = []
    hdir = RAW / "attractions" / "hours"
    for f in sorted(hdir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        ex = d.get("extracted", d)
        h = ex.get("hours", {})
        if h and all(v == "unknown" for v in h.values()):
            out.append(f.stem)
    return out


def _website_for(slug: str) -> str | None:
    apath = ROOT / "data" / "structured" / "attractions.json"
    if not apath.exists():
        return None
    data = json.loads(apath.read_text(encoding="utf-8"))
    arr = data if isinstance(data, list) else data.get("attractions", [])
    for a in arr:
        if a.get("slug") == slug:
            return a.get("website")
    return None


def _hours_subpaths(base: str) -> list[str]:
    """Candidate visit/hours sub-URLs to try for a museum homepage."""
    base = base.rstrip("/")
    return [
        base + "/visit",
        base + "/hours",
        base + "/plan-your-visit",
        base + "/visit/hours",
        base + "/admission",
        base,  # homepage as last resort
    ]


# Named targets always attempted, even if not currently all-unknown.
NAMED_HOURS_TARGETS = [
    "zoo-new-england",
    "the-discovery-museums",
    "worcester-art-museum",
]


def _known_day_count(hours: dict) -> int:
    return sum(1 for v in hours.values() if v != "unknown")


def recover_hours() -> list[dict]:
    slugs = list(dict.fromkeys(NAMED_HOURS_TARGETS + _all_unknown_slugs()))
    results: list[dict] = []
    sub_dir = RAW / "attractions" / "subpages"
    sub_dir.mkdir(parents=True, exist_ok=True)
    hours_dir = RAW / "attractions" / "hours"

    for slug in slugs:
        cur_path = hours_dir / f"{slug}.json"
        cur = (
            json.loads(cur_path.read_text(encoding="utf-8"))
            if cur_path.exists()
            else {}
        )
        cur_ex = cur.get("extracted", cur)
        cur_known = _known_day_count(cur_ex.get("hours", {}))

        website = _website_for(slug)
        if not website:
            results.append({"slug": slug, "status": "no_website",
                            "known_before": cur_known})
            print(f"[hours] {slug}: no website in attractions.json — skipped")
            continue

        rendered_html = None
        used_url = None
        last_error = None
        for url in _hours_subpaths(website):
            try:
                html = fetch(url, render_js=True, force=True, timeout=45)
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                continue
            if html and len(html) > 500:
                rendered_html = html
                used_url = url
                break

        if rendered_html is None:
            results.append({"slug": slug, "status": "fetch_failed",
                            "reason": last_error, "known_before": cur_known})
            print(f"[hours] {slug}: render failed ({last_error})")
            continue

        # Save rendered HTML as a subpage so extract_hours (which reads
        # subpages/<slug>__*.html) can consume it, and it's reproducible.
        rendered_path = sub_dir / f"{slug}__rendered.html"
        rendered_path.write_text(
            f"<!-- source_url: {used_url} (playwright-rendered) -->\n" + rendered_html,
            encoding="utf-8",
        )

        new = extract_hours(slug, RAW)
        new_ex = new.get("extracted", new)
        new_known = _known_day_count(new_ex.get("hours", {}))

        if new_known > cur_known:
            cur_path.write_text(
                json.dumps(new, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            results.append({
                "slug": slug, "status": "improved",
                "known_before": cur_known, "known_after": new_known,
                "url": used_url,
                "source_phrase": new_ex.get("source_phrase"),
            })
            print(f"[hours] {slug}: IMPROVED {cur_known}->{new_known} known days "
                  f"via {used_url}")
        else:
            # Keep the rendered subpage on disk (reproducible) but don't regress
            # the stored JSON.
            results.append({
                "slug": slug, "status": "no_gain",
                "known_before": cur_known, "known_after": new_known,
                "url": used_url,
            })
            print(f"[hours] {slug}: no gain ({cur_known}->{new_known}); kept existing")
    return results


def main(argv: list[str]) -> None:
    job = argv[1] if len(argv) > 1 else "all"
    summary: dict = {}
    if job in ("all", "policies"):
        summary["policies"] = recover_policies()
    if job in ("all", "hours"):
        summary["hours"] = recover_hours()

    print("\n=== scrape_rendered summary ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv)
