# Plan 8 — Audit Follow-ups: pass_type / hours / seasonal / price schema

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the 5 data-quality items the audit reviewer surfaced after plan-7 — frontend/data pass_type enum mismatch, 23 unknown pass_type, cohasset hours bug, malformed seasonal exclusions, and the price-schema two-layer split (age vs identity).

**Architecture:** Tasks 1–4 are surgical fixes (single file edits or one if-else). Task 5 is a real schema migration: extend `OriginalPrice` with `age_pricing` + `identity_pricing` sub-objects, keep flat 8 fields for backward compatibility one release, then drop them. Each task has its own commit. No new external dependencies.

**Tech Stack:** Python 3.11+ stdlib, TypeScript 5.x, pytest, vitest. Edits land in `src/malibbene/build/`, `web/src/data/types.ts`, `data/raw/`, `tests/`, `docs/`.

**Self-contained context (read before starting):**
- Live audit page `audit/index.html` red-callout in Pickup-method panel documents the type-system bug being fixed in Task 1.
- Build pipeline orchestration is in `scripts/build.py`. Pass type and pickup are merged in `src/malibbene/build/passes.py` at the `_resolve_pickup` helper.
- Raw pass policies live at `data/raw/pass_policies/<lib_id>_<slug>.json` (1008 files). Schema in `src/malibbene/build/passes.py::_policy_block`.
- Pricing is currently 8 flat fields on `OriginalPrice` (frontend `web/src/data/types.ts`, build/attractions.py).
- Memory files relevant to this plan (read first):
  - `feedback_product_scope.md` — query-only product, assume MA cardholder
  - `feedback_audit_panel_rule.md` — every data field must serve data-correctness or user-decision
  - `feedback_no_api_call.md` — LLM extraction goes via subagent dispatch, never Anthropic API
  - `feedback_subagent_models.md` — Opus for design/review, Sonnet for extraction

---

## Task 1: Unify PassTypeKind enum to match data — fix 172 silent fallbacks

**Files:**
- Modify: `web/src/data/types.ts` (the `PassTypeKind` union, ~line 114)
- Modify: `web/src/components/PassTypeLabel.tsx` (the META map)
- Test: `web/src/components/PassTypeLabel.test.tsx` (new)

**Why:** Data layer writes `pass_type: "physical-circ"` (272 rows). Frontend enum is `"loan-card"`. The two never match, so all 172 must-return passes hit the unknown fallback and lose the "must return" UX signal.

- [ ] **Step 1: Read current state**

```bash
grep -n "PassTypeKind\|loan-card\|physical-circ" web/src/data/types.ts web/src/components/PassTypeLabel.tsx
```

Expected: types.ts has `'loan-card'` in the union. PassTypeLabel.tsx has `'loan-card'` key in `META`.

- [ ] **Step 2: Write failing test for physical-circ rendering**

