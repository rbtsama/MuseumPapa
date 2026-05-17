# Plan 10 — Dedupe Attraction Slugs + Strip Audit Verbosity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the final 2 gaps from the audit review series:
1. Merge 8 known-duplicate attraction-slug pairs so each museum is a single entity.
2. Strip 22 `methodology` transitional-explanation blocks from audit pages now that data is clean.

**Architecture:** Task 1 is a deterministic data-layer fix — add a `LEGACY_SLUG_TO_CANONICAL` map in build, route legacy slugs to the canonical entity during accumulation, regenerate. Task 2 is a mechanical edit on `scripts/build_audit_site.py` — delete all `<p class="methodology">` blocks except a single minimal "what this panel is" label per panel (per `feedback_audit_no_transitional_text`).

**Tech Stack:** Python 3.11+, pytest. No frontend changes needed (frontend already reads `attraction.categories` and `pass.coupon`; merging slugs only changes which `attraction_slug` value passes carry — the existing pickup-by-slug logic just works).

---

## Required reading before starting

1. Memory:
   - `feedback_audit_no_transitional_text.md` — the rule that motivates Task 2
   - `feedback_do_the_right_thing.md` — pick the cleaner canonical, don't preserve legacy for legacy's sake
   - `feedback_core_product_value.md` — duplicates hurt the comparison view; merging is the correct fix
2. Current data shape:
   - `data/structured/attractions.json` — 107 attractions; 16 of these are 8 duplicate pairs that should be 8 entities
   - `data/structured/passes.json` — 1008 rows; some reference the legacy slugs, must be re-pointed
   - `data/structured/library_catalog.json` — intermediate file that build_attractions reads from

---

## Task 1 — Merge 8 duplicate attraction-slug pairs

**Files:**
- Create: `src/malibbene/build/slug_canonical.py` — single mapping table
- Modify: `src/malibbene/build/attractions.py` — apply mapping during accumulation
- Modify: `src/malibbene/build/passes.py` — apply mapping when emitting `attraction_slug`
- Modify: `audit/duplicates.html` (auto-regen via build_audit_site.py) — should now show 0 pairs
- Test: `tests/test_slug_canonical.py` — schema-lock test

**Canonical winners (locked, do not re-litigate):**

| Legacy slug | → | Canonical slug |
|---|---|---|
| `museum-of-fine-arts` | → | `mfa` |
| `institute-of-contemporary-art-boston` | → | `ica-boston` |
| `john-f-kennedy-library-and-museum` | → | `jfk-library` |
| `the-trustees-of-the-reservations` | → | `trustees-of-reservations` |
| `trustees-of-the-reservations` | → | `trustees-of-reservations` |
| `plimoth-patuxet-museums` | → | `plimoth-patuxet` |
| `american-rep-theater` | → | `american-repertory-theater` |
| `massachusetts-state-parks-department-of-conservation-and-recreation` | → | `ma-state-parks` |
| `the-butterfly-place` | → | `butterfly-place` |

(9 mappings for 8 pairs because Trustees has 3 spellings collapsing to 1.)

- [ ] **Step 1: Write failing test**

Create `tests/test_slug_canonical.py`:

```python
"""Schema lock: each duplicate slug pair must collapse to one canonical entity."""
import json


def test_no_duplicate_attraction_entities():
    """After build, none of the 9 legacy slugs should appear in attractions.json."""
    legacy = [
        "museum-of-fine-arts",
        "institute-of-contemporary-art-boston",
        "john-f-kennedy-library-and-museum",
        "the-trustees-of-the-reservations",
        "trustees-of-the-reservations",
        "plimoth-patuxet-museums",
        "american-rep-theater",
        "massachusetts-state-parks-department-of-conservation-and-recreation",
        "the-butterfly-place",
    ]
    attrs = json.load(open("data/structured/attractions.json", encoding="utf-8"))["attractions"]
    slugs = {a["slug"] for a in attrs}
    leaked = [s for s in legacy if s in slugs]
    assert not leaked, f"Legacy slugs still present in attractions.json: {leaked}"


def test_passes_use_canonical_only():
    """No pass row should reference a legacy slug."""
    legacy = {
        "museum-of-fine-arts", "institute-of-contemporary-art-boston",
        "john-f-kennedy-library-and-museum", "the-trustees-of-the-reservations",
        "trustees-of-the-reservations", "plimoth-patuxet-museums",
        "american-rep-theater",
        "massachusetts-state-parks-department-of-conservation-and-recreation",
        "the-butterfly-place",
    }
    passes = json.load(open("data/structured/passes.json", encoding="utf-8"))["passes"]
    bad = [p for p in passes if p["attraction_slug"] in legacy]
    assert not bad, f"{len(bad)} passes still reference legacy slugs"
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
python -m pytest tests/test_slug_canonical.py -v
```

Expected: both fail because legacy slugs are still present.

