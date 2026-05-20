# Library Eligibility — Sample Research (10 libraries)

**Date:** 2026-05-20
**Researcher:** Claude (Opus 4.7) via WebFetch + WebSearch
**Scope:** Verify ground truth for two distinct eligibility dimensions:
1. **Card application** — who can register for a card
2. **Pass pickup** — when redeeming a museum pass with a valid card, is residency re-checked?

All quotes are verbatim from the library's own pages (or, where the page was 403/404, from cached WebSearch result blurbs and explicitly marked as such). When the page **does not state** a rule, that is recorded as "not stated on this page" — never inferred.

---

## Summary Table

| # | Library | Network | Card Application | Pass Pickup | Confidence | Notes |
|---|---|---|---|---|---|---|
| 1 | Wakefield (Lucius Beebe) | NOBLE | **anyone with ID + address proof** (no MA-residency wording) | **non-Wakefield residents: same-day walk-in only** (no advance reserve) | High | Pass dimension materially differs from card dimension |
| 2 | Reading | NOBLE | residency proof required (MA driver's license etc.), but hometown cards welcome | not stated on the page that loaded | Med | Reading PL pass-policy page returned generic text only |
| 3 | Acton (Memorial) | Minuteman | **MA resident OR works in Acton** (4+) | **any valid Minuteman card** + must present the card used to reserve | High | Card-dim ≠ pickup-dim — different scopes |
| 4 | Lexington (Cary Memorial) | Minuteman | Minuteman network policy (general MA-ID address-proof) | **"living or working in Lexington" only** (1/day) | High | **Strict pickup restriction even though card is open** |
| 5 | Wilmington (Memorial) | MVLC | **Wilmington residents only** (photo + Wilmington address proof) | "patrons with an MVLC library card in good standing" | High | Card-dim is town-only, pickup-dim is network-wide — opposite of normal pattern |
| 6 | Andover (Memorial Hall) | MVLC | Andover residents/owners/employees/students; other MA may use hometown card or apply for MVLC card | per-pass restrictions exist (state-park passes Andover-only); general pass page returned 403 | Med | Per-pass residency rules confirmed by search snippet, not direct quote |
| 7 | Braintree (Thayer) | OCLN | photo ID + address proof (residency not explicitly stated as Braintree-only on the page text retrieved) | not stated on the page that loaded | Low | Both pages truncated/403; needs revisit |
| 8 | Milton | OCLN | not retrievable (policies are PDFs) | LibCal passes page: not stated on this page | Low | Milton seems silent — likely permissive but unverified |
| 9 | Boston Public Library (BPL) | BPL | "live, own property, or work in MA"; students living in MA; **physical card requires in-person ID + MA residency proof** | "active **physical** library card" (eCards explicitly cannot reserve); 1/day; library card required at pickup | High | Cleanest two-dimension example: eCard ≠ physical card for pass purposes |
| 10 | Cohasset (Paul Pratt) | OCLN | **"available free of charge to all"** — explicitly accepts out-of-state with a "local address and phone" | "Museum passes are available for Cohasset library card holders" | High | **Card-dim is the most open of any library sampled**; pickup-dim narrows to "Cohasset cardholder" |

---

## 1. Wakefield — Lucius Beebe Memorial Library (NOBLE)

**Card page** (`https://wakefieldlibrary.org/get-a-card/`):
> "Anyone is eligible for a library card with valid identification and proof of current address (e.g. a driver's license and utility bill)."
> "Valid cards from other NOBLE libraries are accepted in Wakefield."
> "Children of any age can apply for their own library card. A parent or guardian must sign for any child under the age of 16."

**Museum pass policy** (from `wakefieldlibrary.org/policies/`):
> "The library accepts reservations for museum passes from registered Wakefield residents and institutions."
> "Registered non-residents may borrow museum passes on a same-day walk-in basis."

**Classification:**
- Card dim: `none` (no residency requirement — anyone with ID/address)
- Pass-pickup dim: **two-tier** — `town_resident` for advance reservation, `network`/`none` for same-day walk-in
- Confidence: **High**
- **Does not fit current enum** — "same-day walk-in only for non-residents" is a third state.

---

## 2. Reading — Reading Public Library (NOBLE)

**Card page** (`https://www.readingpl.org/services/get-a-library-card/`):
> "Stop by the Borrower Services desk to present identification and proof of residency."
> "Acceptable forms of ID: Massachusetts driver's license with current address, Checkbook with current address and photo ID, Recent mail with current address and photo ID, Student ID and identification with photo ID"
> "If you aren't a resident of Reading, you can still use your hometown card at the Reading Public Library."

**Museum-pass page** (`readingpl.org/museum-passes/`): generic text only.
> "One pass per family per day and two passes per family per week during school vacation weeks. Most passes can only be booked once per calendar month."
> Pass pickup residency: **not stated on this page.**

**Classification:**
- Card dim: `ma_resident` (proof of residency required, MA-ID accepted; out-of-Reading hometown cards welcomed but applying requires proof)
- Pass dim: `unknown` (not stated)
- Confidence: **Medium**

---

## 3. Acton — Acton Memorial Library (Minuteman)

**Card page** (`actonmemoriallibrary.org/services/library-cards/`):
> "Library cards are available to anyone 4 years and older who lives in Massachusetts or works in Acton."
> "Valid name and address identification are required. AML accepts a current, valid Massachusetts Driver's license or Massachusetts State ID card with current address."
> "a Post Office Box or business address is not sufficient- a current address is required."

**Museum-pass page** (`actonmemoriallibrary.org/services/museum-passes/`):
> "Acton's passes may be reserved by anyone 14 years or older with a valid Minuteman Library Network card."
> "The library card that was used to make the reservation must be presented at the Circulation Desk when the pass is picked up."

**Classification:**
- Card dim: `ma_resident` (with "works in Acton" carve-out)
- Pass dim: `network_only` (Minuteman card)
- Confidence: **High**
- Two dimensions clearly diverge — card requires MA residency, pass redemption only requires a network card.

---

## 4. Lexington — Cary Memorial Library (Minuteman)

**Card page** (`carylibrary.org/library-cards`):
> "For Adults and Young Adults (ages 13 and up)"
> "bring a piece of identification with your name and current address to one of our circulation desks"
> "For more information about identification requirements, see the Minuteman Library Network's Library Card Registration Policy"
> "You may register online to get a temporary Minuteman library card, valid for 6 months" but "You must convert your online account to a full library account before borrowing materials"

**Museum-pass page** (`carylibrary.org/museum-passes`):
> "Patrons living or working in Lexington with a valid library card can reserve one pass per day."
> "Coupon/Returnable Passes: Must be picked up at the Adult Service Desk at Cary Library."

**Classification:**
- Card dim: defers to Minuteman network policy (typically MA-resident or works-in-network)
- Pass dim: **`town_resident`** (live OR work in Lexington) — **stricter than card dim**
- Confidence: **High**
- **Surprise:** The card itself is network-wide but the museum-pass pickup is town-only. This is the inverse of what most people would expect.

---

## 5. Wilmington — Wilmington Memorial Library (MVLC)

**Card page** (from `wilmlibrary.org/services/` summary):
> "Wilmington residents are eligible to sign up for a free library card. A document with a picture ID and proof of residency is required."

(Note: the canonical card-policy page at `/about/library-cards/` returned only a docx download link with no inline text. The above quote is the page's summary excerpt.)

**Museum-pass page** (`wilmlibrary.org/services/mp/`):
> "Discount passes to Boston area museums and parks are funded by local organizations and may be borrowed by patrons with an MVLC library card in good standing."

**Classification:**
- Card dim: `town_resident` (Wilmington only)
- Pass dim: `network_only` (any MVLC card — explicitly broader than Wilmington)
- Confidence: **High**
- **Surprise:** Card is town-restricted, but anyone with any MVLC card can borrow passes. Opposite of Lexington (which is open card / town-only passes). This proves the two dimensions are genuinely independent and can move in either direction.

---

## 6. Andover — Memorial Hall Library (MVLC)

**Card eligibility** (from WebSearch snippet of `mhl.org/borrow/on-the-shelves/library-cards-and-borrowing-items` — direct fetch returned 403):
> "All Andover residents, property owners, Town of Andover municipal employees, and Andover public school teachers and students are eligible to get a Memorial Hall Library card."
> "Residents of other cities and towns in Massachusetts may use their hometown library card in the system or apply for a Merrimack Valley Library Consortium (MVLC) card online or in person with appropriate identification."

**Museum-pass policy** (from WebSearch snippet — direct fetch returned 403):
> "For certain state park passes, only Andover residents may reserve and use those passes."

**Classification:**
- Card dim: `town_resident` for full card, with MVLC fallback for other MA residents
- Pass dim: **per-pass — most are network-open, but state-park passes are Andover-only**
- Confidence: **Medium** (search-snippet, not first-party fetch)
- **Does not fit current enum** — restrictions are **per-pass, not per-library**. Has implications for `passes.json` (the restriction belongs on the (library × attraction) cell, not on `library.eligibility`).

---

## 7. Braintree — Thayer Public Library (OCLN)

**Card page** (from WebSearch snippet of `thayerpubliclibrary.org/get-a-library-card/` — direct fetch was truncated):
> "For ages 16+, photo identification (such as a driver's license) and proof of current address (such as vehicle registration or a postmarked envelope addressed to the applicant) are required to obtain a library card."

The cited language does **not** specify Braintree-only or MA-only.

**Pass policy:** not stated on any retrievable page. Booking happens via `thayerpubliclibrary.libcal.com/passes` but the policy block is not present there.

**Classification:**
- Card dim: `unknown` (likely town/MA but page doesn't make it explicit)
- Pass dim: `unknown`
- Confidence: **Low** — needs in-person or phone follow-up.

---

## 8. Milton — Milton Public Library (OCLN)

**Card page:** Policies are linked as PDFs only; no inline text retrievable.

**Pass page** (`miltonlibrary.libcal.com/passes`): only contains pass-specific pickup instructions:
> "The pass is a physical coupon and you need to pick it up at the Milton Public Library before going to the museum. PLEASE BRING YOUR CONFIRMATION EMAIL TO THE MPL TO PICK UP YOUR PASS BEFORE GOING TO THE MUSEUM."

No residency or ID-check policy stated on either retrievable page.

**Classification:**
- Card dim: `unknown`
- Pass dim: `unknown` (no residency restriction stated — probably `none` for pickup but unverified)
- Confidence: **Low**

---

## 9. Boston Public Library (BPL)

**Card page** (`bpl.org/get-a-library-card/`):
> "If you live, own property, or work in Massachusetts, you can get a BPL card."
> "Students who live here while attending school are also eligible."
> "Come with picture ID and proof of Massachusetts residency, which can be either a physical document or an official document available on an electronic device."
> "A Massachusetts driver's license or ID card satisfies both requirements."
> "If you are a short-term resident staying in Massachusetts you are not eligible for an eCard."

**eCard page** (`bpl.org/ecard/`):
> "eCards are available to anyone who lives, resides part-time to attend school, owns property, or works in Massachusetts."
> "eCards do not allow you to check out physical items such as museum passes, DVDs, and physical books."
> "Requesting and borrowing physical materials, including museum passes, requires a physical card."

**Pass page** (`bpl.org/museum-passes/`):
> "You need an active physical library card to reserve a pass. [You cannot use an eCard to reserve a pass]"
> "To reserve museum passes, upgrade your eCard at [any BPL location] by bringing a photo ID and proof of your Massachusetts residency."
> "You will need to bring your library card to pick up both types of passes."
> "Returnable passes have to be picked up the day they are reserved for (or on Friday for a weekend pass)."
> "You may reserve one pass per museum per thirty-day period. Patrons may only book one pass per day."

**Classification:**
- Card dim: `ma_resident` (physical card requires MA residency proof in person)
- Pass dim: same — **but with the extra "physical card required" gate** that effectively forces in-person residency verification before any pass use
- Confidence: **High**
- **Does not fit current enum cleanly** — BPL has a hybrid (eCard with MA-residency but no pass access; physical card with same residency proof + pass access). The eligibility-for-card and eligibility-for-pass are gated by *card type*, not by re-checking residency at pickup.

---

## 10. Cohasset — Paul Pratt Memorial Library (OCLN, MuseumKey)

**Card page** (`cohassetlibrary.org/189/Get-a-Library-Card` and circulation policy):
> "Anyone may use the materials or reference services inside the library. In order to borrow materials you must have a valid library card."
> "Library cards are available free of charge to all adults and children."
> "Library cards are available free of charge to all."
> "Present your driver's license or another form of identification that includes your mailing address."
> "Your library card is valid for use at any Old Colony Library Network (OCLN) member library."
> "Out-of-State Residents: All that is required is a local address and phone number as well as your driver's license or other form of picture identification."

**Pass policy** (cited inside circulation policy):
> "Museum passes are available for Cohasset library card holders."

**Classification:**
- Card dim: **`none`** — explicitly available to anyone including out-of-state with only a local address
- Pass dim: `town_resident` interpreted as *Cohasset-card-holder* (i.e., must hold a Cohasset-issued card, not just any OCLN card)
- Confidence: **High**
- **Surprise:** Cohasset is the most permissive on cards but restricts passes to its own cardholders (not OCLN-wide). This is the opposite split from Acton/Wakefield.

---

## Open Questions / Surprises

### Surprises that contradict the 5-value enum `{ma_resident, town_resident, network_only, none, unknown}`

1. **Two dimensions are genuinely independent and move in BOTH directions.** Examples:
   - **Lexington:** card = network-open, pass = town-only
   - **Wilmington:** card = town-only, pass = network-open
   - **Cohasset:** card = none (out-of-state OK), pass = town-cardholder-only
   - **Acton:** card = MA-resident, pass = network-wide
   This means **one `eligibility` field per library is structurally insufficient.** The schema needs `card_eligibility` and `pass_pickup_eligibility` as separate columns.

2. **A new value is needed: `walk-in_only`** (Wakefield) — non-residents can borrow but cannot reserve in advance. Different from network/town/MA in user-facing behavior (no online booking).

3. **A new value is needed: `card_holder_only`** (Cohasset) — passes are limited to cards *issued by this library*, not the network. Different from `network_only`.

4. **Per-pass residency restrictions exist** (Andover state-park passes). This means some restrictions live on the `(library × attraction)` cell in `passes.json`, **not** on `library.eligibility`. The data model needs a `restrictions.residency` field on `Pass`, not just on `Library`.

5. **BPL's eCard / physical-card split** is a third axis: residency requirement is the same for both card types, but **only the physical card unlocks pass borrowing**. This is a *card-type capability* gate, not a residency gate. Worth surfacing in product copy: "you may need to upgrade your eCard."

### Open questions

- Thayer (Braintree) and Milton card pages were not retrievable. Need direct visit or PDF parse to confirm.
- Reading PL pass-pickup policy: page returned generic text. Suspect there's a deeper policy page worth scraping.
- For libraries where pass-policy is silent (Milton, Reading): is the default "any cardholder, no re-check," or is there a hidden assumption?
- For Andover: are state-park passes the only per-pass-restricted ones, or are there other categories (e.g., zoo passes too)? Need full pass page.

### Recommended schema change (for v0.2)

Replace the single `library.eligibility` enum with:

```ts
library.card_eligibility:    "open" | "ma_resident" | "town_resident" | "network_holder" | "unknown"
library.pass_pickup_default: "any_cardholder" | "network_only" | "town_cardholder" | "town_resident" | "walkin_for_nonresidents" | "unknown"
pass.restrictions.residency: optional override at (library × attraction) level
                             e.g. {"andover-state-park-pass": "town_resident_only"}
```

The current enum collapses two dimensions and one per-cell override into one column, which is why classifications keep drifting back to `unknown` whenever a reviewer hits an edge case.