Create `web/src/components/PassTypeLabel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PassTypeLabel } from './PassTypeLabel';

describe('PassTypeLabel', () => {
  it('renders Pickup & Return for physical-circ (the value the data layer actually emits)', () => {
    render(<PassTypeLabel type="physical-circ" />);
    expect(screen.getByText('Pickup & Return')).toBeInTheDocument();
  });

  it('renders E-pass for digital', () => {
    render(<PassTypeLabel type="digital" />);
    expect(screen.getByText('E-pass')).toBeInTheDocument();
  });

  it('renders Pickup for physical-coupon', () => {
    render(<PassTypeLabel type="physical-coupon" />);
    expect(screen.getByText('Pickup')).toBeInTheDocument();
  });

  it('renders Pass for unknown', () => {
    render(<PassTypeLabel type="unknown" />);
    expect(screen.getByText('Pass')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to confirm FAIL on physical-circ**

```bash
cd web && pnpm test -- --run PassTypeLabel.test
```

Expected: first test fails (physical-circ falls through to META.unknown → "Pass").

- [ ] **Step 4: Update type definition**

In `web/src/data/types.ts`, replace the `PassTypeKind` line:

```typescript
export type PassTypeKind = 'digital' | 'physical-coupon' | 'physical-circ' | 'unknown';
```

- [ ] **Step 5: Update PassTypeLabel META map**

In `web/src/components/PassTypeLabel.tsx`, replace the `'loan-card'` entry with `'physical-circ'`:

```tsx
const META: Record<PassTypeKind, { label: string; fg: string; bg: string }> = {
  'digital':         { label: 'E-pass',           fg: 'var(--g)',  bg: 'var(--g-pale)'  },
  'physical-coupon': { label: 'Pickup',           fg: 'var(--au)', bg: 'var(--au-pale)' },
  'physical-circ':   { label: 'Pickup & Return',  fg: 'var(--or)', bg: 'var(--or-pale)' },
  'unknown':         { label: 'Pass',             fg: 'var(--ink-3)', bg: 'var(--paper)' },
};
```

- [ ] **Step 6: Re-run tests, expect PASS**

```bash
cd web && pnpm test -- --run
```

Expected: all 119+ tests pass (115 prior + 4 new).

- [ ] **Step 7: Spot-check rendered audit page is unaffected**

```bash
cd .. && python scripts/build_audit_site.py
```

Audit page already shows `physical-circ` directly via histogram_table, so no change. Just confirm the script runs.

- [ ] **Step 8: Commit**

```bash
git add web/src/data/types.ts web/src/components/PassTypeLabel.tsx web/src/components/PassTypeLabel.test.tsx
git commit -m "fix(web): align PassTypeKind enum with data layer (physical-circ not loan-card)"
```

---

## Task 2: Backfill pass_type for 23 unknown LibCal/MuseumKey passes

**Files:**
- Modify: `src/malibbene/build/passes.py` (the `_resolve_pickup` function + a new `_resolve_pass_type` helper)
- Test: `tests/test_build_passes.py` (add test for backfill)

**Why:** 23 passes from cohasset/cambridge/brookline/hingham (LibCal + MuseumKey platforms) have `pass_type_raw: ""` so `pass_type` stays `"unknown"`. But their `pickup_method` IS classified by the plan-6 subagent. We can derive pass_type from pickup_method + raw text mention of "return".

- [ ] **Step 1: Inspect current code**

```bash
grep -n "pass_type\|pickup_method" src/malibbene/build/passes.py | head -20
```

Note the flow: `_resolve_pickup` returns `(pickup_method, branches)`; `pass_type` is read from `p.get("pass_type")` and not re-derived.

- [ ] **Step 2: Write failing test**

In `tests/test_build_passes.py`, add:

```python
def test_unknown_pass_type_backfills_from_pickup_method_and_raw():
    """When pass_type is unknown but pickup_method is classified, derive pass_type."""
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {
        "cambridge": {"passes": {
            "x-digital": {"pass_type": "unknown", "pass_type_raw": "",
                           "benefit_label": "Free", "benefit_class": "free",
                           "benefits_text": "Pass admits 4 people for free.",
                           "source_url": "", "pass_type_raw": ""},
            "y-pickup": {"pass_type": "unknown", "pass_type_raw": "",
                          "benefit_label": "Free", "benefit_class": "free",
                          "benefits_text": "Pick up your pass at the Main Library.",
                          "source_url": "", "pass_type_raw": ""},
            "z-return": {"pass_type": "unknown", "pass_type_raw": "",
                          "benefit_label": "Free", "benefit_class": "free",
                          "benefits_text": "Pick up at the library and return next day.",
                          "source_url": "", "pass_type_raw": ""},
        }}
    }}
    classifications = {"cambridge": {
        "x-digital": {"pass_id": "x-digital", "pickup_method": "digital", "pickup_branches": []},
        "y-pickup":  {"pass_id": "y-pickup",  "pickup_method": "physical_at_branch", "pickup_branches": ["cambridge--main"]},
        "z-return":  {"pass_id": "z-return",  "pickup_method": "physical_at_branch", "pickup_branches": ["cambridge--main"]},
    }}
    out = build_passes(catalog, classifications=classifications,
                       branches_doc={"branches": [{"id": "cambridge--main", "library_id": "cambridge"}]})
    by_slug = {p["attraction_slug"]: p for p in out["passes"]}
    assert by_slug["x-digital"]["pass_type"] == "digital"
    assert by_slug["y-pickup"]["pass_type"] == "physical-coupon"   # no "return" in raw → coupon
    assert by_slug["z-return"]["pass_type"] == "physical-circ"     # "return" in raw → circ
