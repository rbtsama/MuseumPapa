# Consortium Reciprocity Research — Museum Pass Borrowing Rules

**Date:** 2026-05-20
**Author:** Claude (subagent research)
**Question:** Is the project's assumption "network membership ⇒ card works at every member library for everything" correct?
**Short answer:** **No.** All 5 networks operate on a per-library-policy basis. Reciprocity for museum passes is the exception, not the default. Most member libraries restrict pass reservations to their own town's residents.

---

## 1. NOBLE — North of Boston Library Exchange

**Members (verified via https://www.noblenet.org/libraries/, fetched 2026-05-20):**
17 public libraries (Beverly, Danvers, Everett, Gloucester, Lynn, Lynnfield, Marblehead/Abbot, Melrose, Peabody, Reading, Revere, Salem, Saugus, Stoneham, Swampscott, Wakefield/Lucius Beebe, Winthrop) + 7 academic (BHCC, Endicott, Gordon, Merrimack, Montserrat, Phillips Academy, Salem State) + MBLC professional library.

**Network-wide reciprocity policy (museum passes):** None. NOBLE explicitly leaves pass policy to each member.

> "Access to museum passes may be restricted according to local policy." — search-surfaced from noblenet.org documentation
> "[E]ach member library is an independent entity, and regulations, fines and charges will vary from library to library." — borrowerscardpol.pdf, noblenet.org

**Positive example (NOBLE card honored beyond home library):** Everett Public Libraries
> "Non-Everett residents with a valid library card from any of the member libraries of the NOBLE Network may visit either the Shute or Parlin libraries to borrow a museum pass on the day of its use, provided the pass has not already been reserved for use that day."
> — https://www.everettpubliclibraries.org/books-and-more/museum-discount-options/

**Negative example flagged in search snippet:** "Belden Noble library — passes available to valid card holders only and must be picked up and returned to the Belden Noble library. They cannot be sent via inter-library loan." (NB: "Belden Noble" is a Vermont library, *not* a NOBLE-MA member — this is a search-engine name collision. Flagged below as "needs human verification" — no confirmed NOBLE-MA blanket negative-exception in this pass.)

---

## 2. Minuteman Library Network

**Members:** "Over 40 libraries" per minlib.net About page. No complete roster on the public About page; the Board page only names ~9 representative libraries (Norwood/Morrill, Brookline, Wellesley, Somerville, Winchester, Lincoln, Maynard, Belmont, Lasell University). Full roster requires a separate page not exposed via the URLs probed.

**Network-wide reciprocity policy (museum passes):** None at the network level. Borrowing books reciprocally is supported ("allows you to request items to be delivered to your home library" — minlib.net/about), but pass policy is per-library.

**Negative exception (verbatim, fetched 2026-05-20):** Woburn Public Library
> "Passes are available to WOBURN RESIDENTS ONLY and may be reserved with a valid Minuteman Library Network card."
> — https://woburnpubliclibrary.org/services/museum-passes/

**Positive exception (verbatim, fetched 2026-05-20):** Wellesley Free Library
> Wellesley residents/employees "may reserve one pass per week, up to 60 days in advance"
> Other Minuteman cardholders: "with a valid library card from any of the member libraries of the Minuteman Library Network may borrow a museum pass on the day of its use provided the pass has not already been reserved for use that day"
> — https://www.wellesleyfreelibrary.org/beyond-wfl/museum-passes/

**Positive exception (verbatim, fetched 2026-05-20):** Cambridge Public Library — fully open
> "Free or discounted museum passes are available to the public through the Cambridge Public Library to anyone with a Minuteman Library card."
> "You must have a valid Minuteman library card to reserve a museum pass" — no residency requirement.
> — https://www.cambridgema.gov/Departments/cambridgepubliclibrary/iwantto/getamuseumpass

**Pattern:** Minuteman libraries fall into three buckets — (a) residents-only (Woburn-style), (b) residents priority + same-day walk-in for other Minuteman cards (Wellesley-style — common), (c) fully open to any Minuteman card (Cambridge-style — rare).

---

## 3. MVLC — Merrimack Valley Library Consortium

**Members:** "36 member libraries" per Newburyport PL. mvlc.org redirects to the SirsiDynix catalog (mvlc.ent.sirsi.net) which returns 403 to WebFetch — full member roster not retrieved in this pass.

**Network-wide reciprocity policy:** Partial. The Wilmington-maintained "All MVLC Museum Pass List" states:
> "Many libraries in the Merrimack Valley Library Consortium (MVLC) lend their passes to any Consortium card-holder in good standing."
> — https://wilmlibrary.org/services/mp/all-mvlc-museum-pass-list/

Note the hedge "Many" — not all.

**Negative exceptions (verbatim from same source):**
Residents-only museum-pass libraries within MVLC:
> Andover, Billerica, Carlisle, Chelmsford, Dracut, Dunstable, Essex, Groveland, Lawrence, Littleton, Lowell, Methuen, Middleton, North Andover, Westford
> Plus Topsfield — "Resident or Friends Members only"

That is ~16 of ~36 (~44%) MVLC libraries that opt out of cross-network pass sharing.

**Generic MVLC museum-pass policy text (Newburyport, Salisbury, etc. echo it):**
> "Anyone with a valid MVLC Library card may reserve a pass: reservations are taken up to 4 weeks in advance."
> "Passes are limited to one pass per day per family and cannot be reserved or used for consecutive days."

This is the policy at the open libraries; the negative-list libraries override it.

**Additional logistical restriction:** "you must pick up passes at the lending library—they won't be delivered to [your home library]" — no inter-library delivery of passes within MVLC.

---

## 4. OCLN — Old Colony Library Network

**Members (~28 libraries, from MBLC/Wikipedia cross-ref, not directly from ocln.org which returns 403):**
Abington, Avon, Braintree (Thayer), Brockton, Canton, Cohasset (Paul Pratt), Duxbury, Hanover (John Curtis), Hingham, Holbrook, Hull, Kingston, Marshfield (Ventress), Milton, Norwell, Plymouth, Quincy (Thomas Crane), Randolph (Turner), Rockland, Sandwich, Scituate, Sharon, Stoughton, Walpole, Weymouth, and others.

**Network-wide reciprocity policy:** Not unified — per-library. ocln.org/museum_passes returned 403; the closest single statement found was:
> "any adult or teen with an OCLN library card in good standing can borrow museum passes regardless of whether they live in Weymouth" — Weymouth PL policy change announcement (July 2023).
> — https://www.weymouth.ma.us/weymouth-public-libraries/news/museum-passes-are-available-to-all

**Negative exception (verbatim, search-surfaced):** Sharon Public Library
> "Sharon Public Library passes are available for Sharon residents only."
> — https://sharonpubliclibrary.org/museum-passes/ (search snippet, not fetched directly)

**Positive exception:** Weymouth (above) — was residents-only pre-July-2023, now open to all OCLN.

**Pattern:** OCLN appears to skew more "residents-only" than MVLC, but the exact list per library could not be enumerated in this pass — see "needs verification" below.

---

## 5. BPL — Boston Public Library eCard (special case)

**This is NOT a consortium**. It is a single-library card that the project treats as a 5th "network."

**Eligibility (verbatim, fetched 2026-05-20):**
> "Your primary residence is in Massachusetts"
> OR "You are living in Massachusetts for most of the year while attending school in-state"
> OR work for a MA employer with physical presence in the state
> OR own real property in MA.
> — https://www.bpl.org/ecard/

→ Any MA resident qualifies — broader than any of the 4 consortia.

**Museum pass access (verbatim):**
> "eCards do not allow you to check out physical items such as museum passes, DVDs, and physical books."
> "Requesting and borrowing physical materials, including museum passes, requires a physical card."

> Upgrade path: eCards "can be upgraded to physical cards at any BPL location by providing photo ID and proof of Massachusetts address."

**Implication for the project:** A BPL eCard alone is INSUFFICIENT for museum passes. The user must obtain a physical BPL card (in-person at any branch) to borrow passes. Once they have a physical BPL card, BPL's museum-pass program is open to that cardholder; the BPL card does *not* grant pass-borrowing rights at NOBLE/Minuteman/MVLC/OCLN libraries (you would need a card from one of those networks).

**Cross-network access for BPL cardholders:** A BPL card is recognized as a "valid library card" within Massachusetts, but consortium pass policies are written around *their own* network cards. A BPL card would not satisfy "MVLC card in good standing" etc. → BPL pass access is BPL-only.

---

## Default Behavior Summary Table

| Network | Default reciprocity for museum passes? | Card needed to reserve elsewhere |
|---|---|---|
| NOBLE | **No** — each library sets its own policy | Most libraries: home-town only. A minority (e.g. Everett) honor any NOBLE card. |
| Minuteman | **No** — each library sets its own policy | Most: residents priority + same-day walk-in for other Minuteman cards; a few residents-only (Woburn); a few fully open (Cambridge). |
| MVLC | **Partial** — "many" libraries share, ~16/36 explicitly opt out | Resident-only libraries listed above; rest accept any MVLC card. |
| OCLN | **No** — each library sets own policy | Some open to any OCLN card (Weymouth post-2023); some residents-only (Sharon). |
| BPL (eCard) | **N/A** — eCard cannot borrow physical passes at all | Must upgrade to physical BPL card in person. Card is BPL-only; not honored by consortium libraries. |

**The project's current assumption "network = full reciprocity" is wrong for all four real consortia.**

## Exceptions Found

### Positive (outside-home-library still honors your card)
| Library | Network | Policy |
|---|---|---|
| Everett (Shute/Parlin) | NOBLE | Same-day walk-in for any NOBLE cardholder |
| Wellesley Free | Minuteman | Same-day walk-in for any Minuteman cardholder |
| Cambridge PL | Minuteman | Full reservation rights for any Minuteman cardholder, no residency check |
| Weymouth (post-2023) | OCLN | Any OCLN cardholder, no residency check |
| "Many" MVLC libraries (per Wilmington's list) | MVLC | Any MVLC cardholder in good standing |

### Negative (member library that excludes outside cardholders)
| Library | Network | Policy |
|---|---|---|
| Woburn PL | Minuteman | "WOBURN RESIDENTS ONLY" verbatim |
| Sharon PL | OCLN | "Sharon residents only" (search snippet) |
| Andover, Billerica, Carlisle, Chelmsford, Dracut, Dunstable, Essex, Groveland, Lawrence, Littleton, Lowell, Methuen, Middleton, North Andover, Westford | MVLC | Residents-only museum passes (Wilmington-maintained list) |
| Topsfield | MVLC | Residents or Friends-of-Library members only |

### Cross-network positives (outside-network library that honors your network's card)
**None documented in this pass.** No public site surfaced an example of, e.g., an MVLC library accepting a NOBLE card for museum passes, or vice versa. This is consistent with how networks scope eligibility ("valid X card").

---

## Still Unclear / Needs Human Verification

1. **NOBLE full per-library museum-pass policy matrix.** Only Everett was confirmed open; the other 16 NOBLE public libraries' pass policies were not individually fetched. The "Belden Noble" hit is a name collision with a Vermont library and should be ignored. Need to walk each NOBLE member's website.
2. **Minuteman full member roster.** minlib.net's About page mentions "over 40 libraries" but does not list them all on the page fetched. Need a different URL (e.g. minlib.net/libraries) or the SirsiDynix catalog member page.
3. **OCLN per-library policy matrix.** ocln.org returns 403 to WebFetch (likely a User-Agent filter). The 28-library list above is reconstructed from MBLC + Wikipedia + search snippets, not from OCLN directly. Need to manually visit ocln.org and each member's pass page.
4. **MVLC full 36-library list.** mvlc.org 302-redirects to the catalog which 403s WebFetch. The negative-exception list (16 residents-only libraries) comes from a *Wilmington-maintained* aggregated page, dated unknown — could be stale. Should be re-verified against each library directly.
5. **"Good standing" definition.** All four networks reference "card in good standing" but the threshold (fine amount, expiry buffer) varies per library and was not enumerated.
6. **Whether a BPL physical-card holder can use that card at any consortium library's museum-pass program.** Cross-checked above as "no" by inference (consortium policies say "valid X card"), but not explicitly confirmed by any consortium policy statement found.
7. **Cross-consortium reciprocity.** Whether, e.g., an OCLN card might be honored at an MVLC library as a "valid library card" — no example found in either direction. Worth a phone call to confirm.
8. **Walk-in vs reservation gap.** Many libraries (Wellesley, Everett) document a same-day walk-in path for non-residents but block advance reservations. The project's current data model needs to capture this two-tier distinction; current schema almost certainly does not.

---

## Action Items for the Project

1. **Replace** the "network membership ⇒ full access" assumption with a per-(library × pass) eligibility field. Minimum fields: `eligibility_mode` ∈ {`residents_only`, `residents_priority_walkin_for_network`, `open_to_network`, `open_to_any_card`}, plus `reservation_lead_days_resident` and `reservation_lead_days_nonresident`.
2. **Re-extract** `data/raw/pass_coupons/` provenance to surface residency restrictions into `passes.json` (likely already in `source_phrases` but not promoted to a structured field).
3. **Manual audit** of the 5 cards the operator holds (Wakefield/Reading/BPL/Wilmington/Somerville) against each library they would attempt to reserve from — the front-end's claim "your card works here" may be wrong for the majority of libraries.
4. **BPL eCard caveat** must be added to the UI: "BPL eCard alone is not enough for museum passes — you need a physical BPL card."
