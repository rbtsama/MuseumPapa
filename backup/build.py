import html
import json
from pathlib import Path

from slug_map import LIB_DOMAIN, LIB_PRIORITY, OWNED_FOR_BOOKING, SLUG_MAP
from bpl_id_map import BPL_PASS_ID
from bpl_pass_format import BPL_FMT

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / "library-data.json").read_text())
AVAIL = json.loads((ROOT / "availability.json").read_text()) if (ROOT / "availability.json").exists() else {"data": {}, "scraped_at": ""}
BPL_AVAIL = json.loads((ROOT / "bpl_availability.json").read_text()) if (ROOT / "bpl_availability.json").exists() else {"data": {}, "scraped_at": ""}
CARDS = json.loads((ROOT / "library-cards.json").read_text()) if (ROOT / "library-cards.json").exists() else {}
PASS_FORMAT = json.loads((ROOT / "pass_format.json").read_text()).get("data", {}) if (ROOT / "pass_format.json").exists() else {}
for _bid, _fmt in BPL_FMT.items():
    PASS_FORMAT.setdefault(_bid, {})["bpl"] = _fmt

CATEGORY_ORDER = ["kids", "parks", "general", "other"]
CATEGORY_LABEL = {
    "kids": "Kid-friendly (3-year-old approved)",
    "parks": "Parks & outdoors",
    "general": "Art, history & adult-oriented",
    "other": "Theatre & other",
}


def drive_label(mins):
    if mins is None:
        return ""
    return f"{mins} min"


def drive_band(mins):
    if mins is None:
        return "unk"
    if mins <= 15:
        return "near"
    if mins <= 30:
        return "med"
    if mins <= 45:
        return "far"
    return "very-far"

VALUE_CLASS = {
    "Free": "free",
    "Half-price": "half",
    "Discount": "discount",
}


def value_class(v: str) -> str:
    if v in VALUE_CLASS:
        return VALUE_CLASS[v]
    if v.startswith("$"):
        return "price"
    return "discount"


libraries = DATA["libraries"]
benefits_sorted = sorted(
    DATA["benefits"],
    key=lambda b: (CATEGORY_ORDER.index(b["category"]), b["name"].lower()),
)
matrix = DATA["matrix"]


def cell_html(lib_id: str, benefit_id: str) -> str:
    lib = next((l for l in libraries if l["id"] == lib_id), None)
    policy = (lib or {}).get("non_resident_policy", "unknown")
    cell = matrix.get(lib_id, {}).get(benefit_id)
    fmt = PASS_FORMAT.get(benefit_id, {}).get(lib_id, "unknown")
    base_attrs = f'data-policy="{policy}" data-libid="{lib_id}" data-format="{fmt}"'
    if not cell:
        return f'<td class="empty" {base_attrs}>—</td>'
    val = cell["value"]
    note = cell.get("note", "")
    cls = value_class(val)
    pass_page = (lib or {}).get("pass_page") or "#"
    marker, marker_title = PASS_FORMAT_MARKER.get(fmt, ('', ''))
    star = (
        f'<span class="cell-star" title="{html.escape(marker_title)}">{marker}</span>'
        if marker else ''
    )
    title_parts = []
    if note: title_parts.append(note)
    if marker_title: title_parts.append(marker_title)
    title = html.escape(" — ".join(title_parts) or val)
    return (
        f'<td class="cell {cls}" {base_attrs}>'
        f'<a href="{html.escape(pass_page)}" target="_blank" rel="noopener" '
        f'title="{title}">{html.escape(val)}{star}</a>'
        f"</td>"
    )


OWNED = {"wakefield", "reading", "bpl", "wilmington"}
POLICY_DOT = {
    "open_ma_resident": ("dot-open",     "Open to any MA resident"),
    "network_only":     ("dot-network",  "Network cardholders only (MVLC/NOBLE/MLN)"),
    "residents_only":   ("dot-residents","Town residents only"),
    "non_resident_fee": ("dot-fee",      "Non-resident fee"),
    "unknown":          ("dot-unknown",  "Policy unknown — call to confirm"),
}


def header_cell(lib: dict) -> str:
    full = html.escape(lib["name"])
    town = html.escape(lib["town"])
    notes = html.escape(lib.get("notes", ""))
    href = html.escape(lib["pass_page"] or "#")
    policy = lib.get("non_resident_policy", "unknown")
    dot_cls, dot_title = POLICY_DOT.get(policy, POLICY_DOT["unknown"])
    owned = " owned" if lib["id"] in OWNED else ""
    badge = '<span class="owned-badge" title="You already have this card">✓</span>' if lib["id"] in OWNED else ""
    return (
        f'<th class="lib-col{owned}" data-policy="{policy}" data-libid="{lib["id"]}" '
        f'title="{full} — {notes}">'
        f'<span class="dot {dot_cls}" title="{html.escape(dot_title)}"></span>'
        f'<a href="{href}" target="_blank" rel="noopener">{town}</a>{badge}'
        f"</th>"
    )


WILMINGTON_ECARD_BLOCKED = set()

PASS_FORMAT_MARKER = {
    "physical-circ":   ('★★', 'Circulating physical pass — pick up at library AND return by 10am next day. $5–10 late fee.'),
    "physical-coupon": ('★',  'Coupon pass — pick up at library, but no return needed.'),
    "digital":         ('',   'Digital pass — link emailed, no library trip required.'),
}