```

- [ ] **Step 3: Run test to confirm FAIL**

```bash
python -m pytest tests/test_build_passes.py::test_unknown_pass_type_backfills_from_pickup_method_and_raw -v
```

Expected: FAIL — pass_type stays "unknown".

- [ ] **Step 4: Add backfill helper to passes.py**

In `src/malibbene/build/passes.py`, right after `_resolve_pickup`, add:

```python
def _resolve_pass_type(
    *,
    original_pass_type: str,
    pickup_method: str,
    benefits_text: str,
) -> str:
    """Derive pass_type when the catalog left it 'unknown'.

    LibCal + MuseumKey platforms don't expose a pass_type label, so plan-6's
    pass_type stays 'unknown' for ~23 cases. But plan-6's subagent classified
    pickup_method correctly, and raw text usually says 'return' for circ passes.
    Combine the two signals to recover a useful pass_type.
    """
    if original_pass_type and original_pass_type != "unknown":
        return original_pass_type
    if pickup_method == "digital":
        return "digital"
    if pickup_method == "physical_at_branch":
        text = (benefits_text or "").lower()
        if "return" in text or "returning" in text:
            return "physical-circ"
        return "physical-coupon"
    return original_pass_type or "unknown"
```

- [ ] **Step 5: Wire backfill into build loop**

Find the existing loop in `build_passes` that constructs each pass record. After computing `pickup_method`, add a `pass_type` recompute:

```python
# inside build_passes(), per-pass loop, after _resolve_pickup() returns pickup_method/branches:
pass_type = _resolve_pass_type(
    original_pass_type=raw_pass.get("pass_type", "unknown"),
    pickup_method=pickup_method,
    benefits_text=raw_pass.get("benefits_text", ""),
)
# then use this pass_type in the pass dict instead of raw_pass.get("pass_type")
```

(The exact insertion point depends on current shape — read the function once and pick the spot where pass_type is currently set.)

- [ ] **Step 6: Run the new test, expect PASS**

```bash
python -m pytest tests/test_build_passes.py::test_unknown_pass_type_backfills_from_pickup_method_and_raw -v
```

- [ ] **Step 7: Run full backend test suite, expect no regressions**

```bash
python -m pytest tests/ -q
```

Expected: 120+ pass (was 120 before this task).

- [ ] **Step 8: Rebuild structured data and verify unknown count dropped**

```bash
python scripts/build.py
python -c "import json; from collections import Counter; passes=json.load(open('data/structured/passes.json',encoding='utf-8'))['passes']; print(Counter(p['pass_type'] for p in passes))"
```

Expected: `unknown` count is 0 or near-0 (was 23). Some may legitimately remain if pickup_method itself was unknown.

- [ ] **Step 9: Commit**

```bash
git add src/malibbene/build/passes.py tests/test_build_passes.py data/structured/passes.json data/structured/library_catalog.json
git commit -m "fix(build): backfill unknown pass_type from pickup_method + raw 'return' keyword"
```

---

## Task 3: Fix cohasset hours raw data (status=ok → seasonal)

**Files:**
- Modify: `data/raw/attraction_hours/cohasset-historical-society.json`
- Verify: `data/structured/attractions.json` after rebuild

**Why:** Raw file has `status: "ok"` but all 7 days are `"Closed"` and notes literally say "Seasonal summer hours only, July–August". The audit page already detects this at display time, but the raw data should agree.

- [ ] **Step 1: Edit the raw file**

Open `data/raw/attraction_hours/cohasset-historical-society.json` and:
1. Change `"status": "ok"` to `"status": "seasonal"`
2. Change `regular_hours` from the all-Closed object to `null`

Resulting file:

```json
{
  "slug": "cohasset-historical-society",
  "status": "seasonal",
  "regular_hours": null,
  "notes": "Seasonal summer hours only. Maritime Museum and other properties open in summer (typically July–August); check cohassethistoricalsociety.org for current season schedule. Closed in winter.",
  "source": "official_site",
  "source_url": "https://www.cohassethistoricalsociety.org/maritime-museum"
}
```

- [ ] **Step 2: Rebuild and verify**

```bash
python scripts/build.py
python -c "import json; a=[x for x in json.load(open('data/structured/attractions.json',encoding='utf-8'))['attractions'] if x['slug']=='cohasset-historical-society'][0]; print('status:', a['hours']['status']); print('regular_hours:', a['hours']['regular_hours'])"
```

Expected: `status: seasonal`, `regular_hours: None`.

- [ ] **Step 3: Re-run backend tests, expect no regressions**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add data/raw/attraction_hours/cohasset-historical-society.json data/structured/attractions.json
git commit -m "fix(data): cohasset hours status was 'ok' with 7 closed days — really seasonal"
```

