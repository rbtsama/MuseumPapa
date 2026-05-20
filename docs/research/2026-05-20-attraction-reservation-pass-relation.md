# Attraction-side reservation vs library museum pass — relationship study

Date: 2026-05-20
Scope: 5 representative timed-entry / reservation-driven Boston-area museums.
Method: WebFetch / WebSearch on museum-own pages + library landing pages. Verbatim quotes preserved.

---

## 1. Museum of Fine Arts (MFA), Boston

Museum-own pass page: https://www.mfa.org/membership/libraries-and-non-profits
General ticketing: https://www.mfa.org/tickets

- **Reservation requirement for general visitors**: MFA sells timed tickets via mfa.org/tickets; same-day walk-ins possible but timed-entry is the default flow.
- **Pass-holder flow**: promo-code model. Verbatim: *"Each institution is provided with a unique promo code, which will allow your patrons to redeem their admission discount online or in person. If redeeming in person, patrons must provide an e-mail from the library with the promo code."* The library issues the code; the patron applies it on mfa.org during checkout to lock the timed slot.
- **Exempt from timed-entry?** No exemption stated. The promo code still flows through the timed-entry funnel.
- **Contact**: *"Contact us at [obfuscated email] or call 617-369-4136."*
- **Bundled benefits**: Explicit exclusion. *"Passes are not applicable toward discounts on shopping, parking, dining, films, concerts, lectures, courses, or any other public programs."*

Pattern: **Library issues code → patron books timed slot on museum site with code → code = discount mechanism, not a reservation shortcut**.

---

## 2. Museum of Science (MoS), Boston

Museum-own page: https://www.mos.org/visit/ways-to-save (HTTP 403 to WebFetch; relying on search excerpt + BPL LibCal entry https://bpl.libcal.com/passes/25815fed11ec).

- **Reservation requirement**: Timed-entry reservations are encouraged and frequently required during peaks. Library passes do not bypass timed-entry capacity.
- **Pass-holder flow**: Library issues an e-ticket / pass; patron then reserves a specific time slot on mos.org, often via a "Library Pass holders" link where the pass number/code is entered.
- **Exempt from timed-entry?** No. Walk-ups with library pass can be turned away if slot is full.
- **Contact**: Refers patrons back to issuing library; no museum-side pass hotline surfaced.
- **Bundled benefits**: Pass covers Exhibit Halls admission only. Omni/planetarium/special exhibits and parking not bundled.

Pattern: **same as MFA — code/voucher + separate timed-slot booking on museum site**.

---

## 3. Boston Children's Museum (BCM)

Museum-own pass page: https://bostonchildrensmuseum.org/membership/library-membership/

- **Reservation requirement**: Timed tickets are the museum's reservation flow.
- **Pass-holder flow**: Verbatim: *"After receiving your coupon from the library, make a reservation on the Museum's Reservations web page. Select Discount Programs – Select Purchase Discount Program Tickets – Select Half Price Library Timed Tickets – Complete your transaction. You will receive your tickets via e-mail."* Visit day: *"bring your tickets and your library discount coupon."*
- **Exempt from timed-entry?** No — explicitly the SKU is named *"Half Price Library Timed Tickets"*, i.e., a dedicated pass-holder lane *inside* the timed-entry system.
- **Contact**: *"Contact the Membership office via telephone – (617) 426-6500 x354"*
- **Bundled benefits**: None — discount applies only to admission.

Pattern: **Two-step (library coupon → museum timed-ticket SKU) with a named pass-holder SKU**. Slightly stronger than MFA: BCM exposes a dedicated discount-program ticket type rather than just a promo code.

---

## 4. Peabody Essex Museum (PEM)

Museum-own page: https://www.pem.org/pems-library-university-pass-program

- **Reservation requirement**: PEM uses online tickets but is generally not strict timed-entry except for special exhibits.
- **Pass-holder flow**: Verbatim: *"your library will receive a unique promotional code for discounted general admission tickets to PEM. Library patrons can purchase museum tickets online at the reduced rate of $12 per person"*. Code is capped (*"can be used 350 times per year"*).
- **Exempt from timed-entry?** No exemption stated; ticket purchase is the same flow as any visitor, just at a discounted price.
- **Contact**: *"alexandra_hoch@pem.org or 978-542-1585"* (Alexandra Hoch).
- **Bundled benefits**: None mentioned; pass covers general admission only.

Pattern: **promo-code into normal ticket flow** (closest to pure-discount; no separate booking lane).

---

## 5. Isabella Stewart Gardner Museum (ISGM)

Museum-own pass page: https://www.gardnermuseum.org/join-give/library-membership
Admissions page: https://www.gardnermuseum.org/visit/admissions

