# Coupon Shape Diversity — `data/raw/pass_coupons/` (n=1026)

Date: 2026-05-20
Source: `F:\pj\MuseumPapa\data\raw\pass_coupons\*.json` (1026 files)
Method: full-corpus distribution scan (PowerShell ConvertFrom-Json over every file) plus a strategic 40-file deep read covering all four `capacity.kind` values, multi-audience cases, all five `form` values, and every triggered `restrictions.*` flag.

---

## 1. Full-corpus distribution (ground truth, not sample)

### capacity.kind  — current enum is complete (4 values, all attested)
| value | count | %    |
|-------|-------|------|
| people      | 849 | 82.7% |
| unspecified | 68  | 6.6%  |
| vehicle     | 59  | 5.7%  |
| ticket      | 50  | 4.9%  |

`vehicle` is dominated by MA DCR State Parks (one row per library). `ticket` is dominated by ferry passes (Boston Harbor Islands) and JFK Library. `unspecified` is the trash bin: typically Trustees-of-Reservations (any number of properties), BPL passes whose `raw` is just marketing copy, and Hale Education.

### audience labels — closed vocabulary, 7 values only
| value | count |
|-------|-------|
| Everyone      | 653 |
| Child         | 521 |
| Adult         | 342 |
| Youth         | 64  |
| Vehicle       | 19  |
| Single ticket | 11  |
| Senior        | 2   |

No "Veteran", "Military", "Student", "Educator", "Family", "Household" labels in the audience field — even when `raw` mentions "Adult/Senior" or "Adults/Seniors/College Students" together (see `belmont_orchard-house.json`), the extractor collapses them into `Adult`. **The closed enum hides real-world fan-out.**

### form values — current enum is complete (5 values, all attested)
| value | count |
|-------|-------|
| free             | 577 |
| per-person-price | 487 |
| percent-off      | 438 |
| discount         | 80  |
| dollar-off       | 30  |

`discount` is the catch-all for "we know there is a benefit but no quantified value" — heavily concentrated in BPL passes whose `raw` is marketing prose and Trustees-of-Reservations ("family membership admission price"). Most are not actionable for the UI summary.

### restrictions — frequency
| flag | count |
|------|-------|
| seasonal (string)      | 40 |
| blackout_dates (≥1)    | 29 |
| weekdays_only (true)   | 4  |
| reservation_required   | **0** (the boolean is in the schema but is **never set to true** — extractor only emits `source_phrases.restrictions.reservation_required` text, not the flag) |

### multi-audience rows
490 files (47.8%) have ≥2 `audience_policies` entries. The common pattern is `[Adult, Child]` or `[Adult, Youth, Child]` with the youngest tier on `form: free`.

---

## 2. Surprising shapes the current schema does not model cleanly

### 2.1 BOGO / "2-for-1" gets squashed into `percent-off: 50`
- `lawrence_wheelock-family-theatre.json` → `"buy one get one free"` → `percent-off: 50`
- `lynn_boston-harbor-island-ferry.json` → `"Buy one ticket, get one ticket free (BOGO=50% off)"` → `percent-off: 50`
- `maynard_boston-harbor-island-ferry.json` → `"2-for-1 rate (50% off)"` → `percent-off: 50`
- `wilmington_boston-harbor-island-ferry.json` → `"2-for-1 ferry fees"` → `percent-off: 50`

Mathematically equivalent, but the constraint is different: BOGO requires **pairing** — a single adult cannot benefit. The UI summary "50% off" lies for solo visitors. Only 4 files, but they all involve high-traffic attractions (Harbor Islands).