---

## Task 4: Clean up 6 malformed seasonal:* exclusion tags

**Files:**
- Modify: 6 specific files under `data/raw/pass_policies/` (identify in Step 1)
- Test: `tests/test_seasonal_tags.py` (new)

**Why:** Plan-5's subagents produced `seasonal:october-october`, `seasonal:1st-October`, `seasonal:apr-oct`, `seasonal:may-sep`, `seasonal:may-oct`, `seasonal:mar-dec`. The first two are garbage; the last four are valid `mmm-mmm` range tags but inconsistent vs the rest of the schema (which expects `seasonal:May-Oct` style). Normalize.

**Decision (from audit conversation):**
- `seasonal:october-october` → DROP from exclusions (not a range, no info), leave the policy raw text alone
- `seasonal:1st-October` → DROP from exclusions (typo of a date, not a season window)
- `seasonal:apr-oct` / `seasonal:may-sep` / `seasonal:may-oct` / `seasonal:mar-dec` → normalize to title case: `seasonal:Apr-Oct`, `seasonal:May-Sep`, etc.

- [ ] **Step 1: Identify the 6 affected files**

```bash
python -c "
import json, glob
for f in glob.glob('data/raw/pass_policies/*.json'):
    d = json.load(open(f, encoding='utf-8'))
    for t in d.get('exclusions') or []:
        if isinstance(t, str) and t.startswith('seasonal:'):
            tail = t.split(':',1)[1]
            if tail in ('october-october','1st-October','apr-oct','may-sep','may-oct','mar-dec'):
                print(f, '→', t)
"
```

Record the 6 file paths and current tag values.

- [ ] **Step 2: Write a test that enforces the schema rule**

Create `tests/test_seasonal_tags.py`:

```python
"""Schema-lock test: seasonal:* exclusion tags must be 'seasonal:Mon-Mon' format."""
import glob
import json
import re

import pytest

MONTH_TOKEN = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
SEASONAL_RE = re.compile(rf'^seasonal:{MONTH_TOKEN}-{MONTH_TOKEN}$')


def test_all_seasonal_tags_match_month_range_format():
    bad = []
    for f in glob.glob('data/raw/pass_policies/*.json'):
        with open(f, encoding='utf-8') as fh:
            d = json.load(fh)
        for t in d.get('exclusions') or []:
            if isinstance(t, str) and t.startswith('seasonal:'):
                if not SEASONAL_RE.match(t):
                    bad.append((f, t))
    if bad:
        msg = '\n'.join(f'  {f}: {t}' for f, t in bad)
        pytest.fail(f'{len(bad)} seasonal tags violate Mon-Mon format:\n{msg}')
```

- [ ] **Step 3: Run test, expect 6 failures listed**

```bash
python -m pytest tests/test_seasonal_tags.py -v
```

- [ ] **Step 4: For each of the 6 files, edit the `exclusions` list**

For each file from Step 1:
- If tag was `seasonal:october-october` or `seasonal:1st-October`: remove that string from the `exclusions` list (leave other entries alone)
- If tag was `seasonal:<lowercase-month>-<lowercase-month>`: rewrite to title case, e.g. `seasonal:apr-oct` → `seasonal:Apr-Oct`

Use `Edit` tool surgically on each file's `exclusions` array.

