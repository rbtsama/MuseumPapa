# Plan 9 — Coupon Model: Capacity + Audience-Policies, Subagent-Reextracted

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the current twin-field `pass.discount` + `pass.policy` model with a single `pass.coupon` model that mirrors the actual user-decision shape (capacity + audience-policy list + mobile-friendly e-commerce summary). Re-extract all 1008 passes from raw benefits_text via Sonnet subagents to populate the new structure cleanly — no regex shortcuts.

**Architecture:** New build-time pipeline component (`build/coupons.py`) reads per-pass raw extraction files written by 5 parallel Sonnet subagents. Summary string generation (`build/coupon_summary.py`) produces mobile e-commerce style labels ("50% off", "FREE", "$9/person"). Frontend types fully replaced — no transition fields. Audit page reworked to surface the per-attraction comparison view (which is the core product value).

**Tech Stack:** Python 3.11+ (build), TypeScript 5 + React 19 (frontend), pytest, vitest. Subagent dispatch via Sonnet model (no Anthropic API per `feedback_no_api_call`).

---

## Required reading (load context before starting)

1. **Memory files** — all 4 are load-bearing:
   - `feedback_core_product_value.md` — comparison view, no auto-calc, let user mentally compute
   - `feedback_do_the_right_thing.md` — correctness > simple/cheap; recommend the right path
   - `feedback_audit_panel_rule.md` — each audit panel must serve data correctness or user decision
   - `feedback_product_scope.md` — query-only product; assume user has cards
   - `feedback_no_api_call.md` — LLM extraction via subagent dispatch, no API
   - `feedback_subagent_models.md` — Opus for design/review, Sonnet for extraction

2. **Live current state**:
   - `src/malibbene/build/passes.py` — has `_policy_block` and `_resolve_pickup`/`_resolve_pass_type`; reads `data/raw/pass_policies/*.json` for policies and (per plan-6) subagent classification files for pickup
   - `web/src/data/types.ts` — current `Pass` has `pass_type`, `pass_type_raw`, `pickup_method`, `pickup_branches`, `discount`, `policy`, `source_url`, `availability`
   - `data/structured/passes.json` — 1008 passes, current shape

3. **What gets removed** (in this plan):
   - `Pass.discount` (typed as `Discount {class, label, raw}`)
   - `Pass.policy` (typed as `Policy {...11 fields}`)
   - Backend reads from `data/raw/pass_policies/` are now legacy
   - `EligibilityTag` / `ExclusionTag` / `BoostTag` / `Policy` / `DiscountClass` / `Discount` types
   - Audit panels: Eligibility tags histogram, Restrictions histogram, 16-Pattern panel
4. **What gets added**:
   - `Pass.coupon` (new shape, defined in Task 1)
   - `data/raw/pass_coupons/<lib_id>_<slug>.json` — 1008 files, subagent-extracted
   - `src/malibbene/build/coupons.py` and `src/malibbene/build/coupon_summary.py`
   - Audit "per-attraction coupon comparison" panel

---

## Locked design (decisions made during audit; do not re-litigate)

### Coupon schema (single source of truth for both data layer and types)

```typescript
// web/src/data/types.ts (Task 5 writes this)

export type CouponCapacityKind = 'people' | 'vehicle' | 'ticket' | 'unspecified';

export interface CouponCapacity {
  kind: CouponCapacityKind;
  n: number | null;   // explicit when kind='people', null otherwise
}

export type CouponAudience =
  | 'Everyone'        // covers party-wide cases (~85%)
  | 'Adult'           // default ages 18-64
  | 'Child'           // must carry age_range
  | 'Youth'           // 11-17 range, must carry age_range
  | 'Senior'          // 65+ typical, age_range optional
  | 'Vehicle'         // for capacity.kind='vehicle'
  | 'Single ticket';  // for capacity.kind='ticket'

export interface AgeRange {
  min: number | null;   // inclusive; null = open-bottom
  max: number | null;   // inclusive; null = open-top
}

export type CouponForm =
  | 'free'
  | 'percent-off'
  | 'dollar-off'
  | 'per-person-price'
  | 'discount';   // generic when raw says only "discounted" without specifics

export interface AudiencePolicy {
  audience: CouponAudience;
  age_range: AgeRange | null;     // required when audience=Child/Youth and raw text contains a boundary
  count: number | null;           // sub-cap within capacity.n, e.g. "2 adults + 2 kids"
  form: CouponForm;
  value: number | null;           // 50 for percent-off, 5 for dollar-off, 9 for per-person-price, null for free/discount
}

export interface Coupon {
  capacity: CouponCapacity;
  audience_policies: AudiencePolicy[];  // length >= 1
  summary: string;                       // backend-generated, mobile e-commerce style
}

export interface Pass {
  library_id: string;
  attraction_slug: string;
  pass_type: PassTypeKind;
  pass_type_raw: string;
  pickup_method: PickupMethod;
  pickup_branches: string[];
  coupon: Coupon;                    // NEW — replaces discount + policy
  source_url: string;
  availability: Record<string, string> | null;
  // restrictions kept as a separate side-channel (date/process), NOT in coupon
  restrictions: PassRestrictions | null;
}

export interface PassRestrictions {
  // Date-related (3% of passes, fine print only)
  blackout_dates: boolean;
  weekdays_only: boolean;
  seasonal: string | null;           // "Apr-Oct" style, or null
  // Process-related
  reservation_required: boolean;
}
```

### Summary string format (mobile e-commerce style)

Form labels:
- `free` → **"FREE"**
- `percent-off` value=50 → **"50% off"**
- `percent-off` value=30 → **"30% off"**
- `dollar-off` value=5 → **"$5 off"**
- `per-person-price` value=9 → **"$9/person"**
- `discount` → **"Special offer"**

