# Plan · Source-block extraction for audit-grade evidence

> **Status**: ready to execute in a fresh Claude Code window.
> **Created**: 2026-05-29 by the coupon-map team
> **Estimated wall-time**: 60–90 min (mostly parallel subagent dispatch)
> **Token budget**: not a constraint per operator

---

## 1 · Why

The matrix popovers / drawer all surface a "Sources" section so the operator can verify any claim against original-source text. Today the underlying `source_phrase` fields are useless for that:

| Field today                                       | Sample content                                                                 | Why useless                                  |
| ------------------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------- |
| `attractions[].prices[i].source_phrase`           | `verified high confidence 2026-05 from americanheritagemuseum.org (online -$2)` | audit breadcrumb, not the actual page text   |
| `attractions[].reservation.source_phrase`         | 171-char snippet of nav menu + today's hours mashed together                   | scraped noise, not the booking policy        |
| `attractions[]._evidence.hours.evidence`          | `legacy original_price (2026-05-20 snapshot)`                                  | empty label, never had real content          |
| `libraries[]._evidence.card_eligibility.evidence` | usually missing                                                                | no evidence at all                           |

**The operator cannot audit data accuracy without the original passage.** Source quality is "the most important content" for audit confidence.

## 2 · Goal

Attach, to each fact in `data/structured/`, a `source_block` field containing the verbatim 1–3 paragraph passage from the official site that establishes that fact.

```jsonc
// example: attractions[].prices[i] after this work
{
  "audience": "adult",
  "price": 20,
  "age_range": { "min": 18, "max": null },
  "source_phrase":  "General Admission: $20",                  // the precise sentence
  "source_block":   "Admission\nGeneral Admission: $20\nSeniors (65+) ... children 6–12 are $10 and children under 6 are free.\nMembers always free.",  // the full passage
  "source_url":     "https://americanheritagemuseum.org/visit/admission/",
  "source_path":    "subpages/american-heritage-museum__admission.html",
  "source_confidence": "high"
}
```

## 3 · Scope

**437 source_blocks** total:

| Entity type | Count | Fields                                                                     |
| ----------- | ----- | -------------------------------------------------------------------------- |
| Attractions | 96    | `prices[i]` (avg ~4/entity) · `reservation` · `hours` · `visitor_eligibility` |
| Libraries   | 59    | `card_eligibility` (the residency requirement passage)                      |

Per operator decision: **full scope**, smart page selection, no POC stage — but **isolated per-entity execution** so one bad page can't pollute another extraction.

## 4 · Architecture (4 phases)

### Phase A · Subpage discovery (one window, batched)

For every entity, ensure we have the right HTML pages downloaded under `data/raw/attractions/{pages,subpages}/` and `data/raw/libraries/_pages/` (new dir for libs).

- `data/raw/attractions/pages/<slug>.html` — homepage, **already exists for all 96**.
- `data/raw/attractions/subpages/<slug>__<subpath>.html` — deep pages. **Partially exists** (boston-athenaeum has 1, american-heritage has 4). For each attraction:
  1. Read `pages/<slug>.html`.
  2. LLM picks up to 3 candidate deep-page URLs whose visible link text or path looks like a fit for **tickets / admission / visit / plan-your-visit / pricing / hours / reservation / book / about**.
  3. Fetch each candidate (HTTP GET with browser UA, follow redirects, save 200s only). Subpath slug in filename is the last URL segment, lowercased, with `-` separators.
  4. Skip if `subpages/<slug>__<sub>.html` already exists (idempotent).
- `data/raw/libraries/_pages/<lib_id>.html` — fetch `library.card_page` URL (already in `data/structured/libraries.json`) for each of the 59 libs that has one.

**Output of Phase A**: every entity has ≥1 (usually 2–4) HTML files representing its public-facing content.

### Phase B · Per-entity LLM extraction (parallel subagent dispatch)

This is the **isolation boundary** the operator asked for. **One subagent per entity** — clean context, no cross-contamination between entities.

For each of the 155 entities (96 attractions + 59 libs):

1. Read all relevant HTML files (`pages/<slug>.html` + every `subpages/<slug>__*.html`, or for libs the `_pages/<lib_id>.html`).
2. Strip HTML to readable text (preserve paragraph boundaries). A simple regex pass is enough — LLM doesn't need pristine output, it needs the paragraphs in order.
3. Call LLM with a tightly-scoped prompt asking ONLY about that one entity. Return JSON exactly matching the schema in §6.
4. Write to `data/raw/attractions/_source_blocks/<slug>.json` (or `data/raw/libraries/_source_blocks/<lib_id>.json`).

**Concurrency**: dispatch via the controller's Agent tool with `subagent_type: general-purpose`. Batch in groups of 10 per round to keep the controller's working set small. ~155 / 10 = ~16 rounds, fully sequential rounds. Roughly **60 min** for this phase.

