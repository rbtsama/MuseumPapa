# North Shore Library Benefits — Project Context

This is a personal-use static-HTML tool that helps the user (Wakefield, MA resident with a 3-year-old daughter) plan family outings using public library museum-pass programs across the North Shore. The single deliverable is `library-benefits.html`, opened directly via `file://` in Chrome.

## Who the user is

- Lives in **Wakefield, MA**
- 3-year-old daughter — kid-friendly attractions are the priority
- Active on **Sat/Sun in Acton, MA** (church there)
- Currently holds 4 library cards:
  - **Wakefield** (NOBLE) — primary residence card
  - **Reading** (NOBLE) — non-resident NOBLE card
  - **BPL** (Boston Public Library, LibCal platform — NOT scraped, no automation)
  - **Wilmington** (MVLC, full physical card after upgrading from eCard) — barcode `22136000621942`
- Considered but not pursued: Burlington (MVLC) and Acton (MLN) cards
- The 3 personal Assabet barcodes are stored in `library-cards.json` (gitignored)

## What the deliverable does

The HTML file shows a single comparison matrix:
- **Rows**: 52 attractions (museums, zoos, parks, theaters), grouped by category, sortable by drive-time-from-Wakefield (default), category, or alphabetical
- **Columns**: 15 libraries (Wakefield + BPL + 13 other Assabet libraries within ~20-min drive)
- **Cells**: discount value (Free / Half-price / Discount / $X) + colored background, clickable to open that library's pass page in a new tab

Per-row UI elements:
- Drive-time pill (5–90 min, color-coded green/yellow/orange/red)
- Hours summary (e.g., `Wed–Sun 10–5`); auto-marks "CLOSED TODAY" if today is in `closed_days`
- Booking-complexity icon (🚪 walk-in / 📅 reservation rec. / 🎟️ booking required / 🔑 promo code / 🕐 timed tour / 🌤️ seasonal)
- "📅 Check & book" button → opens calendar modal

Per-cell markers:
- **★★** = circulating physical pass (pickup + return by 10am next day, $5–10 fine)
- **★** = coupon physical pass (pickup only, no return)
- (no marker) = digital pass (link emailed, no library trip needed)

Per-column header markers:
- ✓ blue badge on libraries the user owns cards for (Wakefield, BPL, Reading, Wilmington)
- 🟢/🟡/🔴 dot for non-resident-card policy (open to MA / network only / residents only)

## The Check-and-book modal