### 2.2 "Family pass / household" carries hidden cardinality assumptions
- `danvers_north-shore-childrens-museum.json`: `"50% off ... for a family of five"` → encoded as `capacity.kind: people, n: 5`. Loses the semantic of "must be one family".
- `lincoln_historic-new-england.json`: `"two adults and anyone under the age of 18 living in the same household"` → encoded as `Adult count=2 free + Child age<=17 free, capacity.kind: unspecified`. The "same household" constraint disappears.
- `haverhill_seacoast-science-center.json`: `"2 adults and up to 4 children in their household"` → `capacity.kind: people, n: null`. **`n: null` for a `people` kind is invalid per the implicit enum invariant** — happens when each audience has its own count but no overall total was extracted.
- `lynn_the-childrens-piazza.json`: `"50% off regular admission to one household/immediate family only. (Weekdays only.)"` → `capacity.kind: unspecified` (lost the household-once constraint).

A "household" / "family pass" concept is real but invisible in the structured form. ~28 files reference it.

### 2.3 `capacity.n: null` is overloaded
- For `vehicle`: always `n: null` (correct — one vehicle).
- For `unspecified`: always `n: null` (correct — unknown).
- For `people`: usually a number, but `haverhill_seacoast-science-center.json` has `kind=people, n=null` because the per-audience counts (`2 adults` + `up to 4 children`) sum to 6 but no overall cap was stated. Downstream code that does `pass.capacity.n` for the "admits up to N" UI summary will mis-render this.

### 2.4 `dollar-off` is sometimes really a `floor price` on top of variable rack rates
- `billerica_isabella-stewart-gardner-museum.json`: `"$5.00 off general admission"` for an attraction with adult $22 / senior $20 / student $15 / under-18 free → the "$5 off" only applies to paying-age visitors, and the regular price is itself audience-tiered. The schema flattens this to one row `Everyone: dollar-off=5`. Combined with the attraction having a `price.adult/senior/student/youth` block, the consuming UI must do a cross-join to know who actually benefits.

### 2.5 `restrictions.reservation_required` boolean is dead
Despite being in every file's schema, it is **never `true`** in 1026 files. The information lives only in `source_phrases.restrictions.reservation_required` as free text (e.g. `"Advanced ticket purchase is required"`, `"please place a reservation"`, `"call to reserve"`, `"must be reserved through the library's online catalog"`). The plan-9 doc claims reservation is a `restrictions` field — in practice, downstream consumers must do substring lookup in `source_phrases` or re-derive it.

### 2.6 `weekdays_only` is correct but `seasonal` is freeform
`seasonal` values seen include: `"Sep-May"`, `"May-Oct"`, `"Jun-Aug"`, `"Jun-Oct"`, `"late May to early October"`, `"May 15 - June 14"`. **No consistent format**. Downstream date logic must accept both compact (`"Sep-May"`) and prose forms. Range-wrap (`"Sep-May"` crosses a year boundary) is not flagged.

### 2.7 Blackout dates are sometimes a synthetic explosion
- `andover_salem-witch-museum.json` "Pass is NOT valid in October" → expanded into 31 individual ISO dates.
- `braintree_new-england-aquarium.json` "not offered during June, July, and August" → expanded into 92 individual ISO dates **and** `seasonal: "Sep-May"` is set.

The "blackout expansion" is generally helpful for UI calendars but: (a) the year is hardcoded `2026` (will silently rot in 2027), (b) the redundancy with `seasonal` means two sources of truth that can disagree.