**Why one-per-entity, not one-per-field**: a single subagent reading all the HTML for one museum and emitting all four fields in one JSON is cheaper AND more accurate (e.g. it can cross-check that the price block and the reservation block don't overlap). Splitting per field would multiply subagent dispatches by 4×.

### Phase C · Merge into structured data

A single CLI re-builds the structured products with the new `source_block` field plumbed through.

1. Add `source_block`, `source_url`, `source_path`, `source_confidence` to the relevant schema sites in `src/malibbene/build/{attractions,libraries}.py`.
2. For each entity, read its `_source_blocks/<id>.json` and overlay onto the build output:
   - Attractions: each `prices[i]` gets the matching `source_block` by audience; `reservation`, `_evidence.hours`, `_evidence.visitor_eligibility` get theirs.
   - Libraries: `_evidence.card_eligibility` gets the residency passage.
3. Re-run `python scripts/build_all.py`.
4. Re-run `pnpm -C coupon-map run dev`'s predev sync to ship the new data to `coupon-map/public/data/`.

### Phase D · Frontend wire-up

Render `source_block` everywhere the matrix currently renders the brittle `source_phrase`:

- `coupon-map/src/components/BookingDrawer.tsx` — Sources section (already uses `coupon.source_phrase_block`; extend pattern to residency / probe).
- `coupon-map/src/pages/Matrix.tsx` — `EvidenceSection` items: change `quote:` field from `…source_phrase` to `…source_block || …source_phrase`. Keep `source_phrase` as a fallback for entities that weren't re-extracted (shouldn't happen but safety net).

## 5 · Repo paths (exact)

```
F:/pj/MuseumPapa/
├── data/
│   ├── structured/
│   │   ├── attractions.json     ← target of Phase C
│   │   ├── libraries.json       ← target of Phase C
│   │   └── passes.json          ← unchanged (coupon source already exists)
│   └── raw/
│       ├── attractions/
│       │   ├── pages/<slug>.html             ← homepage, all 96 present
│       │   ├── subpages/<slug>__<sub>.html    ← deep pages, partial
│       │   └── _source_blocks/<slug>.json    ← NEW, written by Phase B
│       └── libraries/
│           ├── _pages/<lib_id>.html          ← NEW, fetched in Phase A
│           └── _source_blocks/<lib_id>.json  ← NEW, written by Phase B
├── src/malibbene/build/
│   ├── attractions.py            ← extend in Phase C
│   └── libraries.py              ← extend in Phase C
├── scripts/
│   ├── crawl_subpages.py         ← NEW, Phase A
│   ├── extract_source_blocks.py  ← NEW, Phase B controller
│   └── build_all.py              ← run as-is in Phase C
└── coupon-map/src/
    ├── components/BookingDrawer.tsx  ← edit in Phase D
    └── pages/Matrix.tsx              ← edit in Phase D
```

## 6 · Output JSON schema (Phase B)

One file per entity, mirroring the structured-data shape for that entity:

```jsonc
// data/raw/attractions/_source_blocks/<slug>.json
{
  "slug": "american-heritage-museum",
  "extracted_at": "2026-05-29T...",
  "sources_inspected": [
    "pages/american-heritage-museum.html",
    "subpages/american-heritage-museum__admission.html",
    "subpages/american-heritage-museum__visit.html"
  ],
  "prices": [
    {
      "audience": "adult",
      "source_phrase": "General Admission: $20",
      "source_block":  "Admission\nGeneral Admission: $20\nSeniors (65+) and active military with ID: $17 ...",
      "source_url":    "https://americanheritagemuseum.org/visit/admission/",
      "source_path":   "subpages/american-heritage-museum__admission.html",
      "source_confidence": "high"
    },
    { "audience": "senior", ... },
    { "audience": "child",  ... }
  ],
  "reservation": {
    "source_phrase": "Walk-ins welcome, no reservation required",
    "source_block":  "Plan Your Visit\nThe museum is open Tuesday through Sunday ... Walk-ins are welcome, no reservation needed.",
    "source_url":    "https://americanheritagemuseum.org/visit/",
    "source_path":   "subpages/american-heritage-museum__visit.html",
    "source_confidence": "high"
  },
  "hours": {
    "source_phrase": "Open Tue–Sun 10 am – 5 pm",
    "source_block":  "Hours\nMon: Closed\nTuesday – Sunday: 10 am – 5 pm\nLast admission 4 pm.",
    "source_url":    "https://americanheritagemuseum.org/visit/hours/",
    "source_path":   "subpages/american-heritage-museum__hours.html",
    "source_confidence": "high"
  },
  "visitor_eligibility": null   // when the page has no relevant passage
}
```

