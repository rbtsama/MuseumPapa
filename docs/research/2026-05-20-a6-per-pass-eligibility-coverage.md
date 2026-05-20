# A6: Per-Pass Eligibility Coverage (4 libs × 5 passes)

**Date**: 2026-05-20
**Method**: Read verbatim `raw` benefits text from `data/raw/pass_coupons/<lib>_<attr>.json` (subagent-extracted with `source_phrases` provenance, traceable back to library HTML at `assabetinteractive.com` / `bpl.libcal.com`). Cross-referenced `data/raw/assabet/index/<lib>.json` (`benefits_text` field) and `data/raw/policies/<lib>.txt` (library-level policy) for ground truth. **Did not** rely on `data/structured/*.json`.

## Library default policies (`config/library_seeds.json` + `data/raw/policies/`)

| Lib   | Network | Library-level default |
|-------|---------|-----------------------|
| Andover    | MVLC  | unknown (seed) — implicitly MVLC card |
| Wilmington | MVLC  | `network_only` — MVLC card required |
| Wakefield  | NOBLE | `open_ma_resident` — two-tier (resident vs walk-in) |
| BPL        | BPL   | `open_ma_resident` — any MA resident with eCard |

Classifications:
- **inherits**: pass text contains no residency/eligibility text beyond library default
- **stricter**: pass text adds a residency restriction tighter than library default
- **looser**: pass text widens eligibility (e.g. "any MA library card")
- **attraction-side**: pass text mentions a residency rule, but the rule originates at the *attraction* (e.g. "MA resident required to use HMSC pass", "Salem residents free at PEM") — not a library-imposed restriction

### Andover (MVLC)
| Pass | Verbatim eligibility phrase | Class |
|---|---|---|
| MA State Parks (DCR) | "Only Andover residents may reserve and use this pass." | **stricter** |
| MFA | (none — library default) | inherits |
| Museum of Science | (none) | inherits |
| ISG Museum | (none) | inherits |
| Trustees of Reservations | (none) | inherits |
| Zoo New England | (none) | inherits |

Andover: **1/5 stricter** (state parks only).

### Wilmington (MVLC, network_only)
| Pass | Verbatim eligibility phrase | Class |
|---|---|---|
| MA State Parks | (none) | inherits |
| MFA | "supported by Wilmington Council for the Arts" (funding, not restriction) | inherits |
| Museum of Science | "Funded by the Wilmington Community Fund" (funding, not restriction) | inherits |
| New England Aquarium | (none) | inherits |
| ISG Museum | "supported by Wilmington Council for the Arts" (funding) | inherits |

Wilmington: **0/5 stricter, 0/5 looser**. Funding attributions are common but not eligibility restrictions.

### Wakefield (NOBLE)
| Pass | Verbatim eligibility phrase | Class |
|---|---|---|
| MA State Parks | (none) | inherits |
| MFA | (none) | inherits |
| Museum of Science | (none) | inherits |
| New England Aquarium | (none — but seasonal weekdays-only restriction captured in `restrictions`) | inherits |
| Peabody Essex Museum | (none) | inherits |

Wakefield: **0/5**.

### BPL (LibCal)
| Pass | Verbatim eligibility phrase | Class |
|---|---|---|
| MA State Parks | "limited to one booking per month per person" (behavioral, not residency) | inherits |
| MFA | (none) | inherits |
| Museum of Science | (none — "free thanks to Lowell Institute" is funding) | inherits |
| ISG Museum | (none) | inherits |
| Harvard Museums | "pick up at the branch you made the reservation" (logistics, not residency) | inherits |

BPL: **0/5**. The BPL "select locations" mechanic is branch-pickup logistics, not eligibility.

## Summary

| Metric | Count | Rate |
|---|---|---|
| Total passes sampled | 20 | 100% |
| `pass_specific_stricter` (residency tighter than lib default) | 1 | **5%** |
| `pass_specific_looser` | 0 | 0% |
| `inherits_library` | 19 | 95% |
| (Sidebar) Behavioral/logistics restrictions (`one booking/month`, `weekdays only`, `branch pickup`) | 3 | 15% — already covered by `restrictions` + `pass_type` |
| (Sidebar) Attraction-side residency in text ("must be MA resident", "Salem residents free") | observed in HMSC across many libs, PEM peabody/billerica entries, JFK | — — out-of-band |

## Was Andover state-parks representative or exceptional?

**Exceptional, not representative — but a real pattern when it occurs.** A wider scan via grep across all 1008 pass_coupons (sample shown in research session) reveals the dominant case for pass-specific stricter residency is:

- **Town-only libraries that broadcast the restriction across ALL their passes** (e.g. Needham — "FOR NEEDHAM RESIDENTS ONLY" appears on ~all 18 Needham passes). For these libraries, the per-pass text is just re-asserting the library default, not creating per-pass variation.
- **Town-funded special passes inside an otherwise-network-open library** (e.g. Andover state-parks pass funded by Andover town parks dept). This is the genuine per-pass exception class. Estimated <5% of cells across all 59 libraries × ~25 attractions.

## Recommendation for B-phase crawler scope

**Do NOT make per-pass eligibility a first-class extraction target.** Instead:

1. **Library-level eligibility (`Library.non_resident_policy`)** stays the authoritative default — already collected via `sources/policies.py`.
2. **Per-pass override** is a **rare patch field** (`Pass.eligibility_override`), nullable, populated only when the pass benefits_text contains an explicit residency phrase that disagrees with the library default. Detection rule:
   - regex on `benefits_text` / `raw`: `\b(only|exclusively|must be|reserved for)\b.{0,40}(<lib_town>|<network> card|resident)`
   - exclude phrases starting with "supported by" / "funded by" / "thanks to" (funding, not restriction)
   - exclude attraction-side rules ("MA resident", "<attraction-town> resident") — those belong to attraction metadata
3. **Manual audit overrides** (`config/manual_overrides.json`) catch the remaining tail. The expected universe is ~50 (library × pass) cells out of ~1008, manageable by hand.
4. **Behavioral restrictions** (`one booking/month`, `weekdays_only`, `branch pickup`) keep going into `Pass.restrictions` / `Pass.pass_type` as today — they are well-covered.

Coverage cost-benefit: building a full per-pass extractor for the 5% case would 5x the LLM extraction prompt size with no marginal user-facing accuracy gain over the regex + manual-override approach. Recommend **regex-flag + manual-audit** for B-phase.
