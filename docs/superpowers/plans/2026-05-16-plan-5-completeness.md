# Plan 5 — Data completeness, policy structure, missing UI features, and tests

> **For agentic workers:** Use superpowers:subagent-driven-development to execute task-by-task. Steps use checkbox (`- [ ]`) syntax. This plan picks up everything not finished by plans 1–4 and the user's most recent feedback.

**Goal:** Close every remaining gap from plans 1–4, address the newly-identified pricing-policy complexity (party size, eligibility tiers, who-gets-the-discount), and add frontend component tests. After this plan, v0.1 is "feature complete" against the spec + user feedback.

**Architecture:** Two halves — (a) data backfill + new structured `policy` fields propagated through the build pipeline, and (b) frontend changes to consume the richer data plus the deferred UX items (detail-page completeness, settings search, guest-lock mode, component tests).

**Tech stack:** Existing — Python 3.11+ scrapers + Subagent dispatch for LLM extraction; React 19 + Vite 8 + Vitest 3 + Testing Library on the frontend.

---

## 0. Why this plan

User feedback after seeing the production UI:

1. **Discount displays are misleading.** "$30 → $15" treats *50% off up-to-4-people* the same as *50% off adult only*. Real benefit text shows party caps, eligibility tiers, vehicle rules, etc. — none currently surfaced.
2. **Price tiers are richer than `adult/child`.** Real data has Youth (11–16), Family of 4, Military, Educator, Member, "Free under 2/3/5" — we ignore most of it.
3. **Plans 1–4 left several known holes** — geo coverage (75/104), price coverage (54/104), 4 unfetchable libraries, 11 hours-less multi-property attractions, 46 un-mapped libcal passes, missing detail-page fields (phone, description, guest lock mode), no settings-page library search, zero frontend component tests.

User explicitly said: complete everything still open. Re. spec §10 "out of scope": **only the frontend component tests bucket is in scope here**.

---

## 1. New data fields introduced by this plan

### 1.1 Attraction price tiers — broadened schema

Current `OriginalPrice` only has `adult / child / senior / student / family / free_under_age / notes`. Real data also has:
- **youth** (ages roughly 11–16, between child and adult)
- **toddler** (ages 2–5 if charged separately, distinct from free_under_age)
- **military / educator / first_responder** (often grouped with student)
- **member** (separate "members free" common policy — modeled as notes)

Decision: keep current fields, add three new optionals (`youth`, `military`, `educator`). `notes` continues to capture true edge cases.

### 1.2 NEW: per-pass `policy` block

Each `Pass` gains a `policy` object extracted from `discount.raw`:

```json
{
  "policy": {
    "max_people": 4 | null,             // "up to 4 people"
    "max_adults": 2 | null,             // when split: "2 adults + 2 children"
    "max_children": 2 | null,
    "eligibility": "all" | "adults_only" | "vehicle" | "single_ticket" | null,
    "free_under_age": 2 | null,         // "children under 2 free"
    "savings_per_person": 5 | null,     // for "$5 off each"
    "raw_extract": "free admission for up to 4 people in 1 vehicle"
  }
}
```

This stays separate from `discount` so existing fields are unchanged.

### 1.3 NEW: attraction `description` + `phone` fields

Currently `museum_name + address + website` only. Add:
- `description` — 1–3 sentence summary (from website meta description or Wikipedia first paragraph)
- `phone` — formatted US phone number when available (already in raw assabet data, just need to surface it)

---

## 2. File / responsibility split

```
src/malibbene/build/
└── attractions.py                    # add youth/military/educator + description/phone + policy aggregation

src/malibbene/sources/attractions/    # NEW scrapers as needed
└── descriptions.py                   # NEW — fetch + LLM-extract museum description

data/raw/
├── attraction_descriptions/<slug>.json   # NEW
├── attraction_phones/<slug>.json         # NEW (or surface from existing data)
└── pass_policies/<lib>_<slug>.json        # NEW — per (library, attraction) extracted policy

web/src/
├── data/types.ts                     # add Pass.policy, Attraction.description, .phone, expanded OriginalPrice
├── lib/discount-display.ts           # NEW — pure: formats discount + policy into the right display string
│                                       (e.g., "50% off · up to 4 people", not "$30 → $15")
├── components/
│   ├── DiscountLine.tsx              # NEW — renders one option row's discount + policy correctly
│   ├── LibrarySearchBox.tsx          # NEW — used by My passes settings + (future) anywhere
│   └── GuestLockedRow.tsx            # NEW — row variant for guests on detail page
├── pages/
│   ├── AttractionDetail.tsx          # add description, phone, guest lock mode
│   └── MyPasses.tsx                  # add library search/filter
└── (tests)                           # NEW component tests
    ├── components/AttractionCard.test.tsx
    ├── components/PassTypeLabel.test.tsx
    ├── components/ZipPill.test.tsx
    ├── components/SearchBox.test.tsx
    ├── components/BookingConfirmModal.test.tsx
    ├── components/CategoryChips.test.tsx
    ├── components/FavoriteButton.test.tsx
    └── components/DiscountLine.test.tsx
```