```jsonc
// data/raw/libraries/_source_blocks/<lib_id>.json
{
  "library_id": "lexington",
  "extracted_at": "2026-05-29T...",
  "sources_inspected": ["_pages/lexington.html"],
  "card_eligibility": {
    "source_phrase": "Cary Memorial Library cards are free to all Massachusetts residents",
    "source_block":  "Library Cards\nCary Memorial Library cards are free to all Massachusetts residents over the age of 5 ... non-residents may apply for a card for an annual fee.",
    "source_url":    "https://carylibrary.org/get-a-library-card/",
    "source_path":   "_pages/lexington.html",
    "source_confidence": "high"
  }
}
```

Confidence ladder:
- `high` — the passage uses the exact numbers/words that appear in our extracted structured value.
- `medium` — the passage is clearly about the field but doesn't contain the literal value (e.g. price page links to a PDF).
- `low` — best-effort guess. Set when the only hit is a partial mention.
- field set to `null` — no passage found on any inspected page. Honest.

## 7 · Phase B LLM prompt template (USE EXACTLY)

```
You are extracting verifiable evidence passages from an official museum / library website for an audit dataset. Your output must let a human reviewer verify each structured fact against the original page text.

Entity: <ENTITY_NAME> (slug: <SLUG>)
Type: attraction | library

For each HTML file below, the text content is already extracted to readable paragraphs and shown after a "=== <filename> ===" header.

For each FIELD in the FIELDS list, do the following:

1. Find the passage on any of the inspected pages that establishes that fact. Prefer the deepest / most-specific page (e.g. /admission/ over the homepage).
2. Return the FULL paragraph (or up to 3 consecutive paragraphs) verbatim — do NOT paraphrase, do NOT truncate mid-sentence. The passage should be self-explanatory to a reader who has never seen this museum.
3. Also return the single most-specific sentence inside that passage as `source_phrase` (the "anchor" line that pinpoints the value).
4. Record the source URL and the input file path the passage came from.
5. Assign confidence: high / medium / low (see schema).
6. If no relevant passage exists on any inspected page, set the field to null. Do not invent.

FIELDS for an attraction:
- prices: an array, one entry per audience (adult, senior, youth, child, military, member). Each entry has audience, source_phrase, source_block, source_url, source_path, source_confidence.
- reservation: single object — does the visitor need to book a timed slot ahead?
- hours: single object — weekly opening hours.
- visitor_eligibility: single object — any visitor-side requirement (resident-only, members-only, etc.). null if none.

FIELDS for a library:
- card_eligibility: single object — who is eligible to receive a library card from this library (residency / fee / partnership rules).

Output ONLY the JSON. No markdown fence. No prose. Schema:

{ ...as in §6 of the plan... }
```

The controller wraps each subagent dispatch with the entity name, slug, type, fields list, and the readable-text dump of every relevant HTML file (homepage + every matching subpage).

## 8 · Build-pipeline wiring (Phase C)

`build_attractions.py` and `build_libraries.py` already overlay overrides via `apply_overrides`. Add a separate overlay pass for source_blocks:

```python
# pseudo, after the existing apply_overrides:
sb_path = Path("data/raw/attractions/_source_blocks") / f"{a['slug']}.json"
if sb_path.exists():
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    # match prices by audience; reservation/hours/visitor_eligibility direct.
    for p in a["prices"]:
        match = next((x for x in (sb.get("prices") or []) if x["audience"] == p["audience"]), None)
        if match:
            p["source_block"]      = match.get("source_block")
            p["source_url"]        = match.get("source_url")
            p["source_confidence"] = match.get("source_confidence")
    for fld in ("reservation",):
        if sb.get(fld):
            a[fld] = {**(a.get(fld) or {}),
                      "source_block":      sb[fld].get("source_block"),
                      "source_url":        sb[fld].get("source_url"),
                      "source_confidence": sb[fld].get("source_confidence")}
    # hours and visitor_eligibility go under a["_evidence"][field]
    for fld in ("hours", "visitor_eligibility"):
        if sb.get(fld):
            a.setdefault("_evidence", {})[fld] = {
                "evidence":          sb[fld].get("source_phrase"),
                "block":             sb[fld].get("source_block"),
                "source":            sb[fld].get("source_url"),
                "source_confidence": sb[fld].get("source_confidence"),
            }
```

Mirror for libraries: `_source_blocks/<lib_id>.json.card_eligibility` → `l._evidence.card_eligibility.{evidence,block,source,source_confidence}`.

After both functions are updated:
```powershell
python scripts/build_all.py
pnpm -C F:\pj\MuseumPapa\coupon-map run build   # picks up the new data via predev/prebuild sync hook
```

## 9 · Frontend wire-up (Phase D)

Two files:

1. **`coupon-map/src/components/BookingDrawer.tsx`** — Sources section already exists. It currently reads `coupon.source_phrase_block`. The new schema gives us:
   - `pass.residency_restriction.evidence` (existing) + `pass.residency_restriction.block` (NEW from Phase C plumbing — verify if you want this routed too; pass-level coupon source already has phrase_block).
   - For each `<article className="src-card">` rendering `<blockquote className="src-quote">`, prefer the `*_block` field, fall back to `*_phrase`.

2. **`coupon-map/src/pages/Matrix.tsx`** — `EvidenceSection` items (lib popover + branch popover + attraction popover):
   - Change each `quote: …source_phrase` (legacy) to `quote: …block || …source_phrase`.
   - The data shape for the library popover comes from `library._evidence.card_eligibility` and now has `.block` alongside `.evidence`.

3. **`coupon-map/src/data/types.ts`** — extend the TS interfaces:
   - `interface Price { …; source_block?: string; source_confidence?: "high"|"medium"|"low"; source_url?: string }`
   - `interface Reservation { …; source_block?: string; source_confidence?: …; source_url?: string }`
   - `interface _EvidenceEntry { evidence?: string; block?: string; source?: string; source_confidence?: …}` for `_evidence.hours`, `_evidence.card_eligibility`, `_evidence.visitor_eligibility`.

## 10 · Acceptance criteria

A pass:
- [ ] Every attraction in `data/structured/attractions.json` has `_evidence.hours.block` or `null` honestly recorded.
- [ ] Every price row that has a real audience has either `source_block` populated or `source_confidence: null`.
- [ ] Every library in `data/structured/libraries.json` has `_evidence.card_eligibility.block` or `null`.
- [ ] Frontend `pnpm exec tsc --noEmit` returns 0.
- [ ] Five spot-checks: open the drawer for 5 different (library, attraction) pairs spanning Assabet / LibCal / MuseumKey, and the Sources card actually shows a multi-paragraph passage that visibly mentions the structured value.
- [ ] `dist/` builds clean; `vite build` green.

## 11 · Kickoff incantation — what to paste in the new window

Open a fresh Claude Code window pointed at `F:/pj/MuseumPapa`, then paste exactly:

```
Read F:/pj/MuseumPapa/docs/plan_source_block_extraction.md end-to-end. That is the spec. Execute all four phases (A → B → C → D) faithfully, in order. Do not skip phases. Do not POC. Do not ask scope questions — the plan answers them.

Honor these constraints:
- One subagent per entity for Phase B (isolation). Batch dispatches in groups of 10 entities per round; await each round before kicking the next.
- Use the JSON schema in §6 exactly. Output ONLY JSON from every subagent (no markdown, no prose).
- Use the prompt template in §7 verbatim — fill the placeholders, do not rewrite the instructions.
- If a page returns 4xx/5xx during Phase A, skip silently and proceed; don't retry beyond 1 attempt.
- Commit at the end of each phase: A → "scrape: deep subpages + lib card_page HTML"; B → "extract: source blocks for 96 attractions + 59 libs"; C → "build: plumb source_block through structured data"; D → "ui: render source_block in popovers + drawer".
- Use `git -C F:/pj/MuseumPapa` form for all git ops (the workspace CLAUDE.md forbids cd && git).
- When you finish Phase D, post a one-paragraph summary including: total entities processed, # with high-confidence blocks per field, # of null/missing fields, and the 5 sample (lib, attr) pairs you spot-checked.

Begin Phase A immediately.
```

That's the only thing the operator pastes. Everything else is read from the plan file.

## 12 · What NOT to do

- Do **not** retry the same entity inside the same window if a subagent returns an error — write the partial result, move on, log the failures, and have the operator decide whether to rerun. (Time and tokens aren't constraints, but one repeating failure isn't going to fix itself.)
- Do **not** ship empty `source_block: ""` — use `null` when honestly missing.
- Do **not** edit `data/structured/attractions.json` or `libraries.json` directly. Only the build pipeline writes those — your changes go through `scripts/build_all.py`.
- Do **not** modify the matrix popover's HTML structure. The plan is to swap the QUOTE content, not the layout.
- Do **not** delete or rename existing `source_phrase` fields. They stay as fallbacks; the new `source_block` is an addition.

## 13 · Rollback

If anything looks wrong:
```powershell
git -C F:/pj/MuseumPapa restore data/structured/ data/raw/attractions/_source_blocks/ data/raw/libraries/_source_blocks/ data/raw/libraries/_pages/
git -C F:/pj/MuseumPapa checkout -- src/malibbene/build/ coupon-map/src/
```
The current branch (`main`) is the operator's working branch; commits made in execution can be soft-reset and the new files can be cleared individually if Phase B or C produced bad output.

---

**Plan ends. Begin execution by reading this file in a new window and pasting the kickoff incantation from §11.**