### 2.8 Multi-benefit passes don't exist in the data model
Despite 42 files whose `raw` text mentions BOTH "parking" and "admission", **every single one** uses the words to *disclaim* parking ("Pass is not applicable towards discounts on shopping, parking, dining..."). There are no real "admission + parking" or "admission + gift shop" bundled benefits modeled. Parking-only benefits live in a separate row keyed to `ma-state-parks` / `massachusetts-state-parks-...`. **A coupon = one benefit** is empirically true. (One conceptual exception: `acton_the-trustees-of-the-reservations.json` admits to ~120 properties — but it's still one benefit-form, applied uniformly across the property network.)

### 2.9 Edge cases worth flagging
- `bpl_american-rep-theater.json`, `bpl_boch-center.json` and similar BPL entries have `source_phrases: {}` — the LLM extracted `form: "discount"` from nothing more than the library hosting a pass. **`status` is `"ok"` but the data is "unknown unknown".** ~80 files in this bucket.
- `acton_john-f-kennedy-library-and-museum.json`: `audience: "Single ticket"` is an artifact label — not a person type but a quantity hint. Only 11 files use it. Should probably collapse to `Everyone` with `count: 1`.
- `acton_zoo-new-england.json`: three-audience structure where the third row (`Child under 2`) is a *subset* of the second row (`Child` at $6) — implicit override semantics, not made explicit. The UI must know that the youngest tier "wins".
- "Adults must be accompanied by at least one child 12 or younger" (`billerica_davis-farmland.json`) — an admission *eligibility* constraint that has no field; survives only in `raw`.

---

## 3. Proposed minimum viable schema (covers ≥99% of observed cases)

```jsonc
{
  "library_id": "string",
  "attraction_slug": "string",
  "status": "ok | failed:<reason>",
  "raw": "string",                              // full source text — keep!

  "capacity": {
    "kind": "people | vehicle | ticket | unspecified",
    "n":    "int | null",                       // null is legal for vehicle/unspecified AND for people-with-only-per-audience-counts
    "unit_note": "string | null"                // NEW: free text for 'family of 5', 'household', 'carload', etc. — preserves semantic the enum loses
  },

  "audience_policies": [{
    "audience":  "Everyone | Adult | Youth | Child | Senior | Vehicle | Single ticket",
    "age_range": { "min": "int|null", "max": "int|null" } | null,
    "count":     "int | null",
    "form":      "free | percent-off | dollar-off | per-person-price | discount | bogo",  // NEW: bogo (only 4 cases but semantically distinct)
    "value":     "number | null",
    "is_override": "bool"                        // NEW: true if this row overrides a broader row above (e.g. 'Child under 2 free' inside a 'Child $6' world)
  }],

  "restrictions": {
    "blackout_dates":         ["YYYY-MM-DD"],    // keep, but tag the source year explicitly so 2027 rebuilds don't silently use 2026 dates
    "blackout_year":          "int | null",      // NEW: year the expansion is valid for
    "weekdays_only":          "bool",
    "seasonal":               "string | null",   // remain freeform but document allowed shapes
    "reservation_required":   "bool",            // ACTUALLY POPULATE THIS from source_phrases extraction
    "household_constraint":   "bool",            // NEW: 'one household only', 'same household', 'family pass' — 28 files
    "advance_purchase":       "bool",            // NEW: 'must purchase tickets in advance' (often co-occurs with reservation_required but not identical)
    "notes":                  "string | null"    // free-form remainders (e.g. 'adult must accompany child', 'last entry 20 min before close')
  },

  "source_phrases": { /* unchanged — provenance is gold */ }
}
```

### Deliberately NOT in the schema
- **Multi-benefit composition (admission + parking + giftshop)**: not present in the data; introducing it now would be over-engineering. If/when v0.2 surfaces a real example, add a `linked_passes: [pass_id]` field instead of nesting.
- **Per-form-specific value shapes** (e.g. typed unions for `percent-off`/`dollar-off`/`bogo`): the flat `form + value` pair handles all observed cases; type discipline can be moved into TypeScript on the consuming side.
- **Eligibility predicates** ("adult must accompany child"): only 1 example; relegate to `restrictions.notes` for now.

---

## 4. Anti-patterns the consuming UI should defend against

1. **`form: "discount"` with `value: null`** (80 files) — there is no number to display. The "summary" string should fall back to `"discount available — see details"` rather than rendering `"null% off"`.
2. **`capacity.kind: people, n: null`** (rare but real) — sum the per-audience `count`s as the displayed cap.
3. **`blackout_dates` and `seasonal` disagreeing** — seasonal is the canonical date logic; blackout_dates is the rendered calendar. If they disagree, prefer the more restrictive.
4. **`Single ticket` audience** — render as "1 admission" not as a person tier.
5. **`source_phrases.restrictions.reservation_required` non-empty but the boolean is `false`** — trust the string, set the boolean true at build time.