---

## Task 1 — Re-extract price tiers (broaden coverage)

**Files:**
- Re-run subagent on `data/raw/attraction_prices/_pages/*.html`; allow new fields.
- Update `data/raw/attraction_prices/<slug>.json` schema to include `youth`, `military`, `educator`.
- No changes to existing pages — purely re-extraction.

### Step 1.1 — Audit existing HTMLs for richer tiers

```bash
cd "F:/pj/NorthShore Kids Events"
# Find HTMLs mentioning Youth / Military / Educator that we currently miss
python -c "
import re, glob
for f in glob.glob('data/raw/attraction_prices/_pages/*.html'):
    body = open(f, encoding='utf-8', errors='replace').read().lower()
    found = [w for w in ['youth', 'military', 'educator', 'first responder', 'family of 4', 'family pack'] if w in body]
    if found:
        print(f, found)
" | head -30
```

### Step 1.2 — Dispatch broader price extraction subagent

Dispatch a Sonnet subagent. Same strict rules as before (every numeric value must appear in the HTML), but expanded schema:

```json
{
  "adult": <number or null>,
  "child": <number or null>,
  "youth": <number or null>,                // NEW: 11–16 or "youth" line
  "senior": <number or null>,
  "student": <number or null>,
  "military": <number or null>,             // NEW
  "educator": <number or null>,             // NEW: incl. "teacher"
  "family": <number or null>,
  "free_under_age": <number or null>,
  "notes": <string or null>,
  "source_url": <string>
}
```