- **Reservation requirement (general)**: Verbatim from /visit/admissions: *"Advance tickets are required for timed entry."* and *"Tickets can sell out fast, and tickets may not be available at the door, particularly during popular days of the week and times of day."*
- **Pass-holder flow**: Verbatim: *"Library patrons must reserve and receive passes from their library and purchase Museum admission timed-entry tickets in advance using the unique promo code given with each pass."* From the program page: *"Each institution will receive a unique promo code, which will allow library patrons to redeem their admission discount online."* Passes are *"valid only for general admission"* and *"can be used any day the Museum is open"* (no blackout on the *code*, but timed-slot availability still applies). Code must be redeemed *"at least 48 hours prior to visiting"*.
- **Exempt from timed-entry?** **No — explicitly required.** Strongest "you must still book a timed slot" language of the five.
- **Contact**: *"Contact the Membership Office at 617 566 5643 or membership@isgm.org"*; for booking issues *"contact the Box Office at 617 278 5156 or boxoffice@isgm.org at least 48 hours prior to your visit."*
- **Bundled benefits**: Explicit exclusion. *"Passes are valid only for general admission. They are not applicable toward discounts on special events, shopping, dining, concerts, lectures, or any other public and member programs."* Children 17 and under always free regardless of pass.

Pattern: **strictest variant — timed entry mandatory, promo code into museum's own booking system, 48-hour pre-booking floor**.

---

## Cross-cutting pattern

All 5 museums follow the **same skeleton**:

```
library_card → library issues {coupon | promo_code | e-voucher}
            → patron goes to museum's own ticket site
            → enters code in checkout
            → museum site assigns a specific timed slot
            → patron arrives with (museum ticket + library coupon) for door check
```

Variations are small:

| Museum  | Pass-holder lane                                          | Timed-entry exemption | Code lifecycle constraint           | Bundled extras |
|---------|-----------------------------------------------------------|-----------------------|-------------------------------------|----------------|
| MFA     | Same checkout, promo code applies discount                | No                    | Code reusable per institution       | None (explicit) |
| MoS     | Optional "Library Pass holders" section, enter code       | No                    | Per-library quota                   | Exhibit Halls only |
| BCM     | Dedicated SKU "Half Price Library Timed Tickets"          | No                    | Per coupon                          | None |
| PEM     | Same checkout, promo code applies discount                | Not strictly enforced | 350 uses/yr per library             | None |
| ISGM    | Same checkout, promo code applies discount, 48-hr floor   | No (strictest)        | Code locked to reservation date     | None (explicit) |

Across all five: **the museum's own timed-entry system is the source of truth for "can you actually get in at time T"**. The library pass is **only** the price-modifier and proof-of-discount at the door — it is **not** a reservation.

No museum we surveyed exempts pass holders from timed entry.
No museum we surveyed bundles parking / shop / dining with the library pass — all five either explicitly exclude these or simply don't mention them.

---

## Proposed data model

Current `passes.json` (per plan-9) carries `coupon` (capacity/audience/value) and `restrictions` (blackout / weekdays_only / seasonal / reservation_required as a boolean). That boolean is **not enough** to drive the user UX for the 21 timed-entry museums, because it conflates:

- "needs an offline phone-call reservation through the library"
- "needs a separate timed slot booked on the *museum's* site after getting the pass"
- "promo code only, no slot constraint"

### Proposed addition — split reservation pathway

Add a new field per attraction (move OUT of `passes.json`, INTO `attractions.json` — because the reservation rules are a property of the attraction, not the lib×attraction cell):

```jsonc
// attractions.json :: <attraction>
{
  "reservation": {
    "required": "timed_entry",          // enum: none | timed_entry | walk_in_ok
    "booking_url": "https://www.mfa.org/tickets",
    "lead_time_hours": 0,                // ISGM = 48
    "pass_holder_path": {
      "kind": "promo_code_in_general_checkout",
      // enums: promo_code_in_general_checkout
      //      | dedicated_pass_sku            (BCM "Half Price Library Timed Tickets")
      //      | dedicated_pass_holders_url    (MoS "Library Pass holders" link)
      //      | library_only                  (no museum-side booking)
      "instructions": "Enter promo code from library at checkout.",
      "contact_phone": "617-369-4136",
      "contact_email": "..."
    },
    "exempts_pass_holder_from_timed_entry": false  // none of our 5 are true
  }
}
```

And the per-cell `passes.json` keeps its `coupon` + `restrictions` but `restrictions.reservation_required` becomes a soft boolean — overridden by `attractions[*].reservation` at display time. Rationale: the *requirement* lives on the attraction, the *coupon mechanics* live on the cell.

### Recommendation

**Our current `museum_reservation` model is insufficient.** It treats reservation as a binary on the (lib, attraction) cell. The reality is a property of the attraction with a sub-shape describing the pass-holder funnel (promo code vs dedicated SKU vs dedicated URL). The proposed `reservation` object on `attractions.json` captures the four observed funnel types and the lead-time floor (ISGM 48h is the only non-zero in our sample but more will surface as we scale to 21 museums).

The booklet UX consequence: any attraction with `reservation.required == "timed_entry"` should render a prominent "**Two steps**: 1) get pass from library, 2) book timed slot on `<booking_url>` with promo code" callout. Without this, users will show up with a pass and an empty calendar slot and get turned away — which is exactly the failure mode the team is worried about.
