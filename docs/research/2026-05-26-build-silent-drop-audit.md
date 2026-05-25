# Build Pipeline Silent-Drop Audit + Coupon Fix

**Date:** 2026-05-26
**Trigger:** Operator noticed many passes (e.g. Zoo New England) showed no discount amount.
**Severity:** HIGH — corrupted/missing data was shipping silently; only visible post-delivery.

---

## 1. The bug (root cause)

`build/passes.py` read coupon data from the **abandoned** per-platform directory
`data/raw/<platform>/coupons/<lib>__<rawslug>.json` (double underscore, `extracted`-wrapped,
stale) instead of the **authoritative** re-extraction at
`data/raw/pass_coupons/<lib>_<canonical_slug>.json` (single underscore, canonical slug,
top-level fields). Two compounding mismatches:

1. **Path/shape:** wrong directory, wrong filename separator, wrong JSON shape.
2. **Slug:** the live build keyed by the *raw* catalog slug; `pass_coupons/` is keyed by the
   *canonical* slug (e.g. `bpl__boston-children-s-museum-e-coupon` vs `bpl_boston-childrens-museum`).

### Impact on shipped `passes.json` (1033 passes)
- **197 null coupons** despite real data existing.
- **~585 passes carried a WRONG/stale value** (e.g. `acton/boston-childrens-museum` shipped
  "$5 off" when the real offer is 50% off). Silently-wrong is worse than missing.

---

## 2. Broad audit (was this the only one?)

Two independent audits (build code + structured data) cross-referenced every structured
field against available raw. **Conclusion: the coupon bug is the only large silent drop.**
Everything else that looks "missing" is a genuine source gap, not a drop:

| Apparent gap | Count | Verdict |
|---|---|---|
| passes.coupon = null | 197 | **silent drop — 169 directly recoverable + ~26 via slug alias** |
| passes.residency = unknown | 217 | true gap (never probed: libcal/museumkey + uncovered pairs) |
| passes.availability = {} | 41 | true gap (museumkey by design; a few empty raw) |
| attractions.prices = [] | 25 | true gap (raw status=failed: 403/not_published) |
| attractions.hours missing | 11 | **1 recoverable** (museum-of-african-american-history via `maah` alias) + 10 true gap |
| library card/pickup eligibility unknown | 69 | true gap (no clean raw) |
| library *_source_phrase | 67 | **NOISE** (scraped nav menus / schema.org blobs) |

**Latent footgun:** raw extraction dirs use a different/canonical slug vocabulary than
structured (`mfa`↔`museum-of-fine-arts`, `maah`↔full, `the-butterfly-place`↔`butterfly-place`,
…). Any future slug-keyed merge will silently re-drop these without an alias map.

---

## 3. The fix (commit `e82270a`)

`build_passes` now reads coupon numbers from `data/raw/pass_coupons/` (canonical-slug first,
raw-slug fallback) via `coupons.coupon_from_extract`; generates `summary`; converts blackout
dates absolute→relative `{month,day}`; keeps `pass_form` / residency / rich restrictions from
the legacy extraction (which still has them). **Coupon coverage 81% → 99.8%** (null 197 → 2
genuine no-data).

## 4. Prevention (so this class can't recur silently)

1. **Hard guard** (`coupons.coupon_coverage_gaps`, enforced in `build_passes`): the build
   **raises** if any pass ships an empty coupon while an authoritative `pass_coupons/` file
   (status ok) exists. Tests lock both the merge and the guard.
2. **`_meta.coupon_coverage_pct`** stamped on every build — regressions are visible at a glance.
3. **Deleted `scripts/build.py`** — it was unrunnable (old API) yet held the *correct*
   coupon-loading logic that never ran; its existence implied coupons were read correctly.

## 5. Deferred follow-ups

- **Slug-alias map**: apply consistently across build merges. Would recover the 1 MAAH hours
  field and harden ~5 aliased attractions against future re-drops.
- **Library policy provenance**: re-add `*_source_phrase` only with a real policy-text
  extractor (current raw is nav noise; 117 garbage values removed in `4fefa1b`).
- **Override slug consistency** (`build/passes.py` `pass:{lib}__{rawslug}`): latent — overrides
  authored against canonical slug won't apply. Plan 1 mitigated by emitting `attraction_rawslug`.