Target: improve 54/104 → 75+/104 by capturing more tiers from already-fetched HTML. Keep failed entries failed (don't fabricate).

### Step 1.3 — Verify, rerun build, commit

```bash
python scripts/build.py
# Spot check
python -c "
import json
attrs = json.load(open('data/structured/attractions.json', encoding='utf-8'))
n_youth = sum(1 for a in attrs['attractions'] if a['original_price'] and a['original_price'].get('youth') is not None)
n_mil = sum(1 for a in attrs['attractions'] if a['original_price'] and a['original_price'].get('military') is not None)
print(f'youth: {n_youth}, military: {n_mil}')
"
git add data/raw/attraction_prices/ data/structured/attractions.json
git commit -m "data: re-extract attraction prices with youth/military/educator tiers"
```

---

## Task 2 — Extract `policy` per pass

**Why:** Discount text encodes critical information (party caps, vehicle rules) currently hidden in `discount.raw`. Surface it.

**Files:**
- Dispatch extraction subagent (Sonnet) over `data/raw/<platform>/index/*.json` reading `passes[].benefits_text` directly (no HTML needed — text is already there).
- Output: `data/raw/pass_policies/<lib>_<slug>.json`.
- Build pipeline reads these and attaches `policy` to each Pass.

### Step 2.1 — Subagent prompt sketch

Input: a pass's `benefits_text` (e.g., "This pass admits up to four (4) people at half price.")

Output schema:

```json
{
  "library_id": "wakefield",
  "attraction_slug": "boston-childrens-museum",
  "status": "ok" | "failed:unparseable",
  "max_people": 4 | null,
  "max_adults": 2 | null,
  "max_children": 2 | null,
  "eligibility": "all" | "adults_only" | "vehicle" | "single_ticket" | "members" | null,
  "free_under_age": 2 | null,
  "savings_per_person_usd": 5 | null,
  "notes": "Children under 2 admitted for free." | null,
  "raw": "<original benefits_text>"
}
```

**Strict rules (same as previous extractions):**
- Every numeric value must be derivable from the text. If "four (4) people" → max_people=4. If text says only "passes admit a family" with no number → max_people=null, eligibility="all".
- Vehicle-related text ("one vehicle", "per car") → eligibility="vehicle", max_people=null (varies per vehicle).
- Single-ticket text ("one admission ticket") → eligibility="single_ticket", max_people=1.
- Members-only text → eligibility="members".
- Do NOT make up values. `null` is acceptable.

### Step 2.2 — Process ~962 passes in batches

Batch size 50. Sonnet handles JSON extraction. Each subagent run processes one platform (assabet / libcal / museumkey).

### Step 2.3 — Verify policy coverage

```bash
python -c "
import json, glob
files = glob.glob('data/raw/pass_policies/*.json')
ok = sum(1 for f in files if json.load(open(f, encoding='utf-8')).get('status') == 'ok')
print(f'{ok}/{len(files)} policies extracted')

# Distribution of party caps
import collections
caps = collections.Counter()
for f in files:
    d = json.load(open(f, encoding='utf-8'))
    if d.get('status') == 'ok':
        caps[d.get('max_people')] += 1
print('max_people:', dict(caps))
"
```

Target: ≥85% policies extracted from passes with non-empty `benefits_text`.

### Step 2.4 — Commit

```bash
git add data/raw/pass_policies/
git commit -m "data(policies): extract structured pass policy from benefits_text via subagent"
```

---

## Task 3 — Recover 29 attractions missing geo

**Files:**
- `scripts/geocode_all.py` — extend with fallback strategies.

### Step 3.1 — Identify gaps

```bash
python -c "
import json
geo = json.load(open('data/structured/geo.json', encoding='utf-8'))
attrs = json.load(open('data/structured/attractions.json', encoding='utf-8'))
missing = [a for a in attrs['attractions'] if not (geo['attractions'].get(a['slug'], {}).get('ok'))]
for a in missing:
    print(f'{a[\"slug\"]:50s} addr={a[\"address\"]!r}')
" | head -20
```

### Step 3.2 — Fallback strategy

In `scripts/geocode_all.py`, after the primary attempt:

```python
def _attraction_query(entry: dict) -> str | None:
    addr = (entry.get("address") or "").strip()
    if addr: return addr
    # Fallback 1: museum_name + city if known
    name = (entry.get("museum_name") or "").strip()
    if not name: return None
    # Fallback 2: name + 'Massachusetts' (catches statewide orgs)
    return f"{name}, Massachusetts, USA"
```

For empty-address attractions (Trustees of Reservations, JFK Library, etc.), try the museum_name + state. For "Suite 900" / "Building 22" type cluttered addresses, pre-strip those tokens before sending to Nominatim.

### Step 3.3 — Run + verify

Run `python scripts/geocode_all.py`. Expected: 75 → 90+/104.

### Step 3.4 — Commit

```bash
python scripts/build.py
git add scripts/geocode_all.py data/structured/geo.json data/structured/attractions.json
git commit -m "fix(geocode): museum-name fallback for attractions with missing/dirty addresses"
```

---

## Task 4 — Fix 4 missing library street addresses

**Affected:** tewksbury, arlington, chelsea, watertown — fetcher got Cloudflare 403 or JS-only sites.

### Step 4.1 — Manual override path

These addresses are stable public info. Hand-enter them into `config/manual_overrides.json` under `libraries`:

```json
{
  "libraries": {
    "tewksbury":  { "address": { "street": "300 Chandler Street", "city": "Tewksbury",  "state": "MA", "zip": "01876" } },
    "arlington":  { "address": { "street": "700 Massachusetts Avenue", "city": "Arlington", "state": "MA", "zip": "02476" } },
    "chelsea":    { "address": { "street": "569 Broadway",        "city": "Chelsea",    "state": "MA", "zip": "02150" } },
    "watertown":  { "address": { "street": "123 Main Street",     "city": "Watertown",  "state": "MA", "zip": "02472" } }
  }
}
```

**Verify each address against a current source** (library main site, Google Maps) before writing — these are stable but a few buildings have moved.

### Step 4.2 — Wire overrides into build_libraries

`scripts/build.py` already applies `_apply_overrides`. Re-run:

```bash
python scripts/build.py
python scripts/geocode_all.py
python scripts/build.py
```

(Two build runs because geocode_all reads structured libraries.json and writes geo.json, which build then consumes.)

### Step 4.3 — Commit

```bash
git add config/manual_overrides.json data/structured/
git commit -m "data(libraries): manual addresses for 4 unfetchable libraries"
```

---

## Task 5 — Hours for 11 multi-property networks

**Affected:** Trustees of Reservations (3 slugs), Mass Audubon (2), Historic New England, Mass State Parks (2), Wheelock Theatre, NH Phil, Boch Center, Greater Boston Stage.

**Insight:** These either have no single schedule (multi-property) or are event-driven (theaters). Don't fake hours — surface the right UX signal.

### Step 5.1 — Add a `varies` status to hours data

For these specific slugs, write:

```json
{
  "slug": "trustees-of-reservations",
  "status": "varies",
  "regular_hours": null,
  "notes": "Hours vary by property — check trustees.org",
  "source_url": "https://thetrustees.org/"
}
```

### Step 5.2 — Frontend treatment

Update `lib/hours.ts`:

```typescript
export function isClosedOn(attr, iso): boolean {
  if (!attr.hours || attr.hours.status === 'varies') return false;
  // existing logic
}

export function hoursDisplay(attr, iso): { value: string; varies: boolean } | null {
  if (!attr.hours) return null;
  if (attr.hours.status === 'varies') {
    return { value: attr.hours.notes ?? 'Hours vary', varies: true };
  }
  const v = hoursForDate(attr, iso);
  return v ? { value: v, varies: false } : null;
}
```

Card shows: `🕘 Hours vary by location` instead of incorrect "Open today 9–5".

### Step 5.3 — Commit

```bash
git add data/raw/attraction_hours/ web/src/lib/hours.ts web/src/components/AttractionCard.tsx
git commit -m "data+ui(hours): handle multi-property networks with 'varies' status"
```

---

## Task 6 — Complete 46 unmapped libcal passes

**Affected:** Non-BPL LibCal libraries (Cambridge, Brookline, Thayer, Milton) where the manual map `config/platform_pass_ids/libcal.json` doesn't yet cover every pass.

### Step 6.1 — Identify the 46

```bash
python -c "
import json, glob
mapped_libcal = set()
for lib_id, info in json.load(open('config/platform_pass_ids/libcal.json', encoding='utf-8'))['libraries'].items():
    for k in info.get('passes', {}):
        mapped_libcal.add((lib_id, k))

for f in glob.glob('data/raw/libcal/index/*.json'):
    lib_id = f.split('/')[-1].replace('.json','')
    if lib_id == 'bpl': continue
    d = json.load(open(f, encoding='utf-8'))
    for p in d['passes']:
        if p.get('status', '').startswith('failed'): continue
        slug = p.get('slug')
        if (lib_id, slug) not in mapped_libcal:
            print(f'{lib_id:10s} {slug:50s} {p[\"museum_name\"]}')
" | sort | uniq
```

### Step 6.2 — Subagent to suggest canonical slugs

Dispatch a Sonnet subagent: given each unmapped (lib_id, libcal_slug, museum_name) tuple, propose the canonical slug from the existing attraction list. If no clean match exists, propose a new canonical slug.

### Step 6.3 — Human-in-the-loop review

The subagent produces a `_tmp_libcal_proposals.json`. **You review** before merging into `config/platform_pass_ids/libcal.json`. Don't auto-merge — these are 46 decisions that affect canonical data.

### Step 6.4 — Apply + rebuild

After review:

```bash
python scripts/build_attractions_index.py
python scripts/build.py
git add config/platform_pass_ids/libcal.json data/structured/
git commit -m "data(libcal): complete platform_pass_ids mappings (46 entries)"
```

---

## Task 7 — Wire all new data through build pipeline

**Files:**
- `src/malibbene/build/attractions.py` — add `_youth_etc` to `_price_block`, add `description`/`phone` fields.
- `src/malibbene/build/passes.py` — read `data/raw/pass_policies/*.json` and attach `policy`.
- `scripts/build.py` — load new dirs, pass to builders.

### Step 7.1 — Update builders + tests

```python
# in src/malibbene/build/attractions.py:
def _price_block(rec):
    if not rec or rec.get("status") != "ok": return None
    return {
        "adult": rec.get("adult"),
        "child": rec.get("child"),
        "youth": rec.get("youth"),         # NEW
        "senior": rec.get("senior"),
        "student": rec.get("student"),
        "military": rec.get("military"),   # NEW
        "educator": rec.get("educator"),   # NEW
        "family": rec.get("family"),
        "free_under_age": rec.get("free_under_age"),
        "notes": rec.get("notes"),
        "source_url": rec.get("source_url"),
    }
```

Add `description` and `phone` fields to the Attraction dict (read from raw assabet data; phone is already there per `_fetch_log`).

### Step 7.2 — Update Pass builder

```python
# in src/malibbene/build/passes.py:
def build_passes(catalog, policies=None):
    out = []
    for lib_id, lib_entry in catalog.get("libraries", {}).items():
        for slug, p in lib_entry.get("passes", {}).items():
            policy_key = f"{lib_id}_{slug}"
            policy = policies.get(policy_key, {}) if policies else {}
            out.append({
                ...
                "policy": policy if policy.get("status") == "ok" else None,
            })
```

### Step 7.3 — Update existing tests

`tests/test_build_attractions.py` and `tests/test_build_passes.py` — add new fields to fixtures, assert they appear in outputs.

### Step 7.4 — Run

```bash
python scripts/build.py
python -m pytest tests/ -v
```

All ≥114 backend tests still pass + new fields visible in attractions.json + passes.json.

### Step 7.5 — Commit

```bash
git add src/malibbene/build/ scripts/build.py tests/test_build_*.py data/structured/
git commit -m "feat(build): wire policy + price tiers + description/phone through pipeline"
```

---

## Task 8 — Frontend: accurate discount display via policy

**Why:** Replace the misleading `$30 → $15` with policy-aware text.

**Files:**
- `web/src/data/types.ts` — add Policy + youth/military/educator + description/phone
- `web/src/lib/discount-display.ts` — pure helpers
- `web/src/lib/discount-display.test.ts`
- `web/src/components/DiscountLine.tsx` — new component
- `web/src/components/AttractionCard.tsx` — use DiscountLine instead of inline price logic
- `web/src/pages/AttractionDetail.tsx` — same

### Step 8.1 — TS types

```typescript
export interface Policy {
  max_people: number | null;
  max_adults: number | null;
  max_children: number | null;
  eligibility: 'all' | 'adults_only' | 'vehicle' | 'single_ticket' | 'members' | null;
  free_under_age: number | null;
  savings_per_person_usd: number | null;
  notes: string | null;
}

export interface OriginalPrice {
  adult: number | null;
  child: number | null;
  youth: number | null;       // NEW
  senior: number | null;
  student: number | null;
  military: number | null;    // NEW
  educator: number | null;    // NEW
  family: number | null;
  free_under_age: number | null;
  notes: string | null;
  source_url: string | null;
}

export interface Pass {
  // existing...
  policy: Policy | null;
}

export interface Attraction {
  // existing...
  description: string | null;     // NEW
  phone: string | null;            // NEW
}
```

### Step 8.2 — `discount-display.ts`

```typescript
import type { Discount, Policy } from '../data/types';

export interface DiscountDisplay {
  primary: string;       // e.g., "50% off"
  qualifier: string | null;   // e.g., "up to 4 people"
  detail: string | null;       // e.g., "Children under 2 free"
}

export function formatDiscount(d: Discount, policy: Policy | null): DiscountDisplay {
  // primary text from discount class + label
  let primary = d.label || d.class;
  if (d.class === 'free') primary = 'Free';
  if (d.class === 'half') primary = '50% off';

  let qualifier: string | null = null;
  if (policy) {
    if (policy.eligibility === 'vehicle') qualifier = 'per vehicle';
    else if (policy.eligibility === 'adults_only') qualifier = 'adults only';
    else if (policy.eligibility === 'single_ticket') qualifier = '1 ticket';
    else if (policy.eligibility === 'members') qualifier = 'members';
    else if (policy.max_adults && policy.max_children) {
      qualifier = `${policy.max_adults} adults + ${policy.max_children} kids`;
    } else if (policy.max_people) {
      qualifier = `up to ${policy.max_people} people`;
    }
  }

  let detail: string | null = null;
  if (policy?.free_under_age) {
    detail = `Free under ${policy.free_under_age}`;
  } else if (policy?.notes) {
    detail = policy.notes;
  }

  return { primary, qualifier, detail };
}
```

Plus the original-price-times-rate logic only kicks in when we can prove the discount applies to the adult tier uniformly (`eligibility=null` AND no `savings_per_person`). Otherwise display the raw discount label.

### Step 8.3 — `DiscountLine.tsx`

Replaces the inline price block in AttractionCard option rows:

```tsx
<DiscountLine discount={pass.discount} policy={pass.policy} adult={attraction.original_price?.adult ?? null} />
```

Renders:
- For a clean adult-only discount: `$30 → $15` (current behavior)
- For party-cap: `50% off` (bold green, large) + small grey `up to 4 people` below
- For "$5 off each up to 4": `$5 off` + `each, up to 4`
- For free under age: detail `Free under 2`

### Step 8.4 — Card header price line

Update card header to show **all known tiers** when ≥3 are known, instead of just Adult/Child:

```
$30 adult · $25 kids
```

Becomes (when youth is known):

```
$30 adult · $20 youth · $10 kids
```

Just space-separate the known tiers. Drop the "Adult" word when only one is shown (just the number). Cap at 4 tiers visible.

### Step 8.5 — Tests

`web/src/lib/discount-display.test.ts` — covers all 6 combinations:
- free + no policy
- 50% off + max_people 4
- 50% off + adults_only
- $5 off + savings_per_person
- price (e.g., "$5 per person") + max_people
- discount + members eligibility

### Step 8.6 — Commit

```bash
git add web/src/data/types.ts web/src/lib/discount-display.ts web/src/lib/discount-display.test.ts web/src/components/DiscountLine.tsx web/src/components/AttractionCard.tsx
git commit -m "feat(web): policy-aware discount display — accurate for party caps + tiers"
```

---

## Task 9 — Detail page: description, phone, guest lock mode

**Files:**
- `web/src/pages/AttractionDetail.tsx`
- `web/src/components/GuestLockedRow.tsx` (NEW)

### Step 9.1 — Description + phone display

In the existing detail page hero block, add after categories:

```tsx
{attraction.description && (
  <p className="mt-3" style={{ fontSize: 13, color: 'var(--ink-3)', lineHeight: 1.55 }}>
    {attraction.description}
  </p>
)}
{attraction.phone && (
  <p className="mt-2" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
    📞 <a href={`tel:${attraction.phone.replace(/[^\d+]/g,'')}`}>{attraction.phone}</a>
  </p>
)}
```

### Step 9.2 — Guest 🔒 lock mode

Spec §6.4: guests see all theoretical options with lock icon. Currently we hide them.

Add `GuestLockedRow.tsx`:

```tsx
interface Props { pass: Pass; library: Library; onSignInRequest: () => void; }
export function GuestLockedRow({ pass, library, onSignInRequest }: Props) {
  return (
    <button onClick={onSignInRequest} className="flex items-center gap-2 ...">
      <PassTypeLabel type={pass.pass_type} />
      <span>{library.name}</span>
      <span className="ml-auto" style={{ color: 'var(--ink-3)' }}>🔒</span>
      <span style={{ color: 'var(--ink-3)' }}>{pass.discount.label}</span>
    </button>
  );
}
```

Update detail page: when `userCardLibIds` is null AND user is a guest (NOT admin with empty cards — they should see the same thing), render all rows as `<GuestLockedRow>` instead of filtering them out. On click → opens SignInModal.

### Step 9.3 — Commit

```bash
git add web/src/pages/AttractionDetail.tsx web/src/components/GuestLockedRow.tsx
git commit -m "feat(web): detail page description + phone + guest lock-icon mode"
```

---

## Task 10 — Settings page library search

**File:** `web/src/pages/MyPasses.tsx`

### Step 10.1 — Search input + filter logic

At the top of the libraries section, add a SearchBox (existing component). Filter the 59-library list by case-insensitive substring on `name` or `town`.

Also add a "Show only my cards" toggle that filters to libraries where the user already has a card.

### Step 10.2 — Group by network

Optional improvement: group the long list by network (NOBLE / MVLC / Minuteman / etc.) with collapsible headers. Skip if it adds too much complexity for v0.1.

### Step 10.3 — Commit

```bash
git add web/src/pages/MyPasses.tsx
git commit -m "feat(web): library search + my-cards filter on settings page"
```

---

## Task 11 — Frontend component tests

**Why:** Right now we have 49 store/lib tests, 0 component tests. Add basic render + interaction tests for every component.

**Files:** One test file per component, see file structure above.

### Step 11.1 — Set up React Testing Library helpers

`web/src/test-utils.tsx`:

```tsx
import { render } from '@testing-library/react';
import { HeroUIProvider } from '@heroui/react';
import { MemoryRouter } from 'react-router';

export function renderApp(ui: React.ReactElement, { route = '/' } = {}) {
  return render(
    <HeroUIProvider>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </HeroUIProvider>
  );
}
```

### Step 11.2 — Tests, one per component

For each component, cover:
- Default render doesn't throw
- Basic interaction (click, type, focus)
- Conditional state (favorited vs not, valid vs invalid ZIP, etc.)
- Accessibility role/label

Components to cover:
1. `PassTypeLabel` — renders all three types with correct label text
2. `FavoriteButton` — click toggles favorites store; ARIA pressed updates
3. `ZipPill` — typing 5 digits saves; invalid (<5) shows red
4. `SearchBox` — controlled value; × clears
5. `DiscountLine` — all 6 policy/discount combinations render correctly
6. `BookingConfirmModal` — open with pass renders barcode; COPY works (mock clipboard); main CTA opens new tab (mock window.open)
7. `CategoryChips` — All / Favorites / category selection emits onChange
8. `AttractionCard` — guest vs logged-in renders correct state; clicking Book fires onBookPass
9. `Banner` — guest vs admin states; click fires callback

### Step 11.3 — Run + commit

```bash
cd web && pnpm test
```

Target: ≥80 frontend tests passing total (49 existing + ~30 new component tests).

```bash
git add web/src/test-utils.tsx web/src/components/*.test.tsx
git commit -m "test(web): component tests for cards, modals, filters, badges"
```

---

## Task 12 — Final verification + glossary + docs

### Step 12.1 — Full test run

```bash
cd "F:/pj/NorthShore Kids Events"
python -m pytest tests/ -v | tail -5
cd web && pnpm test | tail -5
```

### Step 12.2 — Production build check

```bash
cd web && pnpm run build
```

### Step 12.3 — Update glossary

In `docs/glossary.md`:
- §3 add `policy` as a key new concept
- §4 expand price tiers (youth / military / educator)
- §8 add new state strings: `Hours vary`, `up to 4 people`, `per vehicle`, `adults only`, `1 ticket`, `members`

### Step 12.4 — Update CLAUDE.md

Reflect the new data files under `data/raw/`:
- `attraction_descriptions/`
- `pass_policies/`

And the new build pipeline output fields.

### Step 12.5 — Commit + smoke test

```bash
git add docs/ CLAUDE.md
git commit -m "docs: reflect plan-5 outputs (policy + price tiers + description)"
```

Manual smoke test (dev server):
- ☐ Card prices look right for varied attractions (MOS uniform half, ZNE per-person, parks per-vehicle, etc.)
- ☐ Detail page shows description + phone where available
- ☐ Guest visiting an attraction detail page sees locked rows (🔒)
- ☐ Settings page library list is searchable
- ☐ Trustees / Mass Audubon don't claim "Open today 9-5"; they show "Hours vary"
- ☐ Theme color still matches in dark-mode browser

---

## Verification Summary

After all 12 tasks:

| Artifact | Target |
|---|---|
| Attractions with price (any tier) | 75+/104 (from 54) |
| Attractions with geo | 95+/104 (from 75) |
| Library street addresses | 59/59 (from 55) |
| Hours classified (incl. 'varies') | 104/104 (from 93) |
| Mapped libcal passes | All non-failed mapped (0 unmapped) |
| Per-pass policies extracted | 85%+ of passes with benefits_text |
| New attraction fields | description, phone surfaced on detail page |
| Guest detail mode | lock-icon rows + sign-in prompt |
| Settings page | searchable 59-library list |
| Frontend tests | ≥80 total (≥30 new component tests) |
| All backend tests | 114+ still pass |
| Production build | clean |

After this plan, every gap from plans 1–4 + user feedback rounds is closed.

---

## Open questions to resolve before execution

These should be answered in a fresh session before the agent starts:

1. **Task 6 review process** — 46 libcal manual mappings need human eyes. Confirm you want to review them inline vs trusting the subagent.
2. **Task 2 policy schema** — Are there additional `eligibility` values worth modeling? (e.g., `seniors_free`, `students_get_discount`, etc.)
3. **Task 8 display rules** — Some open product decisions:
   - When discount = "50% off · up to 4 people", do we still show a final dollar amount in green? Or just the discount label?
   - For "$5 off each, up to 4", should we show "save up to $20"?
   - These are UX calls best made when looking at the actual rendered output.

Plan-5 itself is execution-ready — these are tuning decisions, not blockers.