- [ ] **Step 3: Create the canonical mapping module**

`src/malibbene/build/slug_canonical.py`:

```python
"""Canonical slug mapping for attraction-entity deduplication.

When multiple library platforms / scraping paths produced different slugs for
the same museum, this map collapses them at build time.
"""
from __future__ import annotations

LEGACY_TO_CANONICAL: dict[str, str] = {
    "museum-of-fine-arts":                                                  "mfa",
    "institute-of-contemporary-art-boston":                                 "ica-boston",
    "john-f-kennedy-library-and-museum":                                    "jfk-library",
    "the-trustees-of-the-reservations":                                     "trustees-of-reservations",
    "trustees-of-the-reservations":                                         "trustees-of-reservations",
    "plimoth-patuxet-museums":                                              "plimoth-patuxet",
    "american-rep-theater":                                                 "american-repertory-theater",
    "massachusetts-state-parks-department-of-conservation-and-recreation":  "ma-state-parks",
    "the-butterfly-place":                                                  "butterfly-place",
}


def canonical(slug: str) -> str:
    """Return canonical slug; passes through if not a known legacy."""
    return LEGACY_TO_CANONICAL.get(slug, slug)
```

- [ ] **Step 4: Apply mapping in build_attractions**

In `src/malibbene/build/attractions.py`, in the accumulator loop, change:

```python
for lib_id, lib_entry in catalog.get("libraries", {}).items():
    for slug, p in lib_entry.get("passes", {}).items():
        entry = accum.setdefault(slug, {...})
```

to:

```python
from malibbene.build.slug_canonical import canonical

for lib_id, lib_entry in catalog.get("libraries", {}).items():
    for raw_slug, p in lib_entry.get("passes", {}).items():
        slug = canonical(raw_slug)
        entry = accum.setdefault(slug, {
            "slug": slug,
            ...
        })
        # Track the legacy slugs that collapsed into this entity
        legacy_aliases = entry.setdefault("legacy_slugs", [])
        if raw_slug != slug and raw_slug not in legacy_aliases:
            legacy_aliases.append(raw_slug)
```

- [ ] **Step 5: Apply mapping in build_passes**

In `src/malibbene/build/passes.py`, when emitting each pass record, change:

```python
"attraction_slug": slug,
```

to:

```python
from malibbene.build.slug_canonical import canonical
# ... inside the loop ...
"attraction_slug": canonical(slug),
```

This ensures all 1008 pass rows reference the canonical attraction.

- [ ] **Step 6: Apply mapping in raw coupon lookup**

If `build_passes` looks up coupons by `f"{lib_id}_{slug}"`, the coupon files on disk are keyed by the ORIGINAL slug (e.g. `acton_museum-of-fine-arts.json`). Two options:

(a) Look up the raw slug first, fall back to canonical:

```python
coupon_key_raw = f"{lib_id}_{raw_slug}"
coupon_key_canon = f"{lib_id}_{canonical(raw_slug)}"
coupon_rec = coupons.get(coupon_key_raw) or coupons.get(coupon_key_canon)
```

(b) After Step 4 build, run a one-shot rename script over `data/raw/pass_coupons/*.json` to use canonical keys.

Choose (a) — non-destructive and survives future re-extractions. Update the lookup line in `build_passes`.

- [ ] **Step 7: Rebuild structured data**

```bash
python scripts/build.py
```

Expected output: `attractions: 99 entries` (was 107 — minus 8 dropped duplicates) or similar reduction.

- [ ] **Step 8: Re-run tests, expect PASS**

```bash
python -m pytest tests/test_slug_canonical.py -v
python -m pytest tests/ -q
```

Expected: all green. Pre-existing tests for attraction count may need adjustment if any hard-coded 107 — update to the new count.

- [ ] **Step 9: Regenerate audit pages**

```bash
python scripts/build_audit_site.py
```

Open `audit/duplicates.html` — should now show "0 duplicate pairs" or auto-skip the panel entirely.

- [ ] **Step 10: Commit**

```bash
git add src/malibbene/build/slug_canonical.py src/malibbene/build/attractions.py src/malibbene/build/passes.py tests/test_slug_canonical.py data/structured/ audit/
git commit -m "plan-10: collapse 8 duplicate attraction-slug pairs to canonical entities"
```

---

## Task 2 — Strip 22 transitional-explanation blocks from audit pages

**Files:**
- Modify: `scripts/build_audit_site.py` — delete or compress all `<p class="methodology">` blocks
- Regenerate: `audit/index.html`, `audit/libraries.html`, `audit/attractions.html`, `audit/policies.html`

**Current state** (verify with grep at start):
- index.html: 5 methodology blocks
- policies.html: 5 blocks
- attractions.html: 5 blocks
- libraries.html: 7 blocks
- Total: 22