def build_avail_index():
    """For each benefit_id, map date -> { perLib: { lib: status } }.
    All scraped libraries are included so the calendar can show "exists at a
    library you don't have a card for" (gray) vs "all booked everywhere" (red).
    Wilmington is dropped only for attractions on the eCard physical-pass blacklist.
    BPL availability is merged in alongside the 13 Assabet libraries.
    """
    out = {}
    avail_data = AVAIL.get("data", {})
    bpl_data = BPL_AVAIL.get("data", {})
    all_bids = set(avail_data) | set(bpl_data)
    for bid in all_bids:
        libs = dict(avail_data.get(bid, {}))
        libs = {k: v for k, v in libs.items()
                if not (k == "wilmington" and bid in WILMINGTON_ECARD_BLOCKED)}
        if bid in bpl_data:
            libs["bpl"] = bpl_data[bid].get("bpl", {})
        all_dates = set()
        for d in libs.values():
            all_dates.update(d.keys())
        per_date = {}
        for date in sorted(all_dates):
            per_lib = {lib: libs[lib].get(date, "closed") for lib in libs}
            per_date[date] = {"p": per_lib}
        out[bid] = per_date
    return out


AVAIL_INDEX = build_avail_index()


BOOKING_ICON = {
    "walk_in":     ("🚪", "Walk-in — show pass at door, no second booking"),
    "recommended": ("📅", "Reservation recommended — capacity-limited, booking encouraged on museum site"),
    "required":    ("🎟️", "Reservation REQUIRED — must book timed slot on museum's site after getting library pass"),
    "promo_code":  ("🔑", "Promo code — library gives a code, you book a timed ticket on museum site"),
    "timed_tour":  ("🕐", "Timed tour — must arrive at scheduled tour slot"),
    "seasonal":    ("🌤️", "Seasonal — open only part of year; check site for current dates"),
}


def benefit_row(b: dict) -> str:
    kid = "kid" if b.get("kid_focused") else "adult"
    cells = "".join(cell_html(lib["id"], b["id"]) for lib in libraries)
    name = html.escape(b["name"])
    href = html.escape(b.get("official_url", "#"))
    mins = b.get("drive_min_from_wakefield")
    band = drive_band(mins)
    drive = (
        f'<span class="drive drive-{band}" title="Drive time from Wakefield">'
        f'{drive_label(mins)}</span>' if mins is not None else ""
    )
    sort_mins = mins if mins is not None else 999

    hours = html.escape(b.get("hours_summary", ""))
    closed = b.get("closed_days", []) or []
    booking = b.get("booking_model", "walk_in")
    booking_icon, booking_title = BOOKING_ICON.get(booking, BOOKING_ICON["walk_in"])
    note = html.escape(b.get("booking_note", ""))
    full_title = f"{booking_title}. {note}" if note else booking_title

    badge = (
        f'<span class="booking-icon booking-{booking}" title="{html.escape(full_title)}">'
        f'{booking_icon}</span>'
    )
    hours_line = (
        f'<div class="hours-line" data-closed-days="{",".join(closed)}">'
        f'{badge}<span class="hours-text">{hours}</span></div>'
        if hours else ""
    )

    return (
        f'<tr class="row {kid}" data-kid="{str(b.get("kid_focused")).lower()}" '
        f'data-cat="{b["category"]}" data-mins="{sort_mins}" '
        f'data-name="{name.lower()}" data-booking="{booking}" '
        f'data-closed="{",".join(closed)}">'
        f'<th class="benefit-col">'
        f'<a href="{href}" target="_blank" rel="noopener">{name}</a>'
        f"{drive}"
        f"{hours_line}"
        f'{book_btn(b["id"])}'
        f"</th>"
        f"{cells}"
        f"</tr>"
    )


def book_btn(benefit_id: str) -> str:
    if benefit_id not in AVAIL_INDEX or not AVAIL_INDEX[benefit_id]:
        return ""
    return (
        f'<button class="book-btn" data-bid="{benefit_id}" '
        f'title="Check 30-day availability across your 3 cards">📅 Check &amp; book</button>'
    )


def section_rows() -> str:
    by_cat: dict[str, list] = {c: [] for c in CATEGORY_ORDER}
    for b in benefits_sorted:
        by_cat[b["category"]].append(b)
    blocks = []
    span = len(libraries) + 1
    for cat in CATEGORY_ORDER:
        items = by_cat[cat]
        if not items:
            continue
        kid_attr = "true" if cat in ("kids", "parks") else "false"
        blocks.append(
            f'<tr class="section" data-kid="{kid_attr}" data-cat="{cat}">'
            f'<th colspan="{span}">{CATEGORY_LABEL[cat]}</th>'
            f"</tr>"
        )
        blocks.extend(benefit_row(b) for b in items)
    return "\n".join(blocks)


def flat_rows() -> str:
    return "\n".join(benefit_row(b) for b in benefits_sorted)


HEADERS = "".join(header_cell(l) for l in libraries)
ROWS = section_rows()
DATE = DATA.get("researched_date", "")
LIB_COUNT = len(libraries)
BENEFIT_COUNT = len(benefits_sorted)
CELL_COUNT = sum(len(v) for v in matrix.values())