- [ ] **Step 5: Re-run test, expect PASS**

```bash
python -m pytest tests/test_seasonal_tags.py -v
```

- [ ] **Step 6: Rebuild structured data**

```bash
python scripts/build.py
```

- [ ] **Step 7: Sanity check the audit page**

```bash
python scripts/build_audit_site.py
python -c "import re; h=open('audit/attractions.html',encoding='utf-8').read(); print([t for t in re.findall(r'Open ([^<]+?)<', h) if t])"
```

Expected: only legit month-range names appear (`Open Apr-Oct`, `Open May-Sep`, etc.); no `october-october` / `1st-October`.

- [ ] **Step 8: Run full test suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 9: Commit**

```bash
git add data/raw/pass_policies/ tests/test_seasonal_tags.py data/structured/
git commit -m "fix(data): normalize 6 malformed seasonal:* exclusion tags + add schema-lock test"
```

---

## Task 5: Split OriginalPrice into age_pricing + identity_pricing

**Files:**
- Modify: `src/malibbene/build/attractions.py` (the `_price_block` helper)
- Modify: `data/raw/attraction_prices/<slug>.json` (no edits — the new schema is derived)
- Modify: `web/src/data/types.ts` (`OriginalPrice` interface)
- Modify: `web/src/lib/discount-display.ts` (the `adultPrice` lookup)
- Modify: `web/src/components/AttractionCard.tsx` + any other consumers
- Test: `tests/test_build_attractions.py` (extend), `web/src/lib/discount-display.test.ts` (extend)

**Why:** Current schema is 8 flat fields (`adult/child/youth/senior/student/military/educator/family`). They conceptually live in two layers:
- **Age pricing** — applies to everyone of that age (adult/child/youth/senior + free_under_age)
- **Identity pricing** — applies only to people who can prove status (student/military/educator)

Audit reviewer pointed out: the 8 flat fields hide this distinction, and the front-end filter / price-estimate logic should be aware of which is which.

**Design (no further user input required — extracted from audit transcript):**

New `OriginalPrice` shape:

```typescript
export interface AgeTier {
  price: number;
  min_age?: number;   // e.g. Senior 65+
  max_age?: number;   // e.g. Child <=12, Youth 11-17
}

export interface IdentityTier {
  price: number;
  requires?: string;   // free-text human description, e.g. "active military ID"
}

export interface OriginalPrice {
  age_pricing: {
    adult:  AgeTier | null;
    youth:  AgeTier | null;
    child:  AgeTier | null;
    senior: AgeTier | null;
    free_under_age: number | null;   // age threshold, NOT a price
  };
  identity_pricing: {
    student:  IdentityTier | null;
    educator: IdentityTier | null;
    military: IdentityTier | null;
  };
  family:    number | null;     // family-package price, neither age nor identity
  notes:     string | null;
  source_url: string | null;
}
```

**Backwards-compatibility decision:** Drop the flat 8 fields outright — there are only 2 consumers (audit script + 1 frontend component), both updated in this task. No production telemetry depends on the old shape.

**Migration strategy:** the new `age_pricing.*.price` value comes from the existing flat field. Age range (`min_age`/`max_age`) can be parsed out of `notes` in a follow-up if needed, but for now ship without ranges (set them to null).

- [ ] **Step 1: Write failing test for the new shape**

In `tests/test_build_attractions.py`, replace any flat-price assertions on the `mos` fixture with the new shape:

```python
def test_build_attractions_uses_two_layer_price_schema():
    """Prices are split into age_pricing (age-based) and identity_pricing (status-based)."""
    from malibbene.build.attractions import build_attractions
    catalog = {"libraries": {"wakefield": {"passes": {"mos": {
        "museum_name": "Museum of Science", "address": "1 Science Park, Boston, MA",
        "website": "https://www.mos.org", "categories": ["Science", "Family"],
    }}}}}
    prices = {"mos": {"status": "ok", "adult": 33, "child": 28, "youth": 25,
                       "senior": 30, "student": 27, "military": 0, "educator": 0,
                       "family": None, "free_under_age": 3, "notes": None,
                       "source_url": "https://www.mos.org/admission"}}
    out = build_attractions(catalog, prices, {}, {"attractions": {}}, hours={}, descriptions={})
    p = out["attractions"][0]["original_price"]
    assert p["age_pricing"]["adult"]["price"] == 33
    assert p["age_pricing"]["child"]["price"] == 28
    assert p["age_pricing"]["senior"]["price"] == 30
    assert p["age_pricing"]["free_under_age"] == 3
    assert p["identity_pricing"]["student"]["price"] == 27
    assert p["identity_pricing"]["military"]["price"] == 0
    assert p["identity_pricing"]["educator"]["price"] == 0
    # flat fields removed:
    assert "adult" not in p
    assert "student" not in p
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
python -m pytest tests/test_build_attractions.py::test_build_attractions_uses_two_layer_price_schema -v
```

- [ ] **Step 3: Update `_price_block` in `src/malibbene/build/attractions.py`**

Replace the body of `_price_block`:

```python
def _price_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None

    def _age_tier(value):
        return {"price": value, "min_age": None, "max_age": None} if value is not None else None

    def _identity_tier(value):
        return {"price": value, "requires": None} if value is not None else None

    return {
        "age_pricing": {
            "adult":  _age_tier(rec.get("adult")),
            "youth":  _age_tier(rec.get("youth")),
            "child":  _age_tier(rec.get("child")),
            "senior": _age_tier(rec.get("senior")),
            "free_under_age": rec.get("free_under_age"),
        },
        "identity_pricing": {
            "student":  _identity_tier(rec.get("student")),
            "educator": _identity_tier(rec.get("educator")),
            "military": _identity_tier(rec.get("military")),
        },
        "family": rec.get("family"),
        "notes": rec.get("notes"),
        "source_url": rec.get("source_url"),
    }
```

- [ ] **Step 4: Run python test, expect PASS**

```bash
python -m pytest tests/test_build_attractions.py -v
```

- [ ] **Step 5: Update existing test fixtures**

The previous fixture used flat fields. Search for any other `original_price["adult"]` / `original_price["child"]` references in tests and convert them to the new shape.

```bash
grep -n "original_price\[" tests/
```

For each match: change `original_price["adult"]` → `original_price["age_pricing"]["adult"]["price"]`, etc.

- [ ] **Step 6: Rebuild structured data**

```bash
python scripts/build.py
python -c "import json; a=json.load(open('data/structured/attractions.json',encoding='utf-8'))['attractions']; m=next(x for x in a if x['slug']=='museum-of-fine-arts'); print(json.dumps(m['original_price'], indent=2, ensure_ascii=False))"
```

Expected: shows nested age_pricing / identity_pricing structure.

- [ ] **Step 7: Update frontend types**

In `web/src/data/types.ts`, replace the `OriginalPrice` interface (currently 8 flat optional-number fields) with the new shape from the design block above. Also keep the field-comment lines bilingual.

- [ ] **Step 8: Update frontend consumers**

Search for all reads of the flat fields:

```bash
grep -rn "original_price\.\(adult\|child\|youth\|senior\|student\|military\|educator\|family\)" web/src/
```

For each match: change `original_price.adult` → `original_price.age_pricing.adult?.price ?? null`, etc.

Likely consumers:
- `web/src/components/AttractionCard.tsx` — display in the card
- `web/src/lib/discount-display.ts` — the `adultPrice` parameter to `formatDiscount` (use `age_pricing.adult?.price ?? null`)
- `web/src/pages/AttractionDetail.tsx` — detail page rendering

Apply the same shape change wherever found.

- [ ] **Step 9: Update audit page to render two-layer prices**

In `scripts/build_audit_site.py`, the per-attraction price card section currently iterates a flat 8-list. Update to:

```python
age_tiers = [("adult","Adult · 成人"),("youth","Youth · 年轻人"),
             ("child","Child · 儿童"),("senior","Senior · 老人")]
identity_tiers = [("student","Student · 学生"),("educator","Educator · 教师"),
                  ("military","Military · 军人")]

ap = price.get("age_pricing") or {}
ip = price.get("identity_pricing") or {}

# render age block then identity block separately
age_rows = []
for k, label in age_tiers:
    v = (ap.get(k) or {}).get("price") if ap.get(k) else None
    age_rows.append(... )  # same kv pattern as today
# free_under_age separate row from ap["free_under_age"]

id_rows = []
for k, label in identity_tiers:
    v = (ip.get(k) or {}).get("price") if ip.get(k) else None
    id_rows.append(... )
```

Render in two visually separated sub-sections: `年龄定价 · Age-based pricing` and `身份定价 · Identity-based pricing`.

- [ ] **Step 10: Run all tests**

```bash
python -m pytest tests/ -q
cd web && pnpm test -- --run
```

Expected: both green.

- [ ] **Step 11: Rebuild audit page and visually inspect one attraction card**

```bash
cd .. && python scripts/build_audit_site.py
```

Open `audit/attractions.html` in browser, scroll to "museum-of-fine-arts" or "royall-house" — confirm Prices block now shows two labeled sub-sections.

- [ ] **Step 12: Frontend prod build sanity check**

```bash
cd web && pnpm run build
```

Expected: build succeeds. (TypeScript catches any missed consumer.)

- [ ] **Step 13: Commit**

```bash
cd .. && git add src/malibbene/build/attractions.py web/src/data/types.ts web/src/lib/discount-display.ts web/src/components/ web/src/pages/AttractionDetail.tsx scripts/build_audit_site.py tests/test_build_attractions.py audit/ data/structured/attractions.json
git commit -m "feat(schema): split OriginalPrice into age_pricing + identity_pricing layers"
```

---

## Final Verification

- [ ] **All tests pass**

```bash
python -m pytest tests/ -q
cd web && pnpm test -- --run
cd .. && python scripts/build_audit_site.py
```

- [ ] **All 5 audit findings closed**

```bash
python -c "
import json
from collections import Counter

# 1. PassTypeKind
ts = open('web/src/data/types.ts', encoding='utf-8').read()
assert 'physical-circ' in ts and 'loan-card' not in ts, '#1 not fixed'
print('#1 PassTypeKind: OK')

# 2. unknown pass_type
passes = json.load(open('data/structured/passes.json', encoding='utf-8'))['passes']
n_unk = sum(1 for p in passes if p['pass_type'] == 'unknown')
print(f'#2 unknown pass_type: {n_unk} (was 23)')

# 3. cohasset hours
h = json.load(open('data/raw/attraction_hours/cohasset-historical-society.json', encoding='utf-8'))
assert h['status'] == 'seasonal', '#3 not fixed'
print('#3 cohasset hours: OK (seasonal)')

# 4. seasonal:* tags
import glob, re
SEASONAL_RE = re.compile(r'^seasonal:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$')
bad = []
for f in glob.glob('data/raw/pass_policies/*.json'):
    d = json.load(open(f, encoding='utf-8'))
    for t in d.get('exclusions') or []:
        if isinstance(t, str) and t.startswith('seasonal:') and not SEASONAL_RE.match(t):
            bad.append(t)
assert not bad, f'#4 not fixed: {bad}'
print('#4 seasonal:* tags: OK')

# 5. Price schema
attrs = json.load(open('data/structured/attractions.json', encoding='utf-8'))['attractions']
sample = next(a for a in attrs if a.get('original_price'))
keys = list(sample['original_price'].keys())
assert 'age_pricing' in keys and 'identity_pricing' in keys, '#5 not fixed'
assert 'adult' not in keys, '#5 flat fields not removed'
print('#5 OriginalPrice 2-layer: OK')

print()
print('All 5 audit findings closed.')
"
```

Expected: all 5 lines OK.

- [ ] **CLAUDE.md / docs update**

Note in `CLAUDE.md` under "Key Technical Decisions" that:
- pass_type values are now `digital | physical-coupon | physical-circ | unknown` (was `loan-card` in old enum)
- `OriginalPrice` is two-layer (`age_pricing` + `identity_pricing`)

Commit if any docs touched:

```bash
git add CLAUDE.md docs/
git commit -m "docs: reflect plan-8 schema changes (pass_type / OriginalPrice)"
```