Click the per-row **📅 Check & book** button → modal with a 30-day calendar of merged availability across the 3 Assabet libraries the user has cards for (Reading, Wakefield, Wilmington — BPL uses LibCal so isn't scraped):

- **🟢 Green** — at least one of user's cards has it available
- **🟡 Yellow** — at least one has limited availability
- **⚪ Gray (others-only)** — none of user's cards work, but a non-owned library has it (informational, not clickable)
- **🔴 Red** — all 13 scraped libraries booked
- **⬛ Dark hatched (museum-closed)** — that day is in the attraction's `closed_days`, regardless of library availability — overrides everything else
- **▫ N/A** — no library carries this pass

Clicking a green/yellow date opens a yellow library-picker showing only the user's cards that work for that date. Clicking a card → opens that library's `/by-date/YYYY-mmm/DD/<slug>/` reservation form in a new tab AND copies that card's barcode to the clipboard. User pastes (⌘V), enters last name, submits.

## Default UI state (per user preference)

- ☑ "Show only kid-friendly" — pre-checked
- ☑ "Hide residents-only libraries" — pre-checked
- ☐ "Walk-in only" — off
- ☐ "Digital passes only" — off (when on, dims non-digital cells in place)
- Sort: "By drive time from Wakefield ↑"

## Repository layout

| File | Purpose |
|---|---|
| `library-benefits.html` | The deliverable — self-contained, opened via `file://` |
| `build.py` | Renders the HTML from JSON sources |
| `library-data.json` | Source of truth: 15 libraries, 52 attractions, 267 matrix cells, hours, booking model, closed days |
| `availability.json` | Last scrape of 30-day availability for the 3 user-owned Assabet libraries (now: 13 libraries) |
| `pass_format.json` | Per-cell `physical-circ` / `physical-coupon` / `digital` from each Assabet master index |
| `slug_map.py` | Hand-curated map: `benefit_id → {lib_id: assabet_slug}`, plus `LIB_DOMAIN`, `OWNED_FOR_BOOKING`, `LIB_PRIORITY` |
| `library-cards.json` | **gitignored** — user's 3 personal Assabet barcodes |
| `refresh.command` | Bash script to refresh the calendar — double-click to run scrape + build in Terminal |
| `update_data.py` | One-shot: added BPL + non-resident-policy fields |
| `add_distance.py` | One-shot: added `drive_min_from_wakefield` per benefit |
| `add_hours_booking.py` | One-shot: merged research-agent output (`hours-booking.json`) into matrix |
| `hours-booking.json` | Research-agent output — hours and booking model per attraction |
| `build_slug_map.py` | One-shot: auto-discovers Assabet slugs by scraping each library's by-museum index |
| `scrape_availability.py` | Scrapes 30-day calendar from each (library, attraction) Assabet page; ~7-30 sec |
| `scrape_pass_format.py` | Scrapes physical/coupon/digital classification from each library's master index; ~1 sec |
| `preview-*.png` | **gitignored** — verification screenshots from build iterations |

## Refresh flow

```bash
cd "/Users/alexchen/Projects/NorthShore Kids Events"
python3 scrape_availability.py   # ~7-30 sec, refreshes availability.json
python3 scrape_pass_format.py    # ~1 sec, refreshes pass_format.json
python3 build.py                 # ~0.5 sec, regenerates library-benefits.html
```

Or just double-click `refresh.command` from Finder/Desktop — it does steps 1+3 in a Terminal window. (NOTE: `refresh.command` doesn't currently call `scrape_pass_format.py`; pass-format data is stable, only re-scrape if a library reorganizes its catalog.)

## Key facts about Assabet's data model (learned through scraping)

- 13 libraries use **Assabet Interactive** (subdomain pattern `<libname>.assabetinteractive.com`)
- BPL uses **LibCal** (`bpl.libcal.com`) — different platform, not scraped
- Winchester uses custom (`winpublib.org`) — also not scraped, residents-only anyway
- Each library's `museum-passes/by-museum/` page lists all passes; each attraction's slug-block has a `<p class="museum-pass-pass-type">Pass Type: ...</p>` field with EXACTLY one of three values:
  - "Circulating Pass (must be picked up and returned to the branch)"
  - "Coupon Pass (must be picked up from the branch, but does not require returning)"
  - "Printable/Digital Coupon Pass (link delivered by email)"
- Calendar availability uses CSS classes `day-has-openings`, `day-no-openings`, `time-partially-available` per `day-YYYY-MM-DD` div
- Reservation deep-link format: `/museum-passes/by-date/YYYY-mmm/DD/<slug>/` (lowercase month abbreviation, zero-padded day) — lands directly on the form expecting library card barcode

## Library policies relevant to this project

- **Wakefield, Reading**: NOBLE network, accept any MA resident
- **Stoneham, Lynnfield, Peabody, Saugus, North Reading**: also NOBLE, also accept any MA resident
- **Woburn, Melrose, Winchester, Malden, Medford**: residents-only for museum passes (filtered via "Hide residents-only" toggle, default on)
- **Burlington, Wilmington**: MVLC network — accept any MA resident from MBLC-certified town (i.e., almost anywhere)
- **Acton (not currently in table)**: MLN network — accepts any MA resident, would be valuable for after-church Sat/Sun in Acton, mainly for Discovery Museum same-day walk-in
- **Wakefield no-show policy**: "Failure to notify the library of cancellations may result in forfeiture of future bookings" — informally one-and-done warning
- **BPL cancellation**: ≥1 day notice by phone, ≥2 days online; same-day cancellation NOT allowed

## Cancellation flow (the easy way)

Each Assabet booking confirmation email contains a unique cancel-link — clicking it cancels without login. Recommend the user keep these emails labeled.

## Things deliberately NOT done

- **Full auto-booking** — needs PIN/last name and is ToS-gray. The current "click → opens form + copies barcode" is the right tradeoff.
- **BPL availability scraping** — different platform (LibCal), would require separate scraper. BPL's "books up fast" passes (Free MOS, Free NEAQ) are major user-relevant gaps.
- **Live in-browser availability refresh** — requires backend due to CORS. Current model is "scrape via terminal, embed in HTML at build time".
- **Real-time updates** — `refresh.command` (manual double-click) is the user's confirmed preferred refresh mechanism. She rejected the local-Python-server option.
- **Holiday/special closures** — only weekly closed_days are baked in. Holiday closures still cause user surprise.

## Outstanding tradeoffs / known issues

- Pass-format scrape ran with 100% coverage at last run, but new attractions added by libraries will appear as "unknown" until next `scrape_pass_format.py` run.
- Distance estimates in `add_distance.py` are rough non-rush-hour minutes — may be off ±10 min in real conditions.
- `closed_days` only encodes weekly recurring closures; holiday closures (e.g., Christmas, Thanksgiving) not handled.
- Acton Memorial Library would be a natural 14th Assabet library to add but the user hasn't gotten that card yet (decided Discovery Museum doesn't justify the trip since pass terms are uniform across libraries).

## Style notes for future Claude sessions

- The user prefers terse, action-oriented responses (Chinese, mostly).
- She's an active iterator — runs the page constantly, finds bugs herself, requests targeted fixes.
- She values **honest "this won't work"** answers (e.g., the eCard / Acton / BPL automation analyses).
- When she asks for a feature, the right move is usually a small targeted change to `build.py` + a rebuild — not adding new abstractions.
- All her personal data (card barcodes) stays in `library-cards.json` which is gitignored. Never include barcodes in commit messages or log output that might leak to remote.
- The git repo is local-only. No remote configured. Don't push.

## Recent commit history (most recent first)

```
4bfd5f6 Per-cell pass-format stars from Assabet master index
c48a59f Star physical-pass attractions; Wilmington physical card unlocked
c1c2578 Skip museum-closed days in calendar regardless of library pass availability
c9c35d2 Scrape all 13 Assabet libraries; tri-state calendar coloring
12e940b Add refresh.command + in-page Refresh button
9ac918c Filter Wilmington eCard from physical-pass attractions
bf3a482 Initial: Wakefield-area library benefits comparison + booking helper
```