**Rule** (from `feedback_audit_no_transitional_text`):
- KEEP: minimal "what this panel is" label (1 line, no "why/口径/methodology" wording)
- DELETE: any text explaining "为什么不到 100%", "口径", "归一化", "plan-X 工作项", "对用户决策最重要", etc.
- KEEP: the red lib_id callout on libraries.html — that's the audit's required context for the page

- [ ] **Step 1: Inventory all methodology blocks**

```bash
grep -n 'class="methodology"' scripts/build_audit_site.py | head -30
```

Note line numbers; there should be ~22 emission points in the generator.

- [ ] **Step 2: For each block, decide DELETE or COMPRESS**

Rule of thumb:
- Block is multi-line and explains "why the data looks this way" → **DELETE entirely**
- Block is 1-line "this panel = X" / "口径: …" → **DELETE** (data + label is enough)
- The single red `lib_id` callout panel on libraries.html → **KEEP** (architectural context the auditor needs)

Edit `scripts/build_audit_site.py` to remove the targeted f-string blocks. Each removal is typically:

```python
# Before:
<section class="panel">
  <h3>X</h3>
  <p class="methodology">...lots of explanation...</p>
  {histogram_table(...)}
</section>

# After:
<section class="panel">
  <h3>X</h3>
  {histogram_table(...)}
</section>
```

Also remove the `histogram_with_notag` "口径" computation values that were only used by methodology text (e.g. `n_with_any_elig`, `sum(tag_counter.values())` shown in methodology). Keep them only if the histogram itself needs them.

- [ ] **Step 3: Strip the `feedback_audit_panel_rule` style "对产品决策意义" footer paragraphs**

Some panels still carry `<p class="methodology" style="margin-top:8px">…</p>` after the histogram — those are also forbidden. Delete each.

- [ ] **Step 4: Regenerate**

```bash
python scripts/build_audit_site.py
```

- [ ] **Step 5: Verify count drops to 0 (or near-0 with only the red lib_id callout)**

```bash
python -c "
for page in ['audit/index.html','audit/policies.html','audit/attractions.html','audit/libraries.html']:
    h = open(page, encoding='utf-8').read()
    n = h.count('class=\"methodology\"')
    print(f'{page}: {n}')
"
```

Expected: 0 across all pages (the lib_id red callout uses a different class, so the methodology counter should hit zero).

- [ ] **Step 6: Open each page in a browser and visually confirm**

Open `audit/index.html`, `audit/policies.html`, `audit/attractions.html`, `audit/libraries.html`.
- Each panel has a `<h3>` title + the data table/histogram, period
- No paragraph blocks of explanatory text
- Page reads like a dashboard, not a doc

- [ ] **Step 7: Commit**

```bash
git add scripts/build_audit_site.py audit/
git commit -m "plan-10: strip 22 methodology transitional blocks per feedback_audit_no_transitional_text"
```

---

## Final Verification

- [ ] **All gaps closed**

```bash
python -c "
import json

# 1. No duplicate slugs
attrs = json.load(open('data/structured/attractions.json', encoding='utf-8'))['attractions']
slugs = {a['slug'] for a in attrs}
legacy = {'museum-of-fine-arts','institute-of-contemporary-art-boston',
          'john-f-kennedy-library-and-museum','the-trustees-of-the-reservations',
          'trustees-of-the-reservations','plimoth-patuxet-museums',
          'american-rep-theater',
          'massachusetts-state-parks-department-of-conservation-and-recreation',
          'the-butterfly-place'}
assert not (slugs & legacy), f'legacy slugs remain: {slugs & legacy}'
print(f'#1 dup slugs: 0 / 9 legacy in data')

# 2. No methodology blocks
n = 0
for page in ['audit/index.html','audit/policies.html','audit/attractions.html','audit/libraries.html']:
    n += open(page, encoding='utf-8').read().count('class=\"methodology\"')
assert n == 0, f'{n} methodology blocks remain'
print(f'#2 methodology blocks: {n}')

# 3. passes.json still 1008 with all slugs canonical
passes = json.load(open('data/structured/passes.json', encoding='utf-8'))['passes']
print(f'#3 passes: {len(passes)} (expected 1008)')
bad = [p for p in passes if p['attraction_slug'] in legacy]
assert not bad
print('   all passes use canonical slugs.')

print()
print(f'attractions: {len(attrs)} (was 107, expected ~99 after merge)')
"
```

Expected:
- `#1 dup slugs: 0 / 9` ✅
- `#2 methodology blocks: 0` ✅
- `#3 passes: 1008` ✅
- `attractions: ~99 (was 107)`

- [ ] **Full test suite green**

```bash
python -m pytest tests/ -q
cd web && pnpm test -- --run
```

Both green.

- [ ] **Frontend smoke test**

```bash
cd web && pnpm run dev
```

Open MFA detail page → should now show ALL passes from BOTH old slugs (acton's `museum-of-fine-arts` and wakefield's `mfa` etc.) merged into one comparison list — that's the user-visible benefit of dedup.
