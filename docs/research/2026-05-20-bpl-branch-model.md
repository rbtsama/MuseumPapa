# BPL Branch Model for Museum Passes

Date: 2026-05-20
Status: research note (informs `libraries.json` / `passes.json` schema)

## Verbatim policy text (from bpl.org/museum-passes/)

- "This pass must be picked up at the branch you made the reservation" (appears repeatedly).
- "Returnable Passes must be picked up and returned (where required) to the branch where they were reserved."
- "Please note the hours of operation for your chosen Boston Public Library pickup location."
- Passes are tagged either "Available at All Locations" or "Available at Select Locations." The latter enumerates a subset of the ~16 branches shown on the catalog page (Central, Brighton, Chinatown, East Boston, Egleston Square, Faneuil, Grove Hall, Jamaica Plain, Lower Mills, Parker Hill, Roslindale, Shaw-Roxbury, South Boston, Uphams Corner, West End, West Roxbury).
- Pass formats: **Returnable** (laminated, branch pickup + return), **Disposable** (e-coupon / promo code / QR / printed-and-keep), **E-Voucher** (emailed code). The bpl.org page explicitly lists "Digital (downloadable via email) passes" for several attractions (e.g., MFA coupon already in `data/raw/pass_coupons/bpl_mfa.json`).

## Actual booking mechanic (from LibCal scraper & endpoint)

`backup/scrape_bpl_availability.py` hits a single endpoint per pass:

```
GET https://bpl.libcal.com/pass/availability/institution
    ?museum=<bpl_pass_id>&date=<YYYY-MM-01>&digital=0&physical=1
```

Docstring lines 7-11 are unambiguous: the returned calendar shows `s-lc-pass-available` iff **at least one location** has the pass. **Inventory is per-branch (each branch holds N copies), but the public availability view is aggregated across all branches that carry the pass.** Branch selection happens inside the booking modal *after* the user picks a date — they then choose from the branches that still have inventory on that date.

For Disposable / E-Voucher passes the "branch" is effectively a fulfillment formality (email arrives the same regardless), but the LibCal UI still asks for one.

## Answers

1. **Per-branch inventory, central calendar.** Each branch stocks its own physical copies; LibCal aggregates the OR across branches for the date-grid.
2. **Yes, branch is picked at reservation time**, from the subset that still has inventory on the chosen date.
3. **Some passes restricted to "Select Locations"** (subset of branches). Most are "All Locations."
4. **For digital/e-coupon passes branch is semantically meaningless** but the LibCal flow still records one (probably for analytics / fulfillment-by-branch).
5. **~16 distinct branches** offer pickup (full list above).

## Recommendation: model C (one Library + branches as pickup locations on Pass)

- **`libraries.json`**: BPL stays a **single entity** (`lib_id: "bpl"`). Add `branches: [{id, name, address?, geo?}]` as a sidecar field (the 16 from the catalog page). Don't promote branches to top-level libraries — they share one card, one eligibility policy, one card_page, one residency rule. Treating each as its own library would 16x-inflate the libraries table, break the "passes.json = (library × attraction) matrix" invariant (BRD §6.1), and force fake duplication of `passes.json` rows.
- **`passes.json` (BPL rows)**: add an optional `available_at_branches: [branch_id, ...] | "all"` field. Default `"all"`; populate the subset for the "Select Locations" passes. For digital/e-voucher passes, `available_at_branches` is ignored by UI (still write `"all"` for uniformity).
- **Availability**: keep storing the aggregated calendar (no need to fan out per-branch unless v0.2 adds "show me which branch has it"). The current scraper output shape (`{benefit_id: {bpl: {date: status}}}`) is correct.
- **UI implication**: NorthShore product targets Wakefield resident with a BPL eCard; she can pick up at any branch and Central is the obvious default. Surfacing branches as filterable adds noise without value at v0.1.

## Other multi-branch libraries with the same shape

Checked `config/library_seeds.json`. Two candidates run their own LibCal instance and almost certainly have the same pattern:

- **Cambridge Public Library** (`cambridge`, `cambridgepl.libcal.com`) — Main + 6 branches (Boudreau, Central Square, Collins, O'Connell, O'Neill, Valente).
- **Brookline Public Library** (`brookline`, `brooklinelibrary.libcal.com`) — Main + Coolidge Corner + Putterham.

For both, recommend model C with the same `branches` sidecar — confirm with a follow-up WebFetch when those libraries' rows are filled in. Assabet network libraries (52 of the 59) are single-building libraries; no branch problem there. Museumkey (Cohasset, Hingham) likewise single-building.

## Action items

- [ ] Add `branches[]` to `libraries.json` BPL row (16 entries; pull addresses + geo via existing geocode pipeline).
- [ ] Add optional `available_at_branches` to `passes.json` schema; populate for the "Select Locations" passes by re-scraping per-pass detail pages (the body lists branches explicitly).
- [ ] Spot-check Cambridge + Brookline catalog pages — if they expose per-pass branch lists, apply same schema.
- [ ] Defer per-branch availability fan-out to v0.2 (only if user requests "which branch has it" filter).