LIB_LEGEND = "".join(
    f'<li><a href="{html.escape(l["pass_page"] or "#")}" target="_blank" rel="noopener">'
    f'<strong>{html.escape(l["town"])}</strong></a> — '
    f'<span class="muted">{html.escape(l["name"])}</span> '
    f'<em>{html.escape(l.get("notes", ""))}</em></li>'
    for l in libraries
)

AVAIL_JSON = json.dumps(AVAIL_INDEX)
CARDS_JSON = json.dumps({k: {"barcode": v["barcode"]} for k, v in CARDS.items() if k in LIB_DOMAIN or k == "bpl"})
BPL_PASS_ID_JSON = json.dumps(BPL_PASS_ID)
SLUG_MAP_JSON = json.dumps(SLUG_MAP)
LIB_DOMAIN_JSON = json.dumps(LIB_DOMAIN)
LIB_PRIORITY_JSON = json.dumps(LIB_PRIORITY)
OWNED_LIBS_JSON = json.dumps(OWNED_FOR_BOOKING)
BENEFIT_NAMES_JSON = json.dumps({b["id"]: b["name"] for b in DATA["benefits"]})
BENEFIT_CLOSED_JSON = json.dumps({b["id"]: b.get("closed_days", []) for b in DATA["benefits"]})
SCRAPED_AT = AVAIL.get("scraped_at", "")