Composition rules:
1. Capacity prefix: `"Up to {n} · "` / `"Per vehicle · "` / `"1 ticket · "` / `""` (unspecified)
2. If `audience_policies.length == 1 && audience == "Everyone"`: just append the form label.
   - "Up to 4 · 50% off"
   - "Per vehicle · FREE"
3. If `length == 1 && audience != "Everyone"`: append `"{audience-label} only · {form-label}"`.
   - "Up to 4 · Adults only · 50% off"
4. If `length >= 2` with all same `form+value`: merge audience-labels in parens.
   - "Up to 4 · 50% off (Adult, Child 8-16)"
5. If `length >= 2` with differing `form+value`: list each as `"{form-label} ({audience-list})"` joined by " · ".
   - "Up to 4 · 50% off (Adult) · $1/person (Child)"
   - "Up to 4 · 50% off (Adult, Child 8-16) · $2 off (Child <8)"
6. Bonus-tier (when one entry has form=free and overlaps another's audience by age range narrower):
   - "Up to 4 · 50% off · Kids under 3 free"

Audience label render:
- "Adult" → "Adult"
- "Child" with age_range={min:8,max:16} → "Child 8-16"
- "Child" with age_range={min:null,max:7} → "Child <8"
- "Child" with no age_range → "Child"
- "Youth" similar
- "Senior" similar
- "Everyone" / "Vehicle" / "Single ticket" → as-is (capacity prefix already conveys these for capacity)

---

## Task 1 — Define coupon schema (Python + TypeScript types)

**Files:**
- Create: `src/malibbene/build/coupon_types.py` — Python-side dataclasses + JSON schema lock
- Modify: `web/src/data/types.ts` — Replace Pass.discount + Pass.policy with Pass.coupon (see "Locked design" block above for exact shape)
- Test: `tests/test_coupon_types.py` — schema lock test

- [ ] **Step 1: Write failing schema lock test**

Create `tests/test_coupon_types.py`:

```python
"""Schema lock for Pass.coupon — keeps build output stable across refactors."""
import json
import glob


def test_coupon_raw_extraction_schema_lock():
    """Each pass_coupons/*.json file must conform to the locked schema."""
    files = glob.glob('data/raw/pass_coupons/*.json')
    if not files:
        # Plan-9 not yet executed past Task 2; skip when raw dir empty.
        import pytest
        pytest.skip("data/raw/pass_coupons/ is empty; Task 2 must run first")

    required_top = {"library_id", "attraction_slug", "status", "raw",
                    "capacity", "audience_policies", "source_phrases"}
    required_capacity = {"kind", "n"}
    valid_kinds = {"people", "vehicle", "ticket", "unspecified"}
    valid_audiences = {"Everyone", "Adult", "Child", "Youth", "Senior",
                       "Vehicle", "Single ticket"}
    valid_forms = {"free", "percent-off", "dollar-off", "per-person-price", "discount"}

    for f in files:
        with open(f, encoding='utf-8') as fh:
            d = json.load(fh)
        missing = required_top - set(d.keys())
        assert not missing, f"{f}: missing keys {missing}"
        if d["status"] != "ok":
            continue
        cap_missing = required_capacity - set(d["capacity"].keys())
        assert not cap_missing, f"{f}: capacity missing {cap_missing}"
        assert d["capacity"]["kind"] in valid_kinds, f"{f}: bad capacity.kind"
        assert isinstance(d["audience_policies"], list)
        assert len(d["audience_policies"]) >= 1, f"{f}: empty audience_policies"
        for i, ap in enumerate(d["audience_policies"]):
            assert ap["audience"] in valid_audiences, f"{f}: ap[{i}].audience"
            assert ap["form"] in valid_forms, f"{f}: ap[{i}].form"
            if ap.get("age_range") is not None:
                assert "min" in ap["age_range"] and "max" in ap["age_range"]
```

- [ ] **Step 2: Run test, expect SKIP (dir empty)**

```bash
python -m pytest tests/test_coupon_types.py -v
```

Expected: skipped (Task 2 hasn't created the dir yet). This is fine — test wakes up after Task 2.

- [ ] **Step 3: Update TypeScript types**

In `web/src/data/types.ts`, **completely replace** the `Discount` / `DiscountClass` / `Policy` / `EligibilityTag` / `ExclusionTag` / `BoostTag` exports and the `Pass.discount` / `Pass.policy` properties with the new coupon types from the "Locked design" section above. Keep `Pass.pickup_method`, `pickup_branches`, `pass_type`, `pass_type_raw`, `source_url`, `availability` unchanged. Add `Pass.coupon: Coupon` and `Pass.restrictions: PassRestrictions | null`.

- [ ] **Step 4: TypeScript compiles**

```bash
cd web && pnpm tsc --noEmit 2>&1 | head -30
```

Expected: many errors in consumer files (AttractionCard, DiscountLine, BookingConfirmModal, etc.) referencing removed `discount`/`policy`. **Leave them broken for now** — they're fixed in Task 5.

- [ ] **Step 5: Commit**

```bash
git add web/src/data/types.ts tests/test_coupon_types.py
git commit -m "plan-9: lock new Coupon schema in types.ts + schema-lock test"
```

---

## Task 2 — Re-extract 1008 passes via 5 parallel Sonnet subagents

**Files:**
- Create: `data/raw/pass_coupons/<lib_id>_<slug>.json` × 1008
- Create: `_tmp_coupon_batch_1.json` … `_tmp_coupon_batch_5.json` — batched input lists
- Reuse: existing `data/raw/pass_policies/<lib>_<slug>.json` for raw benefits_text

**Why Sonnet, why full re-extraction:**
- Per [[feedback_do_the_right_thing]], regex shortcuts left 31 "adults-only" passes mis-classified in plan-5; we don't repeat that mistake.
- Per [[feedback_no_api_call]], Sonnet subagent dispatch is the canonical LLM path.
- Per [[feedback_subagent_models]], extraction tasks use Sonnet, not Opus.

- [ ] **Step 1: Generate 5 batches of ~200 passes each**

Create `_tmp_make_coupon_batches.py` (delete after Task 2):

```python
import json
import glob
import math
import os

passes = []
for f in sorted(glob.glob('data/raw/pass_policies/*.json')):
    with open(f, encoding='utf-8') as fh:
        p = json.load(fh)
    raw = (p.get('raw') or '').strip()
    if not raw:
        continue
    passes.append({
        "library_id": p["library_id"],
        "attraction_slug": p["attraction_slug"],
        "benefits_text": raw,
    })

n = len(passes)
batch_size = math.ceil(n / 5)
for i in range(5):
    batch = passes[i * batch_size: (i + 1) * batch_size]
    with open(f'_tmp_coupon_batch_{i+1}.json', 'w', encoding='utf-8') as fh:
        json.dump(batch, fh, indent=2, ensure_ascii=False)
    print(f'batch {i+1}: {len(batch)} passes')
print(f'TOTAL: {n}')
```

Run it: `python _tmp_make_coupon_batches.py`. Expected output: `batch 1: ~202 passes` ... `TOTAL: 1008`.

- [ ] **Step 2: Dispatch 5 Sonnet subagents in parallel**

For each batch `i = 1..5`, dispatch a Sonnet subagent with the prompt template below. Send all 5 in one message so they run concurrently.

**Subagent prompt template** (parameterize `BATCH_NUMBER`):

```
You are extracting library museum pass coupons into a strict structured form.

Project root: F:/pj/NorthShore Kids Events. Read `_tmp_coupon_batch_BATCH_NUMBER.json` —
it has ~200 entries, each with {library_id, attraction_slug, benefits_text}.

For each entry, parse `benefits_text` and write
`data/raw/pass_coupons/<library_id>_<attraction_slug>.json` with EXACTLY this shape:

{
  "library_id": "<copy from input>",
  "attraction_slug": "<copy from input>",
  "status": "ok" | "failed:<reason>",
  "raw": "<copy benefits_text verbatim>",
  "capacity": {
    "kind": "people" | "vehicle" | "ticket" | "unspecified",
    "n": <int> | null
  },
  "audience_policies": [
    {
      "audience": "Everyone" | "Adult" | "Child" | "Youth" | "Senior" | "Vehicle" | "Single ticket",
      "age_range": null | {"min": <int>|null, "max": <int>|null},
      "count": <int> | null,
      "form": "free" | "percent-off" | "dollar-off" | "per-person-price" | "discount",
      "value": <number> | null
    }
  ],
  "restrictions": {
    "blackout_dates": <bool>,
    "weekdays_only": <bool>,
    "seasonal": "<month-month string>" | null,
    "reservation_required": <bool>
  },
  "source_phrases": {
    "capacity.n": "<verbatim substring from raw>",
    "audience_policies[0].form": "<verbatim substring>",
    ...
  }
}

EXTRACTION RULES (strict — past extractions fabricated, don't repeat):
1. EVERY non-null scalar value must trace to a verbatim substring of `raw`,
   recorded in `source_phrases` with the dotted path key. If a value cannot be
   sourced, set it to null.
2. capacity.kind:
   - "Up to N people / admits N visitors / admits a family of N" → "people", n=N
   - "Per vehicle / one car / in one vehicle" → "vehicle", n=null
   - "1 ticket / one admission ticket" → "ticket", n=1
   - No quantity stated → "unspecified", n=null
3. audience_policies:
   - Default case (~85%): one entry with audience="Everyone" and the form/value of
     the whole-party discount.
   - Mixed-audience case ("2 adults at 50% + 2 kids at $1"): one entry per audience,
     each with form/value matching its slice. Set `count` if raw specifies sub-caps.
   - Adults-only / Kids-only ("Adults at half-price; kids not included"):
     SINGLE entry with audience="Adult" (no "Everyone" entry for the others).
   - Bonus-tier ("All half-price; kids under 3 free, not counted"):
     TWO entries — {Everyone, half, 50} AND {Child, age_range={max:2}, free, null}.
   - "Up to four (4) people" → n=4 (parse word-numbers).
   - "Children under 3 free" → in age_range use {min:null, max:2} (inclusive,
     subtract 1 from open boundary).
   - "Ages 6-12" → age_range = {min:6, max:12}.
4. form mapping:
   - "free / no charge / complimentary" → "free", value=null
   - "half price / 50% off / 1/2 price" → "percent-off", value=50
   - "30% off / 25% off" → "percent-off", value=<int>
   - "$5 off / $10 off" → "dollar-off", value=<number>
   - "$9 per person / $5 each" → "per-person-price", value=<number>
   - "a discount / discounted admission / save money" with no specifics → "discount", value=null
5. restrictions:
   - blackout_dates: true if raw says "blackout / not valid on / except / excluded
     dates"
   - weekdays_only: true if raw restricts to Mon-Fri or "not valid weekends"
   - seasonal: extract a month-month string like "Apr-Oct" only if raw clearly
     says e.g. "valid May through October"; do not invent ranges
   - reservation_required: true if raw says "must reserve / reservation required"
6. If raw is too short or unparseable, status="failed:<reason>" and leave
   capacity/audience_policies as defaults (capacity.kind="unspecified",
   audience_policies=[]).

OUTPUT: ~200 JSON files. After writing all, print a summary:
"BATCH_NUMBER: <N> ok / <M> failed".

DO NOT modify any other files. DO NOT commit. DO NOT touch existing
data/raw/pass_policies/.
```

Dispatch 5 subagents in parallel. Wait for all 5 to complete.

- [ ] **Step 3: Verify all 1008 files written**

```bash
ls data/raw/pass_coupons/ | wc -l
```

Expected: 1008 (or slightly less if some passes had empty raw).

- [ ] **Step 4: Run schema-lock test, expect PASS**

```bash
python -m pytest tests/test_coupon_types.py -v
```

Expected: passes — every file conforms.

- [ ] **Step 5: Sanity-check 5 random samples**

```bash
python -c "
import json, glob, random
random.seed(42)
for f in random.sample(glob.glob('data/raw/pass_coupons/*.json'), 5):
    d = json.load(open(f, encoding='utf-8'))
    print('==', f)
    print('  raw:', d['raw'][:150])
    print('  capacity:', d['capacity'])
    print('  audience_policies:', d['audience_policies'])
    print('  source_phrases keys:', list(d.get('source_phrases',{}).keys()))
"
```

Confirm each looks sane (matching raw → structured + source_phrases populated).

- [ ] **Step 6: Cleanup temp files**

```bash
rm _tmp_coupon_batch_*.json _tmp_make_coupon_batches.py
```

- [ ] **Step 7: Commit**

```bash
git add data/raw/pass_coupons/
git commit -m "plan-9: re-extract 1008 pass coupons via 5 parallel Sonnet subagents"
```

---

## Task 3 — Build pipeline: coupons.py + integrate into passes.py

**Files:**
- Create: `src/malibbene/build/coupons.py` — loads `data/raw/pass_coupons/*.json` into a dict, attaches to passes
- Modify: `src/malibbene/build/passes.py` — replace `_policy_block` and discount-attachment logic with coupon attachment
- Modify: `scripts/build.py` — load coupons dir, pass to build_passes
- Test: `tests/test_build_coupons.py` — new test file

- [ ] **Step 1: Write failing test for coupon attachment**

Create `tests/test_build_coupons.py`:

```python
def test_build_passes_attaches_coupon():
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {"wakefield": {"passes": {"mos": {
        "pass_type": "digital", "pass_type_raw": "Digital",
        "benefits_text": "Pass admits up to 4 for half price.",
        "source_url": "", "benefit_label": "", "benefit_class": ""
    }}}}}
    coupons = {"wakefield_mos": {
        "status": "ok",
        "capacity": {"kind": "people", "n": 4},
        "audience_policies": [
            {"audience": "Everyone", "age_range": None, "count": None,
             "form": "percent-off", "value": 50}
        ],
        "restrictions": {"blackout_dates": False, "weekdays_only": False,
                         "seasonal": None, "reservation_required": False},
        "raw": "Pass admits up to 4 for half price.",
    }}
    out = build_passes(catalog, coupons=coupons)
    p = out["passes"][0]
    assert p["coupon"]["capacity"]["n"] == 4
    assert p["coupon"]["audience_policies"][0]["form"] == "percent-off"
    assert "discount" not in p   # old field removed
    assert "policy" not in p     # old field removed


def test_build_passes_emits_failed_status_when_coupon_missing():
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {"x": {"passes": {"y": {
        "pass_type": "digital", "pass_type_raw": "",
        "benefits_text": "", "source_url": "",
        "benefit_label": "", "benefit_class": ""}}}}}
    out = build_passes(catalog, coupons={})
    p = out["passes"][0]
    # Pass with no coupon entry gets a placeholder coupon with status info in summary
    assert p["coupon"]["capacity"]["kind"] == "unspecified"
    assert p["coupon"]["audience_policies"] == []
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
python -m pytest tests/test_build_coupons.py -v
```

- [ ] **Step 3: Create src/malibbene/build/coupons.py**

```python
"""Load + attach per-pass coupon data extracted by plan-9 subagents.

Reads data/raw/pass_coupons/<lib>_<slug>.json files written by Task 2.
"""
from __future__ import annotations


VALID_KINDS = {"people", "vehicle", "ticket", "unspecified"}
VALID_AUDIENCES = {"Everyone", "Adult", "Child", "Youth", "Senior",
                    "Vehicle", "Single ticket"}
VALID_FORMS = {"free", "percent-off", "dollar-off", "per-person-price", "discount"}


def coupon_block(rec: dict | None) -> dict:
    """Return a Coupon dict for a pass. If rec is missing/failed, return a
    well-formed empty coupon (kind=unspecified, no policies)."""
    if not rec or rec.get("status") != "ok":
        return {
            "capacity": {"kind": "unspecified", "n": None},
            "audience_policies": [],
            "summary": "",
        }
    cap = rec.get("capacity") or {}
    return {
        "capacity": {
            "kind": cap.get("kind", "unspecified"),
            "n": cap.get("n"),
        },
        "audience_policies": list(rec.get("audience_policies") or []),
        "summary": "",   # filled by coupon_summary.format() in Task 4
    }


def restrictions_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    r = rec.get("restrictions") or {}
    if not any([r.get("blackout_dates"), r.get("weekdays_only"),
                r.get("seasonal"), r.get("reservation_required")]):
        return None
    return {
        "blackout_dates": bool(r.get("blackout_dates")),
        "weekdays_only": bool(r.get("weekdays_only")),
        "seasonal": r.get("seasonal"),
        "reservation_required": bool(r.get("reservation_required")),
    }
```

- [ ] **Step 4: Modify src/malibbene/build/passes.py**

Replace any old `_policy_block` references with `coupon_block` / `restrictions_block`. The build_passes function signature becomes:

```python
def build_passes(catalog, coupons=None, classifications=None, branches_doc=None):
    from malibbene.build.coupons import coupon_block, restrictions_block
    coupons = coupons or {}
    # ... existing pickup logic ...

    for ... in catalog["libraries"].items():
        for slug, p in lib["passes"].items():
            coupon_key = f"{lib_id}_{slug}"
            coupon_rec = coupons.get(coupon_key)

            # Build per-pass record
            pass_obj = {
                "library_id": lib_id,
                "attraction_slug": slug,
                "pass_type": pass_type,
                "pass_type_raw": p.get("pass_type_raw", ""),
                "pickup_method": pickup_method,
                "pickup_branches": pickup_branches,
                "coupon": coupon_block(coupon_rec),
                "restrictions": restrictions_block(coupon_rec),
                "source_url": p.get("source_url", ""),
                "availability": p.get("calendar") or None,
            }
            out.append(pass_obj)
```

Drop the old `discount` and `policy` fields entirely — they don't appear in the new pass_obj.

Update `_meta` to count coupons instead of policies:

```python
"_meta": {
    "n_passes": len(out),
    "n_with_availability": sum(1 for x in out if x["availability"]),
    "n_with_coupon": sum(1 for x in out if x["coupon"]["audience_policies"]),
    "n_with_restrictions": sum(1 for x in out if x["restrictions"]),
    "n_physical_at_branch": sum(1 for x in out if x["pickup_method"] == "physical_at_branch"),
    "n_digital": sum(1 for x in out if x["pickup_method"] == "digital"),
    ...
}
```

- [ ] **Step 5: Modify scripts/build.py**

Replace the policies-loading block with coupons-loading:

```python
# Was: policies = _load_dir_jsons(raw_root / "pass_policies")
coupons = _load_dir_jsons(raw_root / "pass_coupons")
passes_doc = build_passes(catalog, coupons=coupons,
                          classifications=classifications,
                          branches_doc=branches_doc)
```

(Delete the now-unused `policies` variable usage downstream.)

- [ ] **Step 6: Update existing tests that referenced policies**

Search and update:

```bash
grep -rn "\"policy\"\|policies=" tests/ src/malibbene/build/
```

Anywhere that asserted on `p["policy"]` or passed `policies=`, replace with the coupon equivalent. The old `test_build_passes_attaches_policy_from_dict` should be removed (its job is now covered by the new coupon test).

- [ ] **Step 7: Run all backend tests**

```bash
python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 8: Rebuild structured data**

```bash
python scripts/build.py
```

Expected output line: `1008 passes (... with coupon, ... physical_at_branch)`.

- [ ] **Step 9: Verify passes.json has coupon, no policy/discount**

```bash
python -c "
import json
p = json.load(open('data/structured/passes.json', encoding='utf-8'))['passes'][0]
assert 'coupon' in p and 'discount' not in p and 'policy' not in p
print('shape OK:', list(p.keys()))
print('sample coupon:', p['coupon'])
"
```

- [ ] **Step 10: Commit**

```bash
git add src/malibbene/build/coupons.py src/malibbene/build/passes.py scripts/build.py tests/test_build_coupons.py tests/test_build_passes.py data/structured/passes.json
git commit -m "plan-9: replace discount+policy with coupon in build pipeline"
```

---

## Task 4 — Coupon summary generator

**Files:**
- Create: `src/malibbene/build/coupon_summary.py` — produces the mobile e-commerce style summary string
- Modify: `src/malibbene/build/coupons.py` — call `format()` in `coupon_block`
- Test: `tests/test_coupon_summary.py` — new test file with the 8 reference examples

- [ ] **Step 1: Write failing tests with the 8 reference examples**

Create `tests/test_coupon_summary.py`:

```python
"""Test the coupon summary string generator against the locked reference cases."""
from malibbene.build.coupon_summary import format_summary


def _cap(kind="people", n=4):
    return {"kind": kind, "n": n}


def _ap(audience, form, value=None, age_range=None, count=None):
    return {"audience": audience, "form": form, "value": value,
            "age_range": age_range, "count": count}


def test_simple_party_wide_half():
    s = format_summary(_cap(), [_ap("Everyone", "percent-off", 50)])
    assert s == "Up to 4 · 50% off"


def test_simple_party_wide_free():
    s = format_summary(_cap(), [_ap("Everyone", "free")])
    assert s == "Up to 4 · FREE"


def test_per_person_price():
    s = format_summary(_cap(), [_ap("Everyone", "per-person-price", 9)])
    assert s == "Up to 4 · $9/person"


def test_per_vehicle_free():
    s = format_summary(_cap("vehicle", None), [_ap("Vehicle", "free")])
    assert s == "Per vehicle · FREE"


def test_bonus_tier_kids_under_n_free():
    """All half-price, with kids under 3 free as a bonus second entry."""
    s = format_summary(_cap(), [
        _ap("Everyone", "percent-off", 50),
        _ap("Child", "free", age_range={"min": None, "max": 2}),
    ])
    assert s == "Up to 4 · 50% off · Kids under 3 free"


def test_adults_only():
    s = format_summary(_cap(), [_ap("Adult", "percent-off", 50)])
    assert s == "Up to 4 · Adults only · 50% off"


def test_mixed_adult_child_pricing():
    """2 adults at 50%, 2 kids at $1 each."""
    s = format_summary(_cap(), [
        _ap("Adult", "percent-off", 50, count=2),
        _ap("Child", "per-person-price", 1, count=2),
    ])
    assert s == "Up to 4 · 50% off (Adult) · $1/person (Child)"


def test_complex_three_audience_split():
    """Adults + older kids half; younger kids $2 off."""
    s = format_summary(_cap(), [
        _ap("Adult", "percent-off", 50),
        _ap("Child", "percent-off", 50, age_range={"min": 8, "max": 16}),
        _ap("Child", "dollar-off", 2, age_range={"min": None, "max": 7}),
    ])
    assert s == "Up to 4 · 50% off (Adult, Child 8-16) · $2 off (Child <8)"


def test_dollar_off_simple():
    s = format_summary(_cap(), [_ap("Everyone", "dollar-off", 5)])
    assert s == "Up to 4 · $5 off"


def test_unspecified_capacity():
    s = format_summary({"kind": "unspecified", "n": None},
                       [_ap("Everyone", "percent-off", 50)])
    assert s == "50% off"


def test_empty_policies_returns_empty_string():
    s = format_summary(_cap(), [])
    assert s == ""
```

- [ ] **Step 2: Run tests, expect ALL FAIL (module doesn't exist)**

```bash
python -m pytest tests/test_coupon_summary.py -v
```

- [ ] **Step 3: Implement src/malibbene/build/coupon_summary.py**

```python
"""Generate mobile e-commerce style summary strings from Coupon structure."""
from __future__ import annotations


def _form_label(form: str, value: float | None) -> str:
    if form == "free":
        return "FREE"
    if form == "percent-off" and value is not None:
        v = int(value) if value == int(value) else value
        return f"{v}% off"
    if form == "dollar-off" and value is not None:
        v = int(value) if value == int(value) else value
        return f"${v} off"
    if form == "per-person-price" and value is not None:
        v = int(value) if value == int(value) else value
        return f"${v}/person"
    if form == "discount":
        return "Special offer"
    return ""


def _audience_label(ap: dict) -> str:
    audience = ap["audience"]
    age = ap.get("age_range")
    if audience in ("Adult", "Senior", "Vehicle", "Single ticket", "Everyone"):
        return audience + ("s" if audience == "Adult" else "")
    # Child / Youth get age suffix when range present
    if not age:
        return audience
    lo, hi = age.get("min"), age.get("max")
    if lo is None and hi is not None:
        return f"{audience} <{hi + 1}"
    if lo is not None and hi is None:
        return f"{audience} {lo}+"
    if lo is not None and hi is not None:
        return f"{audience} {lo}-{hi}"
    return audience


def _capacity_prefix(capacity: dict) -> str:
    kind, n = capacity.get("kind"), capacity.get("n")
    if kind == "people" and n is not None:
        return f"Up to {n} · "
    if kind == "vehicle":
        return "Per vehicle · "
    if kind == "ticket":
        return "1 ticket · "
    return ""


def format_summary(capacity: dict, audience_policies: list[dict]) -> str:
    if not audience_policies:
        return ""

    prefix = _capacity_prefix(capacity)

    # Special case: bonus-tier (whole-party discount + child-only free under N)
    if (len(audience_policies) == 2
        and audience_policies[0]["audience"] == "Everyone"
        and audience_policies[1]["audience"] == "Child"
        and audience_policies[1]["form"] == "free"
        and (audience_policies[1].get("age_range") or {}).get("max") is not None):
        primary = _form_label(audience_policies[0]["form"], audience_policies[0]["value"])
        ar = audience_policies[1]["age_range"]
        kids_label = f"Kids under {ar['max'] + 1} free"
        return f"{prefix}{primary} · {kids_label}"

    # Single policy
    if len(audience_policies) == 1:
        ap = audience_policies[0]
        label = _form_label(ap["form"], ap["value"])
        if ap["audience"] == "Everyone":
            return f"{prefix}{label}"
        if ap["audience"] == "Adult":
            return f"{prefix}Adults only · {label}"
        if ap["audience"] in ("Vehicle", "Single ticket"):
            return f"{prefix}{label}"
        return f"{prefix}{_audience_label(ap)} · {label}"

    # Multi-policy: group by (form, value), within each group merge audience labels
    groups = []   # list of (form_label, [audience_labels])
    seen = {}
    for ap in audience_policies:
        key = (ap["form"], ap["value"])
        label = _form_label(ap["form"], ap["value"])
        if key in seen:
            seen[key][1].append(_audience_label(ap))
        else:
            entry = (label, [_audience_label(ap)])
            seen[key] = entry
            groups.append(entry)

    parts = []
    for form_label, audiences in groups:
        if len(audiences) == 1:
            parts.append(f"{form_label} ({audiences[0]})")
        else:
            parts.append(f"{form_label} ({', '.join(audiences)})")
    return prefix + " · ".join(parts)
```

- [ ] **Step 4: Wire format_summary into coupon_block**

In `src/malibbene/build/coupons.py`, update `coupon_block`:

```python
from malibbene.build.coupon_summary import format_summary

def coupon_block(rec: dict | None) -> dict:
    if not rec or rec.get("status") != "ok":
        return {"capacity": {"kind": "unspecified", "n": None},
                "audience_policies": [], "summary": ""}
    cap = {"kind": (rec.get("capacity") or {}).get("kind", "unspecified"),
           "n":    (rec.get("capacity") or {}).get("n")}
    aps = list(rec.get("audience_policies") or [])
    return {"capacity": cap, "audience_policies": aps,
            "summary": format_summary(cap, aps)}
```

- [ ] **Step 5: Run all tests, expect PASS**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 6: Rebuild + spot-check 5 summaries**

```bash
python scripts/build.py
python -c "
import json
passes = json.load(open('data/structured/passes.json', encoding='utf-8'))['passes']
seen = set()
for p in passes:
    s = p['coupon']['summary']
    if s and s not in seen:
        seen.add(s)
        print(f'  {p[\"library_id\"]:14s} {p[\"attraction_slug\"]:30s} → {s}')
    if len(seen) >= 15: break
"
```

Confirm summaries look natural and mobile-friendly.

- [ ] **Step 7: Commit**

```bash
git add src/malibbene/build/coupon_summary.py src/malibbene/build/coupons.py tests/test_coupon_summary.py data/structured/passes.json
git commit -m "plan-9: coupon_summary generator + 11 reference tests"
```

---

## Task 5 — Frontend: rewrite consumers for new Coupon shape

**Files:**
- Modify: `web/src/components/AttractionCard.tsx` — show coupon.summary instead of inline discount logic
- Modify: `web/src/components/DiscountLine.tsx` — RENAME to `CouponLine.tsx`, render coupon
- Modify: `web/src/pages/AttractionDetail.tsx` — new comparison view (N rows per library)
- Modify: `web/src/lib/discount-display.ts` — REPLACE with `web/src/lib/coupon-display.ts` (rendering helpers if needed beyond summary)
- Delete (or empty): old test files that reference removed types
- Test: extend `web/src/components/CouponLine.test.tsx`

- [ ] **Step 1: Catalog every consumer of the removed types**

```bash
cd web
grep -rn "pass\.discount\|pass\.policy\|Discount{\|Policy{\|formatDiscount\|EligibilityTag\|ExclusionTag\|BoostTag" src/ | grep -v __snapshots__ | head -40
```

Make a list of every file that references the removed types. Each must be fixed.

- [ ] **Step 2: Rewrite AttractionCard.tsx to render coupon.summary**

In `web/src/components/AttractionCard.tsx`, replace any inline discount label logic with:

```tsx
<div className="coupon-summary">
  {pass.coupon.summary}
</div>
```

Pass the whole `pass` object (not just `discount`). The library name and pickup info already render from other props.

- [ ] **Step 3: Rename DiscountLine → CouponLine**

```bash
git mv web/src/components/DiscountLine.tsx web/src/components/CouponLine.tsx
git mv web/src/components/DiscountLine.test.tsx web/src/components/CouponLine.test.tsx
```

In CouponLine.tsx, the component now takes `coupon: Coupon` instead of `discount: Discount`. Render layout:

```tsx
interface Props { coupon: Coupon; }

export function CouponLine({ coupon }: Props) {
  return (
    <div className="coupon-line">
      <span className="coupon-summary">{coupon.summary}</span>
    </div>
  );
}
```

Update CouponLine.test.tsx to test rendering the 4-5 most common summaries.

- [ ] **Step 4: Replace lib/discount-display.ts with lib/coupon-display.ts**

```bash
rm web/src/lib/discount-display.ts web/src/lib/discount-display.test.ts
```

If any component still imports from the old path, point it at `pass.coupon.summary` directly. If true helper functions are needed beyond summary (probably aren't), create `web/src/lib/coupon-display.ts` with the helpers. Otherwise skip.

- [ ] **Step 5: AttractionDetail.tsx — comparison view**

This is the user-facing core of plan-9. The detail page now shows:

```tsx
<section className="comparison">
  <h2>Original prices · 原价</h2>
  <PriceTable price={attraction.original_price} />

  <h2>Available coupons · 可用优惠 ({passes.length})</h2>
  <div className="coupon-list">
    {passes.map(p => (
      <div key={p.library_id} className="coupon-row">
        <header>
          <span className="lib-name">{libraryNameOf(p.library_id)}</span>
          <PassTypeLabel type={p.pass_type} />
          {p.pickup_method === 'physical_at_branch' && (
            <span className="pickup-hint">· Pickup at {branchNameOf(p.pickup_branches[0])}</span>
          )}
        </header>
        <div className="coupon-summary">{p.coupon.summary}</div>
        {p.restrictions && <RestrictionsBadge restrictions={p.restrictions} />}
      </div>
    ))}
  </div>
</section>
```

`RestrictionsBadge` is a small component that shows a ⚠ icon with hover text — only rendered when restrictions are non-null. Date/process limits live there per `feedback_core_product_value`.

- [ ] **Step 6: Update BookingConfirmModal.test.tsx**

The mock `Pass` object in that test (line 9-20 currently) uses old shape. Update to:

```tsx
const mockPass: Pass = {
  library_id: 'wakefield',
  attraction_slug: 'zoo-boston',
  pass_type: 'digital',
  pass_type_raw: 'digital',
  pickup_method: 'digital',
  pickup_branches: [],
  coupon: {
    capacity: { kind: 'people', n: 4 },
    audience_policies: [{ audience: 'Everyone', age_range: null, count: null,
                          form: 'free', value: null }],
    summary: 'Up to 4 · FREE',
  },
  restrictions: null,
  source_url: 'https://example.com/book',
  availability: null,
};
```

- [ ] **Step 7: Run frontend tests, fix remaining failures one at a time**

```bash
cd web && pnpm test -- --run 2>&1 | tail -30
```

Expected: green after all consumer fixes.

- [ ] **Step 8: TypeScript clean**

```bash
cd web && pnpm tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 9: Production build**

```bash
cd web && pnpm run build
```

Expected: succeeds.

- [ ] **Step 10: Manual smoke test (optional but recommended)**

```bash
cd web && pnpm run dev
```

Open `http://localhost:5173/`, navigate to an attraction with multiple libraries (e.g. MFA), confirm the comparison view shows N coupon rows with the new summary strings.

- [ ] **Step 11: Commit**

```bash
cd .. && git add web/src/ && git commit -m "plan-9: rewrite frontend for Coupon model + comparison view"
```

---

## Task 6 — Audit page: drop 3 panels, add coupon comparison view

**Files:**
- Modify: `scripts/build_audit_site.py`
- Verify: `audit/policies.html` and a new `audit/coupons.html` or panel

- [ ] **Step 1: Remove the 3 panels from policies page generator**

In `scripts/build_audit_site.py`, find and delete the panel-generating blocks for:
- Eligibility tags histogram
- Restrictions histogram (and Date histogram split if present)
- 16-Pattern frequency table

(Bonuses histogram also has no place in the new model — remove if present.)

- [ ] **Step 2: Repurpose policies.html to coupon distribution**

Add a new top-of-page panel showing:
- `Coupon form distribution` — Counter of `coupon.audience_policies[*].form` across all 1008 passes, displayed with the e-commerce labels (FREE / 50% off / 30% off / $X off / $Y/person / Special offer)
- `Capacity distribution` — Counter of `capacity.kind` + sub-bins of `n` for people-kind
- `Audience-split distribution` — count of passes with 1 audience entry (party-wide) vs 2+ (mixed/bonus/etc)

```python
form_counter = Counter()
cap_counter = Counter()
ap_len_counter = Counter()
for p in passes:
    c = p["coupon"]
    cap = c["capacity"]
    cap_key = f"{cap['kind']}" + (f" (n={cap['n']})" if cap['n'] else "")
    cap_counter[cap_key] += 1
    aps = c["audience_policies"]
    ap_len_counter[len(aps)] += 1
    for ap in aps:
        form_counter[ap["form"]] += 1
```

- [ ] **Step 3: Per-attraction comparison panel on attractions.html**

For each attraction card on `audit/attractions.html`, after the existing meta block, add a "Coupon comparison" section listing each library's coupon row:

```python
# inside the per-attraction loop in build_audit_site.py
matching_passes = [p for p in passes if p["attraction_slug"] == slug]
coupon_rows_html = []
for mp in matching_passes:
    lib = mp["library_id"]
    pickup = mp["pickup_method"]
    method_label = {"digital": "E-pass",
                    "physical_at_branch": f"Pickup at {mp['pickup_branches'][0] if mp['pickup_branches'] else '?'}"
                   }.get(pickup, pickup)
    coupon_rows_html.append(
        f'<tr><td>{esc(lib)}</td><td>{esc(method_label)}</td>'
        f'<td><b>{esc(mp["coupon"]["summary"])}</b></td></tr>'
    )
```

Embed in a `<table class="coupon-compare">` with headers Library / Pickup / Coupon.

- [ ] **Step 4: Rebuild audit site**

```bash
python scripts/build_audit_site.py
```

- [ ] **Step 5: Manual inspection**

Open `audit/policies.html` and `audit/attractions.html` in browser. Confirm:
- 3 removed panels are gone
- New coupon-form + capacity + audience-split panels present
- Each attraction card shows a comparison table of all its libraries' coupons

- [ ] **Step 6: Commit**

```bash
git add scripts/build_audit_site.py audit/
git commit -m "plan-9: audit page reworked for Coupon model + per-attraction comparison"
```

---

## Task 7 — Cleanup + final verification

- [ ] **Step 1: Delete legacy raw policies dir**

The 1008 files in `data/raw/pass_policies/` are now superseded by `data/raw/pass_coupons/`. Archive then remove:

```bash
mkdir -p docs/archive
mv data/raw/pass_policies docs/archive/pass_policies_pre_plan9
```

(Keep in archive for one release in case extraction needs revisiting; can be deleted later.)

- [ ] **Step 2: Search for stale references**

```bash
grep -rn "pass_policies\|policy_block\|discount\.class\|Policy\b\|EligibilityTag\|ExclusionTag\|BoostTag\|DiscountClass" src/ web/src/ scripts/ tests/ 2>&1 | head -30
```

Expected: zero hits in `src/`, `web/src/`, `scripts/`, `tests/`. The only acceptable hits are in `docs/` (older plans referring to old shape) and `data/structured/library_catalog.json` (intermediate, fine).

- [ ] **Step 3: Run full backend + frontend test suites**

```bash
python -m pytest tests/ -q
cd web && pnpm test -- --run
```

Both green.

- [ ] **Step 4: Run full pipeline end-to-end**

```bash
cd .. && python scripts/build.py
python scripts/build_audit_site.py
```

Both succeed.

- [ ] **Step 5: Update CLAUDE.md**

In the "Key Technical Decisions" section, replace the old `Pass.policy + Pass.discount` description with:

```
- Pass.coupon (plan-9): single source of truth for "what this pass does for the user".
  Shape: { capacity {kind, n}, audience_policies [{audience, age_range, count, form, value}], summary }.
  Summary string is backend-generated using mobile e-commerce style labels
  ("50% off", "FREE", "$5 off", "$9/person"). Date and process restrictions are
  side-channelled in Pass.restrictions, surfaced as UI fine-print only.
```

Remove any lingering mention of pass.policy / pass.discount fields.

- [ ] **Step 6: Commit**

```bash
git add data/raw/ docs/archive/ CLAUDE.md
git commit -m "plan-9: archive legacy pass_policies, update CLAUDE.md, end-to-end verified"
```

---

## Final Verification

- [ ] **All audit findings closed**

```bash
python -c "
import json
attrs = json.load(open('data/structured/attractions.json', encoding='utf-8'))['attractions']
passes = json.load(open('data/structured/passes.json', encoding='utf-8'))['passes']

# Coupon shape present on every pass
assert all('coupon' in p and 'capacity' in p['coupon'] and 'audience_policies' in p['coupon']
           and 'summary' in p['coupon'] for p in passes), 'shape regression'

# discount / policy fully removed
assert not any('discount' in p or 'policy' in p for p in passes), 'legacy fields remain'

# Sample summaries
seen = set()
for p in passes:
    s = p['coupon']['summary']
    if s and s not in seen:
        seen.add(s)
print(f'distinct summaries: {len(seen)}')
print(f'passes with non-empty summary: {sum(1 for p in passes if p[\"coupon\"][\"summary\"])}')
print('All shape checks pass.')
"
```

Expected: `passes with non-empty summary` ≈ 950+ out of 1008 (small tail of failed extractions OK), distinct summaries ≥ 50.

- [ ] **Manual visual check (frontend dev server)**

```bash
cd web && pnpm run dev
```

Open MFA detail page (any attraction with many libraries), confirm:
- Comparison list shows N rows (one per library)
- Each row has summary like "Up to 4 · 50% off" / "Up to 4 · FREE" etc.
- Restrictions ⚠ badge appears on the ~3% with date/process limits
- Original prices shown at top for mental math