HTML_DOC = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>North Shore Library Benefits — Wakefield Area</title>
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f7f7f8;
  color: #111;
}}
header {{
  padding: 18px 20px 10px;
  background: #fff;
  border-bottom: 1px solid #e5e5e8;
  position: sticky; top: 0; z-index: 50;
}}
h1 {{ margin: 0 0 4px; font-size: 20px; }}
.sub {{ color: #666; font-size: 13px; }}
.controls {{ margin-top: 10px; display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }}
.controls label {{ user-select: none; cursor: pointer; }}
.legend {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; }}
.swatch {{
  display: inline-block; width: 14px; height: 14px; border-radius: 3px;
  vertical-align: middle; margin-right: 4px; border: 1px solid rgba(0,0,0,.08);
}}
.swatch.free     {{ background: #b6f0c5; }}
.swatch.half     {{ background: #ffe7a8; }}
.swatch.discount {{ background: #ffd7b3; }}
.swatch.price    {{ background: #fff2cc; }}
.swatch.empty    {{ background: #ececef; }}

.dot {{
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 5px; vertical-align: middle; border: 1px solid rgba(0,0,0,.15);
}}
.dot.dot-open      {{ background: #4caf50; }}
.dot.dot-network   {{ background: #ffb300; }}
.dot.dot-residents {{ background: #e53935; }}
.dot.dot-fee       {{ background: #ab47bc; }}
.dot.dot-unknown   {{ background: #999; }}

.owned-badge {{
  display: inline-block; margin-left: 4px;
  background: #1976d2; color: white;
  border-radius: 50%; width: 14px; height: 14px;
  font-size: 10px; line-height: 14px; text-align: center;
  font-weight: 700;
}}
.lib-col.owned {{ background: #e3f2fd !important; }}
thead th.lib-col.owned {{ background: #e3f2fd; }}

.drive {{
  display: inline-block;
  margin-left: 8px;
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  vertical-align: middle;
  white-space: nowrap;
}}
.drive-near     {{ background: #c8e6c9; color: #1b5e20; }}
.drive-med      {{ background: #fff9c4; color: #6f5a00; }}
.drive-far      {{ background: #ffe0b2; color: #7b3f00; }}
.drive-very-far {{ background: #ffcdd2; color: #7f1d1d; }}

select.sort {{
  font: inherit; padding: 3px 8px; border: 1px solid #ccc; border-radius: 4px;
  background: #fff;
}}

.hours-line {{
  margin-top: 3px;
  font-size: 11.5px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: normal;
}}
.hours-text {{ font-variant-numeric: tabular-nums; }}
.booking-icon {{
  display: inline-block;
  font-size: 13px;
  cursor: help;
  user-select: none;
}}
.booking-required, .booking-promo_code {{ filter: hue-rotate(0deg); }}

tr.row.closed-today .benefit-col {{ background: #fff5f5; }}
tr.row.closed-today .hours-text::after {{
  content: " · CLOSED TODAY";
  color: #c62828;
  font-weight: 700;
  font-size: 10.5px;
  letter-spacing: .03em;
}}

body.walk-in-only tr.row:not([data-booking="walk_in"]) {{ display: none; }}
body.walk-in-only tr.section[data-cat="other"],
body.walk-in-only tr.section[data-cat="general"] {{ display: none; }}

body.digital-only td.cell:not([data-format="digital"]):not(.empty) a {{
  filter: saturate(.2) opacity(.4);
}}
body.digital-only td.cell:not([data-format="digital"]):not(.empty) {{
  pointer-events: none;
}}

.cell-star {{
  display: inline-block;
  margin-left: 3px;
  font-size: 9px;
  vertical-align: middle;
  color: rgba(0,0,0,.55);
  letter-spacing: -1px;
  cursor: help;
  user-select: none;
}}

.book-btn {{
  display: inline-block;
  margin-top: 4px;
  padding: 3px 8px;
  font: inherit;
  font-size: 11.5px;
  font-weight: 600;
  background: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}}
.book-btn:hover {{ background: #1565c0; }}

.modal-backdrop {{
  position: fixed; inset: 0;
  background: rgba(0,0,0,.5);
  z-index: 100;
  display: none;
  align-items: flex-start;
  justify-content: center;
  padding: 40px 16px 16px;
  overflow-y: auto;
}}
.modal-backdrop.open {{ display: flex; }}
.modal {{
  background: #fff;
  border-radius: 8px;
  max-width: 640px;
  width: 100%;
  padding: 20px;
  box-shadow: 0 8px 32px rgba(0,0,0,.2);
}}
.modal-header {{ display: flex; justify-content: space-between; align-items: start; margin-bottom: 4px; }}
.modal-title {{ font-size: 17px; font-weight: 700; margin: 0; }}
.modal-sub {{ font-size: 12px; color: #666; margin-bottom: 12px; }}
.modal-close {{
  background: none; border: none; font-size: 24px; cursor: pointer; line-height: 1;
  padding: 0 6px; color: #999;
}}
.cal {{
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  margin-bottom: 12px;
}}
.cal-day-label {{
  font-size: 11px;
  color: #999;
  text-align: center;
  font-weight: 600;
  padding: 4px 0;
}}
.cal-cell {{
  aspect-ratio: 1;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  position: relative;
}}
.cal-cell.empty {{ visibility: hidden; cursor: default; }}
.cal-cell.past {{ background: #f5f5f5; color: #c0c0c4; cursor: default; }}
.cal-cell.available    {{ background: #b6f0c5; color: #1b5e20; }}
.cal-cell.bpl-available {{ background: #d9b3ff; color: #4a148c; box-shadow: inset 0 0 0 1px #8e24aa; }}
.cal-cell.limited      {{ background: #ffe7a8; color: #6f5a00; }}
.cal-cell.others-only  {{ background: #d5d5d8; color: #555; cursor: default; }}
.cal-cell.museum-closed {{
  background: #2c2c30; color: #c0c0c4; cursor: default; position: relative;
}}
.cal-cell.museum-closed::after {{
  content: ''; position: absolute; inset: 4px;
  background: repeating-linear-gradient(45deg,
    transparent, transparent 4px,
    rgba(255,255,255,.08) 4px, rgba(255,255,255,.08) 8px);
  pointer-events: none; border-radius: 4px;
}}
.cal-cell.museum-closed > * {{ position: relative; z-index: 1; }}
.cal-cell.booked       {{ background: #ffd4d4; color: #7f1d1d; cursor: default; }}
.cal-cell.na           {{ background: #ececef; color: #999; cursor: default; }}
.cal-cell:not(.past):not(.booked):not(.na):not(.empty):not(.others-only):not(.museum-closed):hover {{ filter: brightness(.93); border-color: #1976d2; }}
.cal-cell.bpl-available:hover {{ border-color: #8e24aa; }}
.cal-cell .lib-tag {{ font-size: 9.5px; opacity: .7; margin-top: 1px; text-transform: uppercase; letter-spacing: .04em; }}
.cal-month-header {{ grid-column: 1 / -1; font-weight: 700; padding: 8px 4px 2px; color: #333; font-size: 13px; }}
.modal-instructions {{ font-size: 12.5px; color: #555; line-height: 1.5; padding: 10px 12px; background: #f4f7fb; border-radius: 6px; }}
.modal-instructions kbd {{ background: #fff; border: 1px solid #ccc; border-bottom-width: 2px; border-radius: 3px; padding: 1px 5px; font-size: 11px; }}
.refresh-btn {{
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  background: #1976d2;
  color: white !important;
  border-radius: 4px;
  text-decoration: none !important;
  font-size: 11.5px;
  font-weight: 600;
}}
.refresh-btn:hover {{ background: #1565c0; }}
#refresh-status.stale #refresh-age {{ color: #c62828; font-weight: 700; }}

.copy-toast {{
  position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
  background: #1b5e20; color: white; padding: 10px 18px; border-radius: 6px;
  font-size: 14px; font-weight: 600; z-index: 200;
  opacity: 0; transition: opacity .2s;
  pointer-events: none;
}}
.copy-toast.show {{ opacity: 1; }}

.lib-picker {{
  display: none;
  margin-top: 12px;
  padding: 14px;
  background: #fffbe6;
  border: 1px solid #f0d97e;
  border-radius: 6px;
}}
.lib-picker.open {{ display: block; }}
.lib-picker-title {{
  font-size: 13.5px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #5d4500;
}}
.lib-picker-buttons {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}}
.lib-pick-btn {{
  flex: 1 1 0;
  min-width: 130px;
  padding: 10px 12px;
  background: #fff;
  border: 2px solid #1976d2;
  border-radius: 6px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  color: #1976d2;
  text-align: left;
}}
.lib-pick-btn:hover {{ background: #e3f2fd; }}
.lib-pick-btn.limited {{ border-color: #b8860b; color: #6f5a00; }}
.lib-pick-btn.limited:hover {{ background: #fff8e1; }}
.lib-pick-btn.bpl {{ border-color: #8e24aa; color: #4a148c; background: #f3e5f5; }}
.lib-pick-btn.bpl:hover {{ background: #e1bee7; }}
.lib-pick-btn .pick-status {{
  display: block;
  font-size: 10.5px;
  font-weight: 500;
  opacity: .8;
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: .04em;
}}
.lib-picker-cancel {{
  background: none;
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #666;
}}

main {{ padding: 12px 16px 60px; }}

.table-wrap {{
  overflow: auto;
  background: #fff;
  border: 1px solid #e5e5e8;
  border-radius: 6px;
  max-height: calc(100vh - 160px);
}}
table {{
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
  min-width: max-content;
}}
th, td {{
  padding: 6px 8px;
  border-bottom: 1px solid #ececef;
  border-right: 1px solid #f0f0f3;
  text-align: center;
  white-space: nowrap;
}}
thead th {{
  position: sticky;
  top: 0;
  background: #fafafb;
  z-index: 5;
  font-weight: 600;
  border-bottom: 2px solid #d4d4d8;
}}
thead th.benefit-col {{
  left: 0; z-index: 6;
  text-align: left;
  background: #fafafb;
}}
.benefit-col {{
  position: sticky; left: 0;
  background: #fff;
  text-align: left;
  font-weight: 500;
  min-width: 220px;
  max-width: 280px;
  white-space: normal;
  border-right: 2px solid #d4d4d8;
  z-index: 4;
}}
.benefit-col a {{ color: #111; text-decoration: none; }}
.benefit-col a:hover {{ text-decoration: underline; }}
.lib-col a {{ color: #111; text-decoration: none; }}
.lib-col a:hover {{ text-decoration: underline; color: #0366d6; }}

tr.section th {{
  position: sticky; left: 0;
  background: #eef3fa;
  color: #1f3a68;
  text-align: left;
  font-weight: 600;
  font-size: 12px;
  letter-spacing: .02em;
  text-transform: uppercase;
  padding: 8px 10px;
  border-bottom: 1px solid #c8d6ea;
  z-index: 3;
}}

td.cell a {{
  display: block;
  padding: 4px 6px;
  border-radius: 3px;
  color: #111;
  text-decoration: none;
  font-weight: 600;
  font-size: 12.5px;
}}
td.cell.free a     {{ background: #b6f0c5; }}
td.cell.half a     {{ background: #ffe7a8; }}
td.cell.discount a {{ background: #ffd7b3; }}
td.cell.price a    {{ background: #fff2cc; }}
td.cell a:hover {{ filter: brightness(.94); text-decoration: underline; }}
td.empty {{ color: #c0c0c4; }}

body.kid-only tr.row.adult,
body.kid-only tr.section[data-kid="false"] {{ display: none; }}

body.hide-residents-only [data-policy="residents_only"] {{ display: none; }}

footer {{
  padding: 18px 20px;
  color: #666;
  font-size: 12.5px;
  background: #fff;
  border-top: 1px solid #e5e5e8;
  margin-top: 16px;
}}
footer ul {{ margin: 8px 0 0; padding-left: 18px; }}
footer li {{ margin: 4px 0; }}
.muted {{ color: #888; }}
em {{ color: #555; font-style: normal; font-size: 12px; }}

@media (max-width: 640px) {{
  header {{ padding: 12px 12px 8px; }}
  h1 {{ font-size: 17px; }}
  main {{ padding: 8px 8px 40px; }}
  .benefit-col {{ min-width: 180px; max-width: 200px; font-size: 12px; }}
  th, td {{ padding: 5px 6px; }}
  td.cell a {{ font-size: 11.5px; padding: 3px 4px; }}
  .table-wrap {{ max-height: calc(100vh - 200px); }}
}}
</style>
</head>
<body>
<header>
  <h1>North Shore Library Benefits — Wakefield Area</h1>
  <div class="sub">{LIB_COUNT} libraries · {BENEFIT_COUNT} attractions · {CELL_COUNT} discounts · researched {DATE} · <span id="refresh-status">availability refreshed <span id="refresh-age">…</span></span> <a class="refresh-btn" id="refresh-btn" href="refresh.command">🔄 Refresh now</a></div>
  <div class="controls">
    <label><input type="checkbox" id="kid-toggle" checked> Show only kid-friendly</label>
    <label><input type="checkbox" id="hide-residents-only" checked> Hide residents-only libraries</label>
    <label><input type="checkbox" id="walk-in-only"> Walk-in only (no second booking)</label>
    <label><input type="checkbox" id="digital-only"> Digital passes only (no library pickup)</label>
    <label>Sort:
      <select id="sort-mode" class="sort">
        <option value="category">By category</option>
        <option value="distance" selected>By drive time from Wakefield ↑ (default)</option>
        <option value="name">By attraction name (A→Z)</option>
      </select>
    </label>
    <div class="legend">
      <span><span class="swatch free"></span>Free</span>
      <span><span class="swatch half"></span>Half-price</span>
      <span><span class="swatch discount"></span>Discount</span>
      <span><span class="swatch price"></span>Reduced $</span>
      <span><span class="swatch empty"></span>Not offered</span>
    </div>
  </div>
  <div class="controls">
    <div class="legend">
      <span><span class="dot dot-open"></span>Open to any MA resident</span>
      <span><span class="dot dot-network"></span>Network only (MVLC/NOBLE/MLN)</span>
      <span><span class="dot dot-residents"></span>Town residents only</span>
      <span><span class="owned-badge" style="margin-right:4px">✓</span>You already have this card</span>
    </div>
  </div>
  <div class="controls">
    <div class="legend">
      <span title="Walk-in — show pass at door, no second booking">🚪 Walk-in</span>
      <span title="Reservation recommended — capacity-limited">📅 Reservation rec.</span>
      <span title="Reservation REQUIRED — must book on museum site">🎟️ Booking required</span>
      <span title="Promo code — book timed ticket on museum site with library code">🔑 Promo code</span>
      <span title="Timed tour — must arrive at scheduled slot">🕐 Timed tour</span>
      <span title="Seasonal — open only part of year">🌤️ Seasonal</span>
      <span title="★★ = Circulating physical pass — pick up + return by 10am next day. ★ = Coupon pickup, no return. (no star) = digital pass, emailed.">★★ pickup+return / ★ pickup-only / no-star digital</span>
    </div>
  </div>
</header>

<main>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="benefit-col">Attraction ↓ &nbsp; / &nbsp; Library →</th>
          {HEADERS}
        </tr>
      </thead>
      <tbody>
        {ROWS}
      </tbody>
    </table>
  </div>
</main>

<div class="modal-backdrop" id="cal-modal">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-header">
      <h2 class="modal-title" id="cal-title"></h2>
      <button class="modal-close" id="cal-close" aria-label="Close">×</button>
    </div>
    <div class="modal-sub" id="cal-sub"></div>
    <div class="cal" id="cal-grid"></div>
    <div class="modal-instructions">
      🟣 = BPL has it (best deal — usually free) · 🟢 = your other card has it · 🟡 = limited · ⚪ = available only at libraries you don't have · ⬛ = museum closed that day · 🔴 = booked everywhere · ▫ = no pass.<br>
      Click any green/yellow date — a popup shows which of your cards work, you pick one. The reservation page opens + card # copied to clipboard. Just <kbd>⌘V</kbd> in the barcode field. Hover any cell to see the per-library breakdown.
    </div>
    <div class="lib-picker" id="lib-picker">
      <div class="lib-picker-title" id="lib-picker-title"></div>
      <div class="lib-picker-buttons" id="lib-picker-buttons"></div>
      <button class="lib-picker-cancel" id="lib-picker-cancel">Cancel</button>
    </div>
  </div>
</div>
<div class="copy-toast" id="copy-toast"></div>

<footer>
  <strong>How to use:</strong> Click a cell to open that library's pass-reservation page in a new tab. Click an attraction name (left column) for the museum's site. Click a town header for the library's full pass list. Hover any cell for terms (party size, restrictions).
  <br><br>
  <strong>Important:</strong> Most libraries restrict pass <em>reservations</em> to their own town's residents — having a Wakefield card lets you reserve at Wakefield only. If you want a different library's passes, you usually need to walk in and get a card from that town (free for any MA resident in most cases).
  <br><br>
  <strong>Library notes:</strong>
  <ul>{LIB_LEGEND}</ul>
  <br>
  <span class="muted">Researched 2026-05-01. Pass offerings rotate seasonally — verify on the library's page before planning a trip.</span>
</footer>

<script>
  const AVAIL = {AVAIL_JSON};
  const CARDS = {CARDS_JSON};
  const SLUG_MAP = {SLUG_MAP_JSON};
  const LIB_DOMAIN = {LIB_DOMAIN_JSON};
  const LIB_PRIORITY = {LIB_PRIORITY_JSON};
  const OWNED_LIBS = {OWNED_LIBS_JSON};
  const BPL_PASS_ID = {BPL_PASS_ID_JSON};
  const BENEFIT_NAMES = {BENEFIT_NAMES_JSON};
  const BENEFIT_CLOSED = {BENEFIT_CLOSED_JSON};
  const SCRAPED_AT = "{SCRAPED_AT}";

  const modal = document.getElementById('cal-modal');
  const calTitle = document.getElementById('cal-title');
  const calSub = document.getElementById('cal-sub');
  const calGrid = document.getElementById('cal-grid');
  const calClose = document.getElementById('cal-close');
  const toast = document.getElementById('copy-toast');

  const DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  function fmtDate(d) {{
    return `${{d.getFullYear()}}-${{String(d.getMonth()+1).padStart(2,'0')}}-${{String(d.getDate()).padStart(2,'0')}}`;
  }}

  function showToast(msg) {{
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2400);
  }}

  function openModal(bid) {{
    const data = AVAIL[bid] || {{}};
    calTitle.textContent = BENEFIT_NAMES[bid] || bid;
    const scrapedDate = SCRAPED_AT.split('T')[0];
    calSub.textContent = `Availability across your 3 cards · refreshed ${{scrapedDate}}`;
    document.getElementById('lib-picker').classList.remove('open');
    renderCalendar(bid, data);
    modal.classList.add('open');
  }}

  function closeModal() {{
    modal.classList.remove('open');
  }}

  function renderCalendar(bid, data) {{
    calGrid.innerHTML = '';
    const today = new Date(); today.setHours(0,0,0,0);
    const start = new Date(today);
    const end = new Date(today); end.setDate(end.getDate() + 30);

    let cursorMonth = -1;
    let firstDow = start.getDay();

    for (let d = new Date(start); d <= end; d.setDate(d.getDate()+1)) {{
      const date = fmtDate(d);
      if (d.getMonth() !== cursorMonth) {{
        const hdr = document.createElement('div');
        hdr.className = 'cal-month-header';
        hdr.textContent = `${{MONTHS[d.getMonth()]}} ${{d.getFullYear()}}`;
        calGrid.appendChild(hdr);
        for (let i = 0; i < 7; i++) {{
          const lbl = document.createElement('div');
          lbl.className = 'cal-day-label';
          lbl.textContent = DAYS[i];
          calGrid.appendChild(lbl);
        }}
        for (let i = 0; i < d.getDay(); i++) {{
          const blank = document.createElement('div');
          blank.className = 'cal-cell empty';
          calGrid.appendChild(blank);
        }}
        cursorMonth = d.getMonth();
      }}

      const cell = document.createElement('div');
      cell.className = 'cal-cell';
      const info = data[date];
      const perLib = info ? info.p : {{}};

      const ownedSet = new Set(OWNED_LIBS);
      const bplAvail = perLib['bpl'] === 'available';
      const ownedAvail = OWNED_LIBS.filter(l => perLib[l] === 'available');
      const ownedLimited = OWNED_LIBS.filter(l => perLib[l] === 'limited');
      const otherAvail = Object.entries(perLib)
        .filter(([l,s]) => !ownedSet.has(l) && l !== 'bpl' && (s === 'available' || s === 'limited'))
        .map(([l]) => l);
      const anyBooked = Object.values(perLib).some(s => s === 'booked');

      let status = 'na';
      if (bplAvail) status = 'bpl-available';
      else if (ownedAvail.length > 0) status = 'available';
      else if (ownedLimited.length > 0) status = 'limited';
      else if (otherAvail.length > 0) status = 'others-only';
      else if (anyBooked) status = 'booked';

      const dayAbbr = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()];
      const closedDays = BENEFIT_CLOSED[bid] || [];
      const museumClosed = closedDays.includes(dayAbbr);
      if (museumClosed) status = 'museum-closed';

      cell.classList.add(status);

      const dayNum = document.createElement('div');
      dayNum.textContent = d.getDate();
      cell.appendChild(dayNum);

      const tag = document.createElement('div');
      tag.className = 'lib-tag';
      const goodOwned = [...ownedAvail, ...ownedLimited];
      if (status === 'museum-closed') {{
        tag.textContent = 'closed';
      }} else if (status === 'bpl-available') {{
        const extras = goodOwned.length;
        tag.textContent = extras > 0 ? `BPL +${{extras}}` : 'BPL';
      }} else if (status === 'available' || status === 'limited') {{
        tag.textContent = goodOwned.length === 1 ? goodOwned[0].slice(0,4) : `${{goodOwned.length}} libs`;
      }} else if (status === 'others-only') {{
        tag.textContent = otherAvail.length === 1 ? otherAvail[0].slice(0,4) : `${{otherAvail.length}} other`;
      }} else if (status === 'booked') {{
        tag.textContent = 'full';
      }}
      cell.appendChild(tag);

      const libsLine = Object.entries(perLib)
        .map(([lib,s]) => {{
          const own = ownedSet.has(lib) ? '✓' : '·';
          return `${{own}} ${{lib}}: ${{s}}`;
        }})
        .join('\\n');
      const closedPrefix = museumClosed
        ? `Museum closed ${{dayAbbr}}s — even if a library has a pass, you can't use it.\\n`
        : '';
      cell.title = closedPrefix + (libsLine || 'No data');

      if (!museumClosed && (bplAvail || ownedAvail.length > 0 || ownedLimited.length > 0)) {{
        cell.addEventListener('click', () => showLibPicker(bid, date, perLib));
      }}

      calGrid.appendChild(cell);
    }}
  }}

  const picker = document.getElementById('lib-picker');
  const pickerTitle = document.getElementById('lib-picker-title');
  const pickerButtons = document.getElementById('lib-picker-buttons');
  const pickerCancel = document.getElementById('lib-picker-cancel');

  function showLibPicker(bid, date, perLib) {{
    const dt = new Date(date + 'T00:00:00');
    const niceDate = dt.toLocaleDateString('en-US', {{ weekday: 'long', month: 'long', day: 'numeric' }});
    pickerTitle.textContent = `Pick which card to book ${{BENEFIT_NAMES[bid]}} on ${{niceDate}}:`;
    pickerButtons.innerHTML = '';
    // BPL first when available — usually the best deal
    if (perLib['bpl'] === 'available' && BPL_PASS_ID[bid]) {{
      const btn = document.createElement('button');
      btn.className = 'lib-pick-btn bpl';
      const card = (CARDS['bpl'] || {{}}).barcode || '';
      const cardEnd = card ? '••••' + card.slice(-4) : '';
      btn.innerHTML = `BPL card ${{cardEnd}}<span class="pick-status">best deal · usually free</span>`;
      btn.addEventListener('click', () => {{
        picker.classList.remove('open');
        bookDate(bid, 'bpl', date);
      }});
      pickerButtons.appendChild(btn);
    }}
    OWNED_LIBS.forEach(libId => {{
      const status = perLib[libId];
      if (status !== 'available' && status !== 'limited') return;
      const btn = document.createElement('button');
      btn.className = 'lib-pick-btn' + (status === 'limited' ? ' limited' : '');
      const card = (CARDS[libId] || {{}}).barcode || '';
      const cardEnd = card ? '••••' + card.slice(-4) : '';
      btn.innerHTML = `${{libId.charAt(0).toUpperCase() + libId.slice(1)}} card ${{cardEnd}}<span class="pick-status">${{status}}</span>`;
      btn.addEventListener('click', () => {{
        picker.classList.remove('open');
        bookDate(bid, libId, date);
      }});
      pickerButtons.appendChild(btn);
    }});
    picker.classList.add('open');
    picker.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }}

  pickerCancel.addEventListener('click', () => picker.classList.remove('open'));

  const MONTH_SLUG = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];

  function bookDate(bid, libId, date) {{
    let url;
    const card = (CARDS[libId] || {{}}).barcode || '';
    if (libId === 'bpl') {{
      const passId = BPL_PASS_ID[bid];
      if (!passId) return;
      url = `https://bpl.libcal.com/passes/${{passId}}`;
    }} else {{
      const slug = (SLUG_MAP[bid] || {{}})[libId];
      if (!slug) return;
      const domain = LIB_DOMAIN[libId];
      const [yyyy, mm, dd] = date.split('-');
      const monthSlug = `${{yyyy}}-${{MONTH_SLUG[parseInt(mm,10)-1]}}`;
      url = `https://${{domain}}/museum-passes/by-date/${{monthSlug}}/${{dd}}/${{slug}}/`;
    }}
    if (card && navigator.clipboard) {{
      navigator.clipboard.writeText(card).then(() => {{
        showToast(`📋 ${{libId}} card copied · opening reservation...`);
      }}, () => {{
        showToast(`Opening ${{libId}} reservation (clipboard blocked, card: ${{card}})`);
      }});
    }} else {{
      showToast(`Opening ${{libId}} reservation`);
    }}
    setTimeout(() => window.open(url, '_blank', 'noopener'), 250);
  }}

  document.addEventListener('click', e => {{
    const btn = e.target.closest('.book-btn');
    if (btn) {{
      e.preventDefault();
      openModal(btn.dataset.bid);
    }}
  }});
  calClose.addEventListener('click', closeModal);
  modal.addEventListener('click', e => {{ if (e.target === modal) closeModal(); }});
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

  const toggle = document.getElementById('kid-toggle');
  toggle.addEventListener('change', () => {{
    document.body.classList.toggle('kid-only', toggle.checked);
  }});
  document.body.classList.toggle('kid-only', toggle.checked);

  const hideResToggle = document.getElementById('hide-residents-only');
  function applyHideRes() {{
    document.body.classList.toggle('hide-residents-only', hideResToggle.checked);
  }}
  hideResToggle.addEventListener('change', applyHideRes);
  applyHideRes();

  const walkInToggle = document.getElementById('walk-in-only');
  walkInToggle.addEventListener('change', () => {{
    document.body.classList.toggle('walk-in-only', walkInToggle.checked);
  }});

  const digitalOnlyToggle = document.getElementById('digital-only');
  digitalOnlyToggle.addEventListener('change', () => {{
    document.body.classList.toggle('digital-only', digitalOnlyToggle.checked);
  }});

  const TODAY_ABBR = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][new Date().getDay()];
  document.querySelectorAll('tr.row').forEach(r => {{
    const closed = (r.dataset.closed || '').split(',').filter(Boolean);
    if (closed.includes(TODAY_ABBR)) r.classList.add('closed-today');
  }});

  if (SCRAPED_AT) {{
    const scraped = new Date(SCRAPED_AT);
    const ageMs = Date.now() - scraped.getTime();
    const hours = Math.floor(ageMs / 3600000);
    const days = Math.floor(hours / 24);
    let label;
    if (hours < 1) label = 'just now';
    else if (hours < 24) label = `${{hours}}h ago`;
    else label = `${{days}}d ago`;
    document.getElementById('refresh-age').textContent = label;
    if (hours >= 24) document.getElementById('refresh-status').classList.add('stale');
  }}

  const sortMode = document.getElementById('sort-mode');
  const tbody = document.querySelector('tbody');
  const originalRows = Array.from(tbody.children);

  function rebuild(mode) {{
    tbody.innerHTML = '';
    if (mode === 'category') {{
      originalRows.forEach(r => tbody.appendChild(r));
      return;
    }}
    const dataRows = originalRows.filter(r => r.classList.contains('row'));
    let sorted;
    if (mode === 'distance') {{
      sorted = dataRows.slice().sort((a, b) =>
        parseInt(a.dataset.mins) - parseInt(b.dataset.mins) ||
        a.dataset.name.localeCompare(b.dataset.name)
      );
    }} else {{
      sorted = dataRows.slice().sort((a, b) =>
        a.dataset.name.localeCompare(b.dataset.name)
      );
    }}
    sorted.forEach(r => tbody.appendChild(r));
  }}

  sortMode.addEventListener('change', () => rebuild(sortMode.value));
  if (sortMode.value !== 'category') rebuild(sortMode.value);
</script>
</body>
</html>
"""

(ROOT / "library-benefits.html").write_text(HTML_DOC)
print(f"wrote library-benefits.html ({len(HTML_DOC):,} bytes)")
