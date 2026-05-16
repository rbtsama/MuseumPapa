"""Build a static HTML audit site under audit/.

Reads data/structured/* and data/raw/* and produces 8 self-contained HTML pages
for a non-technical auditor. No build step on the auditor side — they open
audit/index.html in a browser.

Run from project root:
    python scripts/build_audit_site.py
"""
from __future__ import annotations

import html
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRUCT = ROOT / "data" / "structured"
RAW = ROOT / "data" / "raw"
WEB_IMG = ROOT / "web" / "public" / "images"
OUT = ROOT / "audit"
ASSETS = OUT / "assets"

# ---------- Label maps (must match web/src/lib/discount-display.ts) ----------
ELIG_LABEL = {
    "vehicle": "per vehicle",
    "adults_only": "adults only",
    "children_only": "kids only",
    "single_ticket": "1 ticket",
    "members_free": "members free",
    "seniors_free": "seniors free",
    "students_only": "students only",
    "military_free": "military free",
    "educator_free": "educators free",
    "family": "family pass",
    "groups": "group rate",
    "residents_only": "residents only",
    "all": "open to all",
}
EXCL_LABEL = {
    "weekdays_only": "weekdays only",
    "weekends_only": "weekends only",
    "weekends_excluded": "no weekends",
    "blackout_dates": "some dates excluded",
    "reservation_required": "reservation needed",
    "id_required": "ID at gate",
    "residents_only": "residents only",
}
BOOST_LABEL = {
    "ebt_discount": "EBT discount",
    "snap_free": "SNAP free",
    "library_card_required": "library card required",
    "members_discount": "members discount",
    "gift_shop_discount": "gift shop discount",
}

# Eligibility semantic group
ELIG_GROUP = {
    "all": "default",
    "vehicle": "structural",
    "single_ticket": "structural",
    "family": "structural",
    "groups": "structural",
    "residents_only": "structural",
    "adults_only": "audience",
    "children_only": "audience",
    "seniors_free": "free-group",
    "students_only": "free-group",
    "military_free": "free-group",
    "educator_free": "free-group",
    "members_free": "free-group",
}

OWN_CARDS = {"wakefield", "reading", "bpl", "wilmington", "somerville"}

KNOWN_DUPLICATES = [
    ("mfa", "museum-of-fine-arts"),
    ("ica-boston", "institute-of-contemporary-art-boston"),
    ("jfk-library", "john-f-kennedy-library-and-museum"),
    ("trustees-of-reservations", "the-trustees-of-the-reservations"),
    ("plimoth-patuxet", "plimoth-patuxet-museums"),
    ("american-rep-theater", "american-repertory-theater"),
    ("ma-state-parks", "massachusetts-state-parks-department-of-conservation-and-recreation"),
    ("butterfly-place", "the-butterfly-place"),
]

# ---------- Helpers ----------

def esc(s) -> str:
    if s is None:
        return ""
    return html.escape(str(s), quote=True)


def load_json(p: Path):
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def find_local_image(slug: str) -> str | None:
    """Return relative path to image under audit/ (../web/public/images/..) or None."""
    if not WEB_IMG.exists():
        return None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = WEB_IMG / f"{slug}{ext}"
        if p.exists():
            return f"../web/public/images/{slug}{ext}"
    return None


def read_raw(subdir: str, name: str) -> dict | None:
    p = RAW / subdir / f"{name}.json"
    if not p.exists():
        return None
    try:
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------- Source-phrase highlighting ----------

def highlight_raw(raw: str, source_phrases: dict | None) -> tuple[str, list[tuple[str, str, int]]]:
    """Return (html_with_marks, list of (field, phrase, idx)).

    Source phrases may be None or missing or not actually present in raw text.
    Only ones found get superscripts; others still listed at idx=0 (no mark).
    """
    if not raw:
        return "", []
    raw_text = raw
    found = []  # list of (field, phrase, idx_or_None)
    spans = []  # (start, end, idx, field)
    idx = 0
    if source_phrases:
        for field, phrase in source_phrases.items():
            if not phrase:
                found.append((field, phrase, None))
                continue
            # case-insensitive substring search
            lower_raw = raw_text.lower()
            lower_phrase = str(phrase).lower()
            pos = lower_raw.find(lower_phrase)
            if pos < 0:
                found.append((field, phrase, None))
                continue
            idx += 1
            end = pos + len(phrase)
            spans.append((pos, end, idx, field))
            found.append((field, phrase, idx))
    # Sort spans by start
    spans.sort()
    # Merge: drop overlaps (keep earlier)
    cleaned = []
    last_end = -1
    for s, e, i, f in spans:
        if s < last_end:
            continue
        cleaned.append((s, e, i, f))
        last_end = e
    # Build HTML
    out = []
    cursor = 0
    for s, e, i, _f in cleaned:
        out.append(esc(raw_text[cursor:s]))
        color_cls = f"src-{((i - 1) % 6) + 1}"
        out.append(f'<mark class="{color_cls}">{esc(raw_text[s:e])}<sup>{i}</sup></mark>')
        cursor = e
    out.append(esc(raw_text[cursor:]))
    return "".join(out), found


# ---------- Pattern clustering ----------

def signature(pass_obj: dict) -> tuple:
    pol = pass_obj.get("policy") or {}
    dc = pass_obj.get("discount", {}).get("class", "unknown")
    tags = pol.get("eligibility_tags") or []
    primary = None
    for t in tags:
        if t != "all":
            primary = t
            break
    if primary is None and "all" in tags:
        primary = "all"
    has_cap = bool(pol.get("max_people") or pol.get("max_adults") or pol.get("max_children"))
    has_under = pol.get("free_under_age") is not None
    has_per_person = pol.get("savings_per_person_usd") is not None
    has_excl = bool(pol.get("exclusions"))
    return (dc, primary, has_cap, has_under, has_per_person, has_excl)


DISCOUNT_LABEL_EN = {
    "free": "Free admission",
    "half": "Half-price",
    "percent-off": "Percent off",
    "dollar-off": "Dollar off",
    "price": "Fixed price",
    "discount": "Discount",
    "unknown": "Unspecified discount",
}
DISCOUNT_LABEL_ZH = {
    "free": "免费",
    "half": "半价",
    "percent-off": "百分比折扣",
    "dollar-off": "立减金额",
    "price": "固定价格",
    "discount": "折扣",
    "unknown": "未明示折扣",
}


def signature_name(sig: tuple) -> tuple[str, str]:
    dc, primary, has_cap, has_under, has_per, has_excl = sig
    en_parts = [DISCOUNT_LABEL_EN.get(dc, dc)]
    zh_parts = [DISCOUNT_LABEL_ZH.get(dc, dc)]
    if has_cap:
        en_parts.append("admits up to N")
        zh_parts.append("上限 N 人")
    if has_under:
        en_parts.append("kids under age free")
        zh_parts.append("低龄儿童免费")
    if has_per:
        en_parts.append("per-person savings")
        zh_parts.append("按人折扣")
    if primary:
        lab = ELIG_LABEL.get(primary, primary)
        en_parts.append(lab)
        zh_parts.append(lab)
    if has_excl:
        en_parts.append("with restrictions")
        zh_parts.append("含限制")
    return " · ".join(en_parts), " · ".join(zh_parts)


# ---------- Badges ----------

def badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{esc(text)}</span>'


def discount_badge(d: dict) -> str:
    cls = d.get("class", "unknown")
    label = d.get("label") or DISCOUNT_LABEL_EN.get(cls, cls)
    glyph = {"free": "■", "half": "▣", "percent-off": "%", "dollar-off": "$", "price": "$$", "discount": "◇"}.get(cls, "·")
    return f'<span class="badge badge-disc-{cls}">{esc(glyph)} {esc(label)}</span>'


def pass_type_badge(pt: str) -> str:
    return f'<span class="badge badge-pt-{esc(pt)}">{esc(pt)}</span>'


def elig_badges(tags: list[str]) -> str:
    out = []
    for t in tags or []:
        grp = ELIG_GROUP.get(t, "structural")
        lab = ELIG_LABEL.get(t, t)
        out.append(f'<span class="badge badge-elig-{grp}">{esc(lab)}</span>')
    return "".join(out)


def excl_badges(tags: list[str]) -> str:
    out = []
    for t in tags or []:
        if t.startswith("seasonal:"):
            rng = t.split(":", 1)[1]
            out.append(f'<span class="badge badge-seasonal">Open {esc(rng)}</span>')
        else:
            lab = EXCL_LABEL.get(t, t)
            out.append(f'<span class="badge badge-excl">{esc(lab)}</span>')
    return "".join(out)


def boost_badges(tags: list[str]) -> str:
    out = []
    for t in tags or []:
        lab = BOOST_LABEL.get(t, t)
        out.append(f'<span class="badge badge-boost">{esc(lab)}</span>')
    return "".join(out)


# ---------- Page chrome ----------

NAV_LINKS = [
    ("index.html", "Overview"),
    ("libraries.html", "Libraries"),
    ("attractions.html", "Attractions"),
    ("policies.html", "Policies"),
    ("gaps.html", "Gaps"),
    ("duplicates.html", "Duplicates"),
    ("lineage.html", "Lineage"),
    ("schema.html", "Schema"),
]


def page_shell(title: str, body: str, current: str, extra_head: str = "", data_blob: str = "") -> str:
    nav = " · ".join(
        f'<a href="{href}" class="{"current" if href == current else ""}">{label}</a>'
        for href, label in NAV_LINKS
    )
    blob = f'<script id="data-blob" type="application/json">{data_blob}</script>' if data_blob else ""
    return f"""<!doctype html>
<html lang="zh"><head>
<meta charset="utf-8">
<title>{esc(title)} — MuseumPapa Audit</title>
<link rel="stylesheet" href="assets/style.css">
{extra_head}
</head><body>
<header class="site-head">
  <div class="brand"><span class="font-serif">MuseumPapa</span> · Data Audit</div>
  <nav class="topnav">{nav}</nav>
</header>
<main>
{body}
</main>
<div id="modal-root" class="modal-root hidden"><div class="modal-backdrop"></div><div class="modal-box"><button class="modal-close" type="button">×</button><div class="modal-body"></div></div></div>
{blob}
<script src="assets/audit.js"></script>
</body></html>
"""


# =========================================================================
# PAGE 1 — index.html
# =========================================================================

def page_index(libs_data, attr_data, passes_data, libcat) -> str:
    libs = libs_data["libraries"]
    attrs = attr_data["attractions"]
    passes = passes_data["passes"]

    n_libs = len(libs)
    n_attrs = len(attrs)
    n_passes = len(passes)

    # coverage stats
    lib_cov = {
        "street address": sum(1 for L in libs if (L.get("address") or {}).get("street")),
        "geo lat/lon": sum(1 for L in libs if L.get("geo")),
        "residency eligibility": sum(1 for L in libs if L.get("eligibility")),
        "card_page url": sum(1 for L in libs if L.get("card_page")),
    }
    attr_cov = {
        "hero image": sum(1 for A in attrs if (A.get("hero_image") or {}).get("local_path")),
        "price (any)": sum(1 for A in attrs if A.get("original_price")),
        "hours": sum(1 for A in attrs if A.get("hours")),
        "description": sum(1 for A in attrs if A.get("description")),
        "phone": sum(1 for A in attrs if A.get("phone")),
        "geo": sum(1 for A in attrs if A.get("geo")),
    }
    pass_cov = {
        "policy present": sum(1 for p in passes if p.get("policy")),
        "discount classified": sum(1 for p in passes if p.get("discount", {}).get("class") not in (None, "unknown")),
        "pass_type known": sum(1 for p in passes if p.get("pass_type") not in (None, "unknown")),
        "availability data": sum(1 for p in passes if p.get("availability")),
    }

    tag_counter = Counter()
    excl_counter = Counter()
    for p in passes:
        pol = p.get("policy") or {}
        for t in pol.get("eligibility_tags") or []:
            tag_counter[t] += 1
        for t in pol.get("exclusions") or []:
            excl_counter[t] += 1

    def coverage_list(cov: dict, total: int) -> str:
        rows = []
        for k, v in cov.items():
            pct = round(100 * v / total) if total else 0
            rows.append(f'<li><span class="cov-label">{esc(k)}</span><span class="cov-frac">{v}/{total}</span><span class="cov-pct">{pct}%</span></li>')
        return f'<ul class="coverage">{"".join(rows)}</ul>'

    def histogram(counter: Counter, label_map: dict, total: int) -> str:
        rows = []
        most = counter.most_common()
        max_n = most[0][1] if most else 1
        for key, n in most:
            lab = label_map.get(key, key) if not key.startswith("seasonal:") else f"Open {key.split(':',1)[1]}"
            bar_w = round(40 * n / max_n)
            pct = round(100 * n / total) if total else 0
            rows.append(f'<tr><td>{esc(lab)}</td><td class="bar-cell"><span class="bar">{"█"*bar_w}</span></td><td class="num">{n}</td><td class="pct">{pct}%</td></tr>')
        return f'<table class="histogram">{"".join(rows)}</table>'

    plat_counter = Counter(libcat["libraries"][lid]["platform"] for lid in libcat["libraries"])

    anomalies = []
    # passes with raw text but no source_phrases
    n_no_src = 0
    n_unexpl_null = 0
    for p in passes:
        pol = p.get("policy") or {}
        raw = pol.get("raw") or p.get("discount", {}).get("raw") or ""
        sp = None
        rp = read_raw("pass_policies", f"{p['library_id']}_{p['attraction_slug']}")
        if rp:
            sp = rp.get("source_phrases")
        if raw and (not sp):
            n_no_src += 1
        if pol.get("max_people") is None and pol.get("discount_percent") is None and not (pol.get("eligibility_tags") or []) and raw:
            n_unexpl_null += 1
    anomalies.append(f"<li>{n_no_src} passes with raw text but no extracted source_phrases — <a href='policies.html'>see Policies</a></li>")
    anomalies.append(f"<li>{n_unexpl_null} passes with raw text but no extracted policy fields</li>")
    n_unknown_pt = sum(1 for p in passes if p.get("pass_type") == "unknown")
    anomalies.append(f"<li>{n_unknown_pt} passes with pass_type = unknown</li>")
    n_dup = len(KNOWN_DUPLICATES)
    anomalies.append(f"<li>{n_dup} duplicate attraction slug pairs — <a href='duplicates.html'>see Duplicates</a></li>")
    n_missing_price = n_attrs - attr_cov["price (any)"]
    anomalies.append(f"<li>{n_missing_price} attractions missing price data — <a href='gaps.html'>see Gaps</a></li>")
    n_missing_desc = n_attrs - attr_cov["description"]
    anomalies.append(f"<li>{n_missing_desc} attractions missing description</li>")

    body = f"""
<h1 class="page-title">MuseumPapa <span class="font-serif">数据审计 Data Audit</span></h1>
<p class="subtitle">Non-technical verification view of the structured dataset behind the MuseumPapa frontend.</p>

<section class="cards-row">
  <div class="num-card"><div class="num">{n_libs}</div><div class="label">Libraries 图书馆</div></div>
  <div class="num-card"><div class="num">{n_attrs}</div><div class="label">Attractions 景点</div></div>
  <div class="num-card"><div class="num">{n_passes}</div><div class="label">Passes 优惠</div></div>
</section>

<section class="grid-3">
  <div class="panel"><h3>Libraries coverage</h3>{coverage_list(lib_cov, n_libs)}</div>
  <div class="panel"><h3>Attractions coverage</h3>{coverage_list(attr_cov, n_attrs)}</div>
  <div class="panel"><h3>Passes coverage</h3>{coverage_list(pass_cov, n_passes)}</div>
</section>

<section class="panel">
  <h3>Eligibility tags · histogram</h3>
  {histogram(tag_counter, ELIG_LABEL, n_passes)}
</section>

<section class="panel">
  <h3>Restrictions · histogram</h3>
  {histogram(excl_counter, EXCL_LABEL, n_passes)}
</section>

<section class="panel">
  <h3>Platform distribution</h3>
  <ul class="platform-row">
    <li><b>Assabet</b> <span class="num">{plat_counter.get('assabet', 0)}</span> libraries</li>
    <li><b>LibCal</b> <span class="num">{plat_counter.get('libcal', 0)}</span> libraries</li>
    <li><b>MuseumKey</b> <span class="num">{plat_counter.get('museumkey', 0)}</span> libraries</li>
  </ul>
</section>

<section class="panel">
  <h3>异常 Top 信号 · Anomalies</h3>
  <ul class="anomaly-list">{"".join(anomalies)}</ul>
</section>

<footer class="page-foot">
  Built {esc(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))} ·
  <a href="#" class="view-json-link" data-json-key="meta">View JSON of dataset summary</a>
</footer>
"""
    blob = json.dumps({
        "meta": {
            "libraries": libs_data.get("_meta"),
            "attractions": attr_data.get("_meta"),
            "passes": passes_data.get("_meta"),
            "library_catalog": libcat.get("_meta"),
        }
    }, ensure_ascii=False)
    return page_shell("Overview", body, "index.html", data_blob=blob)


# =========================================================================
# PAGE 2 — libraries.html
# =========================================================================

def page_libraries(libs_data) -> str:
    libs = libs_data["libraries"]
    rows = []
    for L in libs:
        own = "★" if L["id"] in OWN_CARDS else ""
        addr = L.get("address") or {}
        residency = esc(L.get("eligibility") or "")
        card_link = ""
        if L.get("card_page"):
            card_link = f'<a href="{esc(L["card_page"])}" target="_blank" rel="noopener">↗</a>'
        n_passes = "—"  # filled later if catalog passed
        rows.append(f"""<tr data-search="{esc((L['id']+' '+L['name']+' '+L.get('town','')+' '+L.get('network','')).lower())}">
  <td class="mono">{esc(L['id'])}</td>
  <td>{esc(L['name'])}</td>
  <td>{esc(L.get('town',''))}</td>
  <td>{esc(L.get('network',''))}</td>
  <td><span class="badge badge-plat-{esc(L.get('platform',''))}">{esc(L.get('platform',''))}</span></td>
  <td class="truncate">{residency}</td>
  <td class="own">{own}</td>
  <td>{card_link}</td>
</tr>""")
    body = f"""
<h1 class="page-title">Libraries · 59</h1>
<p>Row marked <b>★</b> indicates one of the 5 operator-owned cards (Wakefield / Reading / BPL / Wilmington / Somerville).</p>
<div class="toolbar"><input type="search" class="search-box" placeholder="filter rows... (id / name / town / network)" data-target="libs-table"></div>
<table id="libs-table" class="data-table">
<thead><tr><th>id</th><th>name</th><th>town</th><th>network</th><th>platform</th><th>residency</th><th>own</th><th>card page</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
<p class="foot-link"><a href="#" class="view-json-link" data-json-key="libraries">View full libraries.json</a></p>
"""
    blob = json.dumps({"libraries": libs_data}, ensure_ascii=False)
    return page_shell("Libraries", body, "libraries.html", data_blob=blob)


# =========================================================================
# PAGE 3 — attractions.html
# =========================================================================

def page_attractions(attr_data) -> str:
    attrs = attr_data["attractions"]
    slug_counts = Counter(A["slug"] for A in attrs)
    all_cats = sorted({c for A in attrs for c in (A.get("categories") or [])})

    rows = []
    missing_image = []
    for A in attrs:
        slug = A["slug"]
        price = A.get("original_price") or {}
        hours = A.get("hours") or {}
        rh = hours.get("regular_hours") or {}
        img_path = find_local_image(slug)
        if not img_path:
            missing_image.append(slug)
        img_html = f'<img class="hero-thumb" src="{esc(img_path)}" alt="" data-full="{esc(img_path)}">' if img_path else '<div class="hero-thumb noimg">—</div>'

        sources = A.get("sources") or []
        n_libs = len(sources)

        dup_warn = ""
        if slug_counts[slug] > 1:
            dup_warn = '<span class="warn">⚠ duplicate slug</span>'

        cats_html = "".join(f'<span class="badge badge-cat">{esc(c)}</span>' for c in (A.get("categories") or []))

        # Prices
        price_cells = []
        for k, label in [("adult", "Adult"), ("child", "Child"), ("youth", "Youth"),
                         ("senior", "Senior"), ("student", "Student"), ("military", "Military"),
                         ("educator", "Educator"), ("family", "Family")]:
            v = price.get(k) if price else None
            if v is None:
                price_cells.append(f'<span class="price-cell honest-gap">{label} —</span>')
            else:
                vstr = f"${v}"
                src_link = ""
                if price and price.get("source_url"):
                    src_link = f' <a href="{esc(price["source_url"])}" target="_blank" rel="noopener">↗</a>'
                price_cells.append(f'<span class="price-cell verified">{label} {esc(vstr)}{src_link}</span>')
        fua = price.get("free_under_age") if price else None
        if fua is not None:
            price_cells.append(f'<span class="price-cell verified">free under {fua}</span>')

        # Hours
        day_keys = [("mon", "M"), ("tue", "T"), ("wed", "W"), ("thu", "Th"),
                    ("fri", "F"), ("sat", "S"), ("sun", "Su")]
        hour_cells = []
        for k, lab in day_keys:
            v = rh.get(k) or "—"
            v_compact = v.replace(" ", "").replace("AM", "a").replace("PM", "p").replace("–", "-")
            hour_cells.append(f'<span class="hr-cell">{lab} {esc(v_compact)}</span>')
        hours_status = hours.get("status") or "—"

        desc = A.get("description") or ""
        desc_trunc = (desc[:140] + "…") if len(desc) > 140 else desc

        phone = A.get("phone") or ""
        geo = A.get("geo") or {}
        geo_txt = f"{geo.get('lat'):.4f},{geo.get('lon'):.4f}" if geo.get("lat") else "—"

        sources_str = ", ".join(sources)

        search_text = (slug + " " + (A.get("museum_name") or "") + " " + " ".join(A.get("categories") or [])).lower()

        rows.append(f"""<article class="attr-row" data-search="{esc(search_text)}" data-categories="{esc(','.join(A.get('categories') or []))}">
  <div class="attr-head">
    {img_html}
    <div class="attr-title">
      <code class="slug">{esc(slug)}</code>
      <span class="attr-name">{esc(A.get('museum_name') or '')}</span>
      {cats_html}
      <span class="n-libs">{n_libs} libs offer</span>
      {dup_warn}
    </div>
  </div>
  <div class="attr-prices"><b>Prices:</b> {"".join(price_cells)}</div>
  <div class="attr-hours"><b>Hours:</b> {"".join(hour_cells)} <span class="meta">({esc(hours_status)})</span></div>
  <div class="attr-info"><b>Info:</b>
    {f'<span>📞 <a href="tel:{esc(phone)}">{esc(phone)}</a></span>' if phone else '<span class="honest-gap">📞 —</span>'}
    <span>🗺 {esc(geo_txt)}</span>
    <span class="desc">📝 {esc(desc_trunc)}</span>
  </div>
  <div class="attr-srcs"><b>Offered by:</b> <span class="lib-list">{esc(sources_str)}</span></div>
</article>""")

    cat_options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in all_cats)
    body = f"""
<h1 class="page-title">Attractions · {len(attrs)}</h1>
<div class="toolbar">
  <input type="search" class="search-box" placeholder="filter (slug / name / category)..." data-target="attr-list">
  <select class="filter-select" data-target="attr-list" data-filter-attr="data-categories">
    <option value="">All categories</option>
    {cat_options}
  </select>
</div>
<div id="attr-list" class="attr-list">{"".join(rows)}</div>
"""
    return page_shell("Attractions", body, "attractions.html"), missing_image


# =========================================================================
# PAGE 4 — policies.html
# =========================================================================

def page_policies(passes_data, libs_data, attr_data) -> str:
    passes = passes_data["passes"]
    # Compute signatures, take top 15 by frequency, rest = P16 Other
    sigs = Counter(signature(p) for p in passes if p.get("policy"))
    top = sigs.most_common(15)
    sig_to_pid = {sig: f"P{i+1}" for i, (sig, _) in enumerate(top)}

    # Group passes by pid
    by_pid: dict[str, list] = defaultdict(list)
    for p in passes:
        if not p.get("policy"):
            by_pid["P16"].append(p)
            continue
        sig = signature(p)
        pid = sig_to_pid.get(sig, "P16")
        by_pid[pid].append(p)

    # Build pattern metadata
    pattern_meta = []
    for i, (sig, n) in enumerate(top):
        en, zh = signature_name(sig)
        pattern_meta.append((f"P{i+1}", en, zh, n))
    if "P16" in by_pid:
        pattern_meta.append(("P16", "Other / Long-tail patterns", "其它 / 长尾", len(by_pid["P16"])))

    # TOC
    toc_items = "".join(
        f'<a href="#{pid}" class="toc-item">{pid}<br><small>{esc(en)}</small><span class="toc-n">{n}</span></a>'
        for pid, en, zh, n in pattern_meta
    )

    def render_pass_article(p: dict, idx: int) -> str:
        lib = p["library_id"]
        slug = p["attraction_slug"]
        pol = p.get("policy") or {}
        raw = pol.get("raw") or p.get("discount", {}).get("raw") or ""
        rp = read_raw("pass_policies", f"{lib}_{slug}") or {}
        src_phrases = rp.get("source_phrases") or {}
        marked, found = highlight_raw(raw, src_phrases)

        # Extracted line
        ext_parts = []
        field_to_idx = {f: i for f, _, i in found if i}
        for fname in ("max_people", "max_adults", "max_children", "free_under_age",
                      "discount_percent", "discount_dollar_off", "savings_per_person_usd"):
            val = pol.get(fname)
            if val is None:
                continue
            sup = f' ↩<sup>{field_to_idx[fname]}</sup>' if fname in field_to_idx else ""
            ext_parts.append(f'<span class="ext">{esc(fname)} <b>{esc(val)}</b>{sup}</span>')

        tags_b = elig_badges(pol.get("eligibility_tags") or [])
        excl_b = excl_badges(pol.get("exclusions") or [])
        boost_b = boost_badges(pol.get("boosts") or [])

        src_link = ""
        if p.get("source_url"):
            src_link = f'<a href="{esc(p["source_url"])}" target="_blank" rel="noopener">↗ source</a>'

        json_key = f"pol_{lib}_{slug}"

        return f"""<article class="policy-row" data-search="{esc((lib+' '+slug+' '+raw).lower()[:400])}">
  <header>
    <span class="lib-arrow-slug"><b>{esc(lib)}</b> → <code>{esc(slug)}</code></span>
    {pass_type_badge(p.get("pass_type", "unknown"))}
    {discount_badge(p.get("discount") or {})}
    {tags_b}{excl_b}{boost_b}
  </header>
  <p class="raw">{marked or '<i class="honest-gap">(no raw text)</i>'}</p>
  {"<p class='extracted'>"+ " · ".join(ext_parts) +"</p>" if ext_parts else ""}
  <p class="src-link">{src_link} {('· <a href="#" class="view-json-link" data-json-key="'+json_key+'">JSON</a>') if rp else ''}</p>
</article>"""

    # Build sections (By Pattern view)
    pattern_sections = []
    for pid, en, zh, n in pattern_meta:
        rows = "".join(render_pass_article(p, i) for i, p in enumerate(by_pid.get(pid, [])))
        pct = round(100 * n / len(passes))
        pattern_sections.append(f"""<section class="pattern-section" id="{pid}">
  <h2 class="pattern-header">{pid} — {esc(en)} <span class="pattern-zh">{esc(zh)}</span>
    <span class="pattern-meta">{n} passes ({pct}%)</span></h2>
  <div class="pattern-rows">{rows}</div>
</section>""")

    # By Attraction view
    by_attr: dict[str, list] = defaultdict(list)
    for p in passes:
        by_attr[p["attraction_slug"]].append(p)
    attr_sections = []
    for slug in sorted(by_attr.keys()):
        plist = by_attr[slug]
        rows = "".join(render_pass_article(p, i) for i, p in enumerate(plist))
        attr_sections.append(f'<section class="pattern-section" id="A_{esc(slug)}"><h2 class="pattern-header"><code>{esc(slug)}</code> <span class="pattern-meta">{len(plist)} passes</span></h2><div class="pattern-rows">{rows}</div></section>')

    # By Library view
    by_lib: dict[str, list] = defaultdict(list)
    for p in passes:
        by_lib[p["library_id"]].append(p)
    lib_sections = []
    for lid in sorted(by_lib.keys()):
        plist = by_lib[lid]
        rows = "".join(render_pass_article(p, i) for i, p in enumerate(plist))
        lib_sections.append(f'<section class="pattern-section" id="L_{esc(lid)}"><h2 class="pattern-header"><b>{esc(lid)}</b> <span class="pattern-meta">{len(plist)} passes</span></h2><div class="pattern-rows">{rows}</div></section>')

    body = f"""
<h1 class="page-title">Policies · 1008 passes · {len(pattern_meta)} patterns</h1>

<div class="policies-toolbar">
  <div class="tab-row">
    <button class="tab active" data-tab="tab-pattern">By Pattern · 按模式</button>
    <button class="tab" data-tab="tab-attraction">By Attraction · 按景点</button>
    <button class="tab" data-tab="tab-library">By Library · 按图书馆</button>
  </div>
  <input type="search" class="search-box" placeholder="filter within current tab..." data-target="policies-active">
</div>

<nav class="toc" id="pattern-toc">{toc_items}</nav>

<div id="tab-pattern" class="tab-panel active">{"".join(pattern_sections)}</div>
<div id="tab-attraction" class="tab-panel">{"".join(attr_sections)}</div>
<div id="tab-library" class="tab-panel">{"".join(lib_sections)}</div>
"""

    # Build minimal data blob: per-pass policy raw JSON, key="pol_<lib>_<slug>"
    blob_d = {}
    for p in passes:
        rp = read_raw("pass_policies", f"{p['library_id']}_{p['attraction_slug']}")
        if rp:
            blob_d[f"pol_{p['library_id']}_{p['attraction_slug']}"] = rp
    blob = json.dumps(blob_d, ensure_ascii=False)
    return page_shell("Policies", body, "policies.html", data_blob=blob), len(pattern_meta)


# =========================================================================
# PAGE 5 — gaps.html
# =========================================================================

def page_gaps(attr_data, libs_data) -> str:
    attrs = attr_data["attractions"]
    slug_counts = Counter(A["slug"] for A in attrs)

    sections = defaultdict(list)
    for A in attrs:
        slug = A["slug"]
        name = A.get("museum_name") or ""
        if not A.get("original_price"):
            sections["Missing price data"].append((slug, name, "no price extracted (theater / event-priced / blocked / 403)"))
        if not A.get("description"):
            sections["Missing description"].append((slug, name, "no description extracted"))
        if not A.get("phone"):
            sections["Missing phone"].append((slug, name, "no phone extracted"))
        if not A.get("geo"):
            sections["Geo geocode failure"].append((slug, name, "no lat/lon"))
        if (A.get("hours") or {}).get("status") and (A.get("hours") or {})["status"] != "ok":
            sections["Hours vary by location / season"].append((slug, name, (A.get("hours") or {}).get("status")))
        if slug_counts[slug] > 1:
            sections["Duplicate slug pairs"].append((slug, name, "see duplicates page"))
        if not (A.get("hero_image") or {}).get("local_path"):
            sections["Missing hero image"].append((slug, name, "fallback to placeholder"))

    out = []
    for label, items in sections.items():
        if not items:
            continue
        rows = "".join(
            f'<tr><td class="mono">{esc(s)}</td><td>{esc(n)}</td><td>{esc(why)}</td></tr>'
            for s, n, why in items
        )
        out.append(f'<section class="panel"><h2>{esc(label)} <span class="num-pill">{len(items)}</span></h2><table class="data-table"><thead><tr><th>slug</th><th>name</th><th>reason / note</th></tr></thead><tbody>{rows}</tbody></table></section>')

    body = f"""
<h1 class="page-title">Gaps · Known data holes</h1>
<p>Each section groups attractions where the corresponding field could not be auto-collected. Action: manual override or accept gap.</p>
{"".join(out)}
"""
    return page_shell("Gaps", body, "gaps.html")


# =========================================================================
# PAGE 6 — duplicates.html
# =========================================================================

def page_duplicates(attr_data) -> str:
    attrs = {A["slug"]: A for A in attr_data["attractions"]}

    def render_record(A: dict) -> str:
        if not A:
            return "<i>(not found in dataset)</i>"
        price = A.get("original_price") or {}
        price_str = "·".join(f"{k}={v}" for k, v in price.items() if v is not None and k != "source_url") or "—"
        return f"""<div class="dup-card">
  <code class="slug">{esc(A['slug'])}</code>
  <h4>{esc(A.get('museum_name') or '')}</h4>
  <ul>
    <li>libs offer: <b>{len(A.get('sources') or [])}</b></li>
    <li>website: {esc(A.get('website') or '—')}</li>
    <li>phone: {esc(A.get('phone') or '—')}</li>
    <li>address: {esc(A.get('address') or '—')}</li>
    <li>price: {esc(price_str)}</li>
    <li>has description: {"yes" if A.get("description") else "no"}</li>
    <li>has hero image: {"yes" if (A.get('hero_image') or {}).get("local_path") else "no"}</li>
    <li>categories: {esc(", ".join(A.get('categories') or []))}</li>
  </ul>
</div>"""

    pairs_html = []
    for a, b in KNOWN_DUPLICATES:
        A = attrs.get(a)
        B = attrs.get(b)
        # Suggested keep: whichever has more libs
        keep = a if (len(A.get("sources") or []) if A else 0) >= (len(B.get("sources") or []) if B else 0) else b
        drop = b if keep == a else a
        pairs_html.append(f"""<section class="panel dup-pair">
  <h3>{esc(a)} ⇄ {esc(b)}</h3>
  <div class="dup-grid">{render_record(A)}{render_record(B)}</div>
  <p class="suggestion"><b>Suggested:</b> keep <code>{esc(keep)}</code>, drop <code>{esc(drop)}</code></p>
</section>""")
    body = f"""
<h1 class="page-title">Duplicates · {len(KNOWN_DUPLICATES)} pairs</h1>
<p>Pairs of attraction slugs that refer to the same real-world venue. Goal: pick one canonical slug, migrate libraries, retire the other.</p>
{"".join(pairs_html)}
"""
    return page_shell("Duplicates", body, "duplicates.html")


# =========================================================================
# PAGE 7 — lineage.html
# =========================================================================

def page_lineage() -> str:
    body = """
<h1 class="page-title">Data lineage</h1>
<p>How a single fact (e.g. "Acton offers half-price BCM admission for 4 people") travels from a library website to the user's screen.</p>

<svg class="lineage-svg" viewBox="0 0 900 460" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#4A4845"/>
    </marker>
    <style>
      .node { fill: #FAFAF7; stroke: #B5B2A8; stroke-width: 1.5; }
      .node-raw { fill: #F4EFE8; }
      .node-out { fill: #EAF1EE; }
      .label { font: 13px 'DM Sans', sans-serif; fill: #1A1917; }
      .sub { font: 11px 'DM Sans', sans-serif; fill: #4A4845; }
      .edge { stroke: #4A4845; stroke-width: 1.5; fill: none; marker-end: url(#arrow); }
    </style>
  </defs>

  <g><rect class="node" x="20" y="40" width="170" height="60" rx="6"/><text class="label" x="105" y="68" text-anchor="middle">Library website</text><text class="sub" x="105" y="86" text-anchor="middle">59 sources</text></g>
  <g><rect class="node" x="240" y="40" width="170" height="60" rx="6"/><text class="label" x="325" y="68" text-anchor="middle">Python fetcher</text><text class="sub" x="325" y="86" text-anchor="middle">sources/&lt;platform&gt;</text></g>
  <g><rect class="node node-raw" x="460" y="40" width="170" height="60" rx="6"><a href="schema.html"/></rect><text class="label" x="545" y="68" text-anchor="middle">data/raw/&lt;platform&gt;</text><text class="sub" x="545" y="86" text-anchor="middle">scraper JSON</text></g>
  <g><rect class="node" x="680" y="40" width="200" height="60" rx="6"/><text class="label" x="780" y="68" text-anchor="middle">Subagent extract</text><text class="sub" x="780" y="86" text-anchor="middle">Sonnet → policy fields</text></g>

  <g><rect class="node node-raw" x="240" y="180" width="170" height="60" rx="6"/><text class="label" x="325" y="208" text-anchor="middle">raw/pass_policies/</text><text class="sub" x="325" y="226" text-anchor="middle">1008 cells</text></g>
  <g><rect class="node node-raw" x="460" y="180" width="170" height="60" rx="6"/><text class="label" x="545" y="208" text-anchor="middle">raw/attraction_*</text><text class="sub" x="545" y="226" text-anchor="middle">price · hours · desc</text></g>
  <g><rect class="node" x="680" y="180" width="200" height="60" rx="6"/><text class="label" x="780" y="208" text-anchor="middle">scripts/build.py</text><text class="sub" x="780" y="226" text-anchor="middle">merge + normalize</text></g>

  <g><rect class="node node-out" x="20" y="320" width="200" height="60" rx="6"><a href="libraries.html"/></rect><text class="label" x="120" y="348" text-anchor="middle">structured/libraries.json</text><text class="sub" x="120" y="366" text-anchor="middle">59 rows</text></g>
  <g><rect class="node node-out" x="250" y="320" width="200" height="60" rx="6"><a href="attractions.html"/></rect><text class="label" x="350" y="348" text-anchor="middle">structured/attractions.json</text><text class="sub" x="350" y="366" text-anchor="middle">107 rows</text></g>
  <g><rect class="node node-out" x="480" y="320" width="200" height="60" rx="6"><a href="policies.html"/></rect><text class="label" x="580" y="348" text-anchor="middle">structured/passes.json</text><text class="sub" x="580" y="366" text-anchor="middle">1008 rows</text></g>
  <g><rect class="node" x="710" y="320" width="170" height="60" rx="6"/><text class="label" x="795" y="348" text-anchor="middle">React frontend</text><text class="sub" x="795" y="366" text-anchor="middle">web/</text></g>

  <path class="edge" d="M 190 70 L 240 70"/>
  <path class="edge" d="M 410 70 L 460 70"/>
  <path class="edge" d="M 630 70 L 680 70"/>
  <path class="edge" d="M 780 100 L 780 180"/>
  <path class="edge" d="M 545 100 L 545 180"/>
  <path class="edge" d="M 680 210 L 630 210"/>
  <path class="edge" d="M 680 210 L 410 210"/>
  <path class="edge" d="M 780 240 L 780 290 L 580 290 L 580 320"/>
  <path class="edge" d="M 780 240 L 350 290 L 350 320"/>
  <path class="edge" d="M 780 240 L 120 290 L 120 320"/>
  <path class="edge" d="M 680 350 L 710 350"/>
</svg>

<p class="lineage-foot">
  Tap a green box to inspect its structure on this audit site. The schema definitions are in
  <a href="schema.html">schema.html</a>.
</p>
"""
    return page_shell("Lineage", body, "lineage.html")


# =========================================================================
# PAGE 8 — schema.html
# =========================================================================

def page_schema() -> str:
    body = """
<h1 class="page-title">数据结构说明 · Schema</h1>
<p>本页用自然语言解释三大产物中的每个字段,包括字段意义、可能的值、示例,以及为什么这个字段会存在。</p>

<section class="panel">
  <h2>1. 图书馆 Libraries</h2>
  <ul class="schema-list">
    <li><b>id</b>:库的短代码,如 <code>wakefield</code>。所有交叉引用都用它。</li>
    <li><b>name</b>:正式馆名,如 "Lucius Beebe Memorial Library"。</li>
    <li><b>town · network</b>:所在市镇 / 隶属网络(NOBLE / MLN / Minuteman 等)。</li>
    <li><b>platform</b>:博物馆通行证后台,目前有三种 — Assabet(52 馆)/ LibCal(5 馆)/ MuseumKey(2 馆)。决定了我们用哪个 scraper。</li>
    <li><b>card_page</b>:办卡说明页 URL。</li>
    <li><b>eligibility</b>:办卡资格 — <code>open_ma_resident</code> 表示麻州居民均可办,<code>residents_only</code> 表示仅本镇居民。</li>
    <li><b>supports_availability</b>:平台是否可查未来 30 天的库存(MuseumKey 不支持)。</li>
    <li><b>address</b>:街道地址,5 个字段。</li>
    <li><b>geo</b>:经纬度,由 OSM Nominatim 反查得到,缓存在 <code>data/.cache/geocode.json</code>。</li>
  </ul>
</section>

<section class="panel">
  <h2>2. 景点 Attractions</h2>
  <ul class="schema-list">
    <li><b>slug</b>:URL 友好的稳定 ID,如 <code>boston-childrens-museum</code>。</li>
    <li><b>museum_name</b>:正式名称。</li>
    <li><b>address / website / phone / description</b>:景点元数据,来自景点官网或 Wikipedia。</li>
    <li><b>categories</b>:分类标签数组(Children / Family / Science / Art / Nature / History ...)。</li>
    <li><b>sources</b>:提供本景点 pass 的所有图书馆 id 数组。</li>
    <li><b>original_price</b>:景点门市原价。包含 adult / child / youth / senior / student / military / educator / family 八种票种,以及 <code>free_under_age</code>(低于该岁数免费)、notes、source_url。任何字段可为 null,表示未提取到。</li>
    <li><b>hero_image</b>:景点官网 <code>&lt;meta property="og:image"&gt;</code> 抓取的封面图;<code>local_path</code> 是本地缓存路径(gitignored)。</li>
    <li><b>hours</b>:周一至周日营业时间;<code>status</code> 字段表示数据可信度(ok / varies / seasonal / missing)。</li>
    <li><b>geo</b>:经纬度,用于距离排序。</li>
  </ul>
</section>

<section class="panel">
  <h2>3. 优惠规则 Passes</h2>
  <p>每行表示一个 (lib × attraction) 组合,共 1008 行。</p>
  <ul class="schema-list">
    <li><b>library_id / attraction_slug</b>:主键,联合唯一。</li>
    <li><b>pass_type</b>:三种 pass 形态 —
      <ul>
        <li><b>digital</b>:邮件即时发送的电子券,用户可立即下载并使用(553 个)。</li>
        <li><b>physical-coupon</b>:门店取纸质券,用完不归还(260 个)。</li>
        <li><b>physical-circ / loan-card</b>:循环借阅卡,用完需归还图书馆(172 个)。</li>
        <li><b>unknown</b>:未能识别(23 个)。</li>
      </ul>
    </li>
    <li><b>discount</b>:折扣类型与展示标签。class 五种:
      <ul>
        <li><b>free</b>:完全免费(277 个)</li>
        <li><b>half</b>:半价 / 50% off(290 个)</li>
        <li><b>percent-off</b>:其它百分比折扣(4 个)</li>
        <li><b>dollar-off</b>:固定金额减免,如 $5 off(19 个)</li>
        <li><b>price</b>:打到一个固定低价,如 "Adults $5 / Kids $3"(342 个)</li>
        <li><b>discount</b>:笼统折扣(23 个);<b>unknown</b>:未识别(53 个)</li>
      </ul>
    </li>
    <li><b>policy</b>:从 raw 文本中抽出的结构化字段:
      <ul>
        <li><b>max_people</b>(总人数上限) / <b>max_adults</b> / <b>max_children</b></li>
        <li><b>free_under_age</b>:低于该岁数免费</li>
        <li><b>discount_percent / discount_dollar_off / savings_per_person_usd</b>:折扣量</li>
        <li><b>eligibility_tags</b>:适用人群标签(见下)</li>
        <li><b>exclusions</b>:限制条件(见下)</li>
        <li><b>boosts</b>:额外福利</li>
        <li><b>raw</b>:原始优惠说明,所有抽取都基于它</li>
      </ul>
    </li>
    <li><b>source_phrases</b>(在 raw/pass_policies/*.json 中):每个抽取字段对应在 raw 中的子串,供审计高亮。</li>
    <li><b>availability</b>:未来 30 天的可预订状态字典(museumkey 不可用)。</li>
  </ul>

  <h3>Eligibility 标签 · 13 种</h3>
  <ul class="schema-list">
    <li><b>all</b> · open to all — 默认值,任何持卡人都能用</li>
    <li><b>vehicle</b> · per vehicle — 按车而非按人(适用州立公园)</li>
    <li><b>single_ticket</b> · 1 ticket — 单张票,而非"上限 N 人"</li>
    <li><b>family</b> · family pass — family pass,常含父母 + 子女</li>
    <li><b>groups</b> · group rate — 按团体打折</li>
    <li><b>residents_only</b> · residents only — 仅特定市镇居民</li>
    <li><b>adults_only</b> / <b>children_only</b> — 只覆盖成人或儿童一种票种</li>
    <li><b>seniors_free</b> · <b>students_only</b> · <b>military_free</b> · <b>educator_free</b> · <b>members_free</b> — 该群体特殊免费</li>
  </ul>

  <h3>Exclusions 限制</h3>
  <ul class="schema-list">
    <li><b>weekdays_only / weekends_only / weekends_excluded</b>:工作日 / 周末限制</li>
    <li><b>blackout_dates</b>:特定日期不可用</li>
    <li><b>reservation_required</b>:必须先预约</li>
    <li><b>id_required</b>:入场需出示证件</li>
    <li><b>seasonal:X-Y</b>:仅在某月份范围内开放,例如 <code>seasonal:apr-oct</code></li>
  </ul>

  <h3>Boosts 加成</h3>
  <ul class="schema-list">
    <li><b>library_card_required</b>:进入景点需出示图书馆卡</li>
    <li><b>members_discount</b>:景点会员另享折扣</li>
    <li><b>gift_shop_discount</b>:礼品店折扣</li>
    <li><b>ebt_discount / snap_free</b>:EBT / SNAP 低收入援助</li>
  </ul>
</section>

<p class="foot-link"><a href="#" class="view-json-link" data-json-key="schema">查看技术 JSON 结构</a></p>
"""
    blob = json.dumps({
        "schema": {
            "passes_row_keys": ["library_id", "attraction_slug", "pass_type", "pass_type_raw",
                                 "discount", "policy", "source_url", "availability"],
            "policy_keys": ["max_people", "max_adults", "max_children", "free_under_age",
                            "savings_per_person_usd", "discount_percent", "discount_dollar_off",
                            "eligibility_tags", "exclusions", "boosts", "notes", "raw"],
            "discount_classes": ["free", "half", "percent-off", "dollar-off", "price", "discount", "unknown"],
            "pass_types": ["digital", "physical-coupon", "physical-circ", "loan-card", "unknown"],
        }
    }, ensure_ascii=False)
    return page_shell("Schema", body, "schema.html", data_blob=blob)


# =========================================================================
# CSS + JS
# =========================================================================

CSS = """
:root {
  --bg: #F4F3EF; --paper: #ECEAE4; --white: #FAFAF7;
  --ink: #000000; --ink-2: #1A1917; --ink-3: #4A4845;
  --g: #1B5740; --g-2: #2A7055; --g-light: #C4DDCF; --g-pale: #EAF1EE;
  --au: #8C6018; --au-pale: #F4EFE8;
  --or: #D97706; --or-pale: #FDF1E2;
  --rd: #8C2A1E; --rd-pale: #F4EAE9;
  --rule: #D0CEC6; --rule-strong: #B5B2A8;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { background: var(--bg); color: var(--ink-2); font: 13px/1.78 'DM Sans','PingFang SC',sans-serif; }
.font-serif { font-family: 'Libre Baskerville', Georgia, serif; }

a { color: var(--g); text-decoration: none; }
a:hover { text-decoration: underline; }
code, .mono { font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 12px; }

.site-head { background: var(--white); border-bottom: 1px solid var(--rule); padding: 12px 24px; position: sticky; top: 0; z-index: 50; }
.site-head .brand { font-size: 15px; font-weight: 600; }
.topnav { margin-top: 6px; font-size: 12px; color: var(--ink-3); }
.topnav a { color: var(--ink-3); margin-right: 4px; }
.topnav a.current { color: var(--g); font-weight: 600; }

main { max-width: 1280px; margin: 0 auto; padding: 28px 24px 80px; }

.page-title { font-family: 'Libre Baskerville', Georgia, serif; font-size: 28px; margin: 0 0 6px; color: var(--ink); font-weight: 700; }
.subtitle { color: var(--ink-3); margin: 0 0 28px; }

.panel { background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 18px 22px; margin-bottom: 20px; }
.panel h2, .panel h3 { margin: 0 0 12px; font-size: 15px; color: var(--ink); }

.cards-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.num-card { background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 22px; text-align: center; }
.num-card .num { font-size: 42px; font-weight: 700; color: var(--g); font-family: 'Libre Baskerville', Georgia, serif; }
.num-card .label { color: var(--ink-3); font-size: 13px; margin-top: 6px; }

.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
.coverage { list-style: none; padding: 0; margin: 0; }
.coverage li { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px dotted var(--rule); }
.cov-pct { color: var(--g); font-weight: 600; }

.histogram { width: 100%; }
.histogram td { padding: 4px 8px; border-bottom: 1px dotted var(--rule); }
.histogram .bar-cell { width: 60%; }
.histogram .bar { color: var(--g); font-family: monospace; letter-spacing: -2px; }
.histogram .num { color: var(--ink-2); font-weight: 600; }
.histogram .pct { color: var(--ink-3); }

.platform-row { list-style: none; padding: 0; margin: 0; display: flex; gap: 32px; }
.platform-row .num { color: var(--g); font-weight: 700; font-size: 24px; margin: 0 8px; }

.anomaly-list { padding-left: 18px; }
.anomaly-list li { padding: 4px 0; }

.page-foot { color: var(--ink-3); margin-top: 32px; font-size: 12px; text-align: center; }

.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.search-box, .filter-select { padding: 8px 12px; border: 1px solid var(--rule-strong); border-radius: 6px; background: var(--white); font-size: 13px; }
.search-box { min-width: 280px; }

.data-table { width: 100%; border-collapse: collapse; background: var(--white); border: 1px solid var(--rule); border-radius: 8px; overflow: hidden; }
.data-table thead { background: var(--paper); }
.data-table th, .data-table td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--rule); font-size: 12.5px; }
.data-table tr:last-child td { border-bottom: none; }
.data-table .truncate { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.data-table .own { color: var(--au); font-size: 16px; text-align: center; }

.foot-link { color: var(--ink-3); margin-top: 16px; font-size: 12px; }

/* Badges */
.badge { display: inline-block; padding: 2px 8px; margin: 2px 3px 2px 0; border-radius: 11px; font-size: 11px; line-height: 1.6; }
.badge-plat-assabet { background: var(--g-pale); color: var(--g); }
.badge-plat-libcal  { background: var(--au-pale); color: var(--au); }
.badge-plat-museumkey { background: var(--rd-pale); color: var(--rd); }

.badge-pt-digital { background: var(--g-pale); color: var(--g); }
.badge-pt-physical-coupon { background: var(--au-pale); color: var(--au); }
.badge-pt-physical-circ { background: var(--rd-pale); color: var(--rd); }
.badge-pt-loan-card { background: var(--rd-pale); color: var(--rd); }
.badge-pt-unknown { background: var(--paper); color: var(--ink-3); }

.badge-disc-free { background: var(--g-pale); color: var(--g); font-weight: 600; font-family: 'Libre Baskerville', Georgia, serif; }
.badge-disc-half { background: var(--g-pale); color: var(--g-2); }
.badge-disc-percent-off { background: var(--au-pale); color: var(--au); }
.badge-disc-dollar-off { background: var(--au-pale); color: var(--au); }
.badge-disc-price { background: var(--paper); color: var(--ink-3); }
.badge-disc-discount { background: var(--au-pale); color: var(--au); }
.badge-disc-unknown { background: var(--paper); color: var(--ink-3); }

.badge-elig-default { background: var(--g-pale); color: var(--g); }
.badge-elig-structural { background: var(--au-pale); color: var(--au); }
.badge-elig-audience { background: var(--or-pale); color: var(--or); }
.badge-elig-free-group { background: var(--g-light); color: var(--g); }

.badge-excl { background: var(--rd-pale); color: var(--rd); }
.badge-seasonal { background: var(--au-pale); color: var(--au); }
.badge-boost { background: var(--g-pale); color: var(--g-2); }
.badge-cat { background: var(--paper); color: var(--ink-3); font-size: 10.5px; }

/* Coverage states */
.verified { color: var(--g); }
.ok-no-src { color: var(--au); background: var(--au-pale); }
.honest-gap { color: var(--ink-3); }
.unexplained { color: var(--rd); background: var(--rd-pale); }

/* Attractions */
.attr-list { display: flex; flex-direction: column; gap: 12px; }
.attr-row { background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 14px 16px; font-size: 12.5px; }
.attr-head { display: flex; gap: 12px; align-items: center; margin-bottom: 6px; }
.hero-thumb { width: 48px; height: 48px; object-fit: cover; border-radius: 4px; cursor: zoom-in; flex-shrink: 0; }
.hero-thumb.noimg { background: var(--paper); display: flex; align-items: center; justify-content: center; color: var(--ink-3); }
.attr-title { display: flex; flex-wrap: wrap; gap: 6px; align-items: baseline; }
.attr-title .slug { background: var(--paper); padding: 1px 6px; border-radius: 3px; }
.attr-title .attr-name { font-weight: 600; }
.attr-title .n-libs { color: var(--ink-3); font-size: 11px; }
.attr-title .warn { color: var(--rd); }
.attr-row > div { margin: 3px 0; }
.attr-row b { color: var(--ink); }
.price-cell, .hr-cell { display: inline-block; margin-right: 8px; padding: 1px 4px; border-radius: 3px; font-size: 11.5px; }
.lib-list { font-family: monospace; font-size: 11px; color: var(--ink-3); }
.attr-info span { margin-right: 14px; }

/* Policies */
.policies-toolbar { background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; position: sticky; top: 64px; z-index: 30; }
.tab-row { display: flex; gap: 6px; margin-bottom: 8px; }
.tab { background: var(--paper); border: 1px solid var(--rule); padding: 5px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; color: var(--ink-3); }
.tab.active { background: var(--g); color: var(--white); border-color: var(--g); }
.tab-panel { display: none; }
.tab-panel.active { display: block; }

.toc { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.toc-item { background: var(--white); border: 1px solid var(--rule); padding: 6px 10px; border-radius: 6px; font-size: 11px; color: var(--ink-2); min-width: 130px; }
.toc-item small { color: var(--ink-3); }
.toc-item .toc-n { float: right; font-weight: 600; color: var(--g); }

.pattern-section { margin-bottom: 28px; }
.pattern-header { font-size: 16px; background: var(--paper); padding: 10px 14px; border-radius: 6px; border-left: 4px solid var(--g); margin: 0 0 12px; position: sticky; top: 158px; z-index: 20; }
.pattern-meta { float: right; color: var(--ink-3); font-size: 12px; font-weight: 400; }
.pattern-zh { color: var(--ink-3); font-weight: 400; font-size: 13px; margin-left: 8px; }

.policy-row { background: var(--white); border: 1px solid var(--rule); border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; font-size: 12px; }
.policy-row header { margin-bottom: 6px; }
.lib-arrow-slug { margin-right: 10px; }
.policy-row .raw { margin: 4px 0; color: var(--ink-2); line-height: 1.7; }
.policy-row .extracted { margin: 4px 0; font-size: 11.5px; color: var(--ink-3); }
.policy-row .extracted .ext { margin-right: 12px; }
.policy-row .src-link { margin: 4px 0 0; font-size: 11px; }

mark { padding: 0 2px; border-radius: 2px; }
mark.src-1 { background: #FFF3B0; }
mark.src-2 { background: #C4DDCF; }
mark.src-3 { background: #FDE2C8; }
mark.src-4 { background: #F4D6D2; }
mark.src-5 { background: #D5D9F0; }
mark.src-6 { background: #E8DCC4; }
mark sup { font-size: 9px; margin-left: 2px; color: var(--ink-3); }

/* Duplicates */
.dup-pair h3 { margin-top: 0; color: var(--rd); }
.dup-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.dup-card { background: var(--paper); padding: 12px; border-radius: 6px; }
.dup-card h4 { margin: 4px 0 8px; }
.dup-card ul { list-style: none; padding: 0; margin: 0; font-size: 12px; }
.dup-card ul li { padding: 2px 0; border-bottom: 1px dotted var(--rule); }
.suggestion { background: var(--g-pale); padding: 8px 12px; border-radius: 6px; margin-top: 12px; color: var(--g); }

/* Gaps */
.num-pill { background: var(--rd-pale); color: var(--rd); padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-left: 8px; }

/* Schema */
.schema-list { list-style: none; padding: 0; }
.schema-list > li { padding: 6px 0; border-bottom: 1px dotted var(--rule); }
.schema-list b { color: var(--ink); }
.schema-list ul { margin-top: 6px; padding-left: 18px; }

/* Lineage */
.lineage-svg { width: 100%; max-width: 900px; height: auto; display: block; margin: 20px auto; background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 16px; }
.lineage-foot { text-align: center; color: var(--ink-3); }

/* Modal */
.modal-root { position: fixed; inset: 0; z-index: 100; }
.modal-root.hidden { display: none; }
.modal-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.45); }
.modal-box { position: relative; background: var(--white); max-width: 720px; max-height: 80vh; overflow: auto; margin: 5vh auto; padding: 24px; border-radius: 8px; }
.modal-close { position: absolute; top: 8px; right: 12px; background: none; border: none; font-size: 22px; cursor: pointer; color: var(--ink-3); }
.modal-body img { max-width: 500px; height: auto; }
.modal-body pre { background: var(--paper); padding: 12px; border-radius: 6px; overflow: auto; font-size: 11px; max-height: 60vh; }
"""

JS = r"""
// audit.js — minimal interactivity

(function () {
  // Modal
  const modalRoot = document.getElementById('modal-root');
  const modalBody = modalRoot.querySelector('.modal-body');
  const closeBtn = modalRoot.querySelector('.modal-close');
  const backdrop = modalRoot.querySelector('.modal-backdrop');

  function openModal(html) {
    modalBody.innerHTML = html;
    modalRoot.classList.remove('hidden');
  }
  function closeModal() {
    modalRoot.classList.add('hidden');
    modalBody.innerHTML = '';
  }
  closeBtn.addEventListener('click', closeModal);
  backdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });

  // Hero thumbnail modal
  document.querySelectorAll('.hero-thumb').forEach(function (el) {
    if (el.classList.contains('noimg')) return;
    el.addEventListener('click', function () {
      const src = el.getAttribute('data-full') || el.src;
      openModal('<img src="' + src + '" alt="">');
    });
  });

  // JSON view modal
  const dataBlobEl = document.getElementById('data-blob');
  const dataBlob = dataBlobEl ? JSON.parse(dataBlobEl.textContent || '{}') : {};

  document.querySelectorAll('.view-json-link').forEach(function (link) {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      const key = link.getAttribute('data-json-key');
      const val = dataBlob[key];
      const pretty = val === undefined ? '(key not in data blob: ' + key + ')' : JSON.stringify(val, null, 2);
      const escaped = pretty.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      openModal('<h3>' + key + '</h3><pre>' + escaped + '</pre>');
    });
  });

  // Search filter
  document.querySelectorAll('.search-box').forEach(function (box) {
    box.addEventListener('input', function () {
      const target = box.getAttribute('data-target');
      const q = box.value.toLowerCase().trim();
      let container;
      if (target === 'policies-active') {
        container = document.querySelector('.tab-panel.active');
      } else {
        container = document.getElementById(target);
      }
      if (!container) return;
      // Filter direct rows (tr or article)
      const items = container.querySelectorAll('[data-search]');
      items.forEach(function (it) {
        const hay = it.getAttribute('data-search') || '';
        it.style.display = (!q || hay.indexOf(q) !== -1) ? '' : 'none';
      });
    });
  });

  // Category filter on attractions
  document.querySelectorAll('.filter-select').forEach(function (sel) {
    sel.addEventListener('change', function () {
      const target = sel.getAttribute('data-target');
      const attr = sel.getAttribute('data-filter-attr');
      const v = sel.value;
      const container = document.getElementById(target);
      if (!container) return;
      container.querySelectorAll('[' + attr + ']').forEach(function (it) {
        const list = it.getAttribute(attr) || '';
        it.style.display = (!v || list.split(',').indexOf(v) !== -1) ? '' : 'none';
      });
    });
  });

  // Tabs on policies page
  document.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      const id = tab.getAttribute('data-tab');
      document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
      tab.classList.add('active');
      document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.remove('active'); });
      const panel = document.getElementById(id);
      if (panel) panel.classList.add('active');
    });
  });

  // Smooth scroll on TOC links (anchor)
  document.querySelectorAll('.toc-item').forEach(function (a) {
    a.addEventListener('click', function (e) {
      const href = a.getAttribute('href');
      if (href && href.startsWith('#')) {
        e.preventDefault();
        const t = document.querySelector(href);
        if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
})();
"""


# =========================================================================
# Main
# =========================================================================

def main():
    OUT.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)

    print("[1/8] loading data ...")
    libs_data = load_json(STRUCT / "libraries.json")
    attr_data = load_json(STRUCT / "attractions.json")
    passes_data = load_json(STRUCT / "passes.json")
    libcat = load_json(STRUCT / "library_catalog.json")

    pages = []

    def write(name: str, content: str):
        p = OUT / name
        p.write_text(content, encoding="utf-8")
        size_kb = p.stat().st_size / 1024
        print(f"  wrote {name:18s}  {size_kb:8.1f} KB")
        pages.append((name, p.stat().st_size))

    print("[2/8] index.html")
    write("index.html", page_index(libs_data, attr_data, passes_data, libcat))

    print("[3/8] libraries.html")
    write("libraries.html", page_libraries(libs_data))

    print("[4/8] attractions.html")
    attr_html, missing_image = page_attractions(attr_data)
    write("attractions.html", attr_html)

    print("[5/8] policies.html")
    pol_html, n_patterns = page_policies(passes_data, libs_data, attr_data)
    write("policies.html", pol_html)

    print("[6/8] gaps.html")
    write("gaps.html", page_gaps(attr_data, libs_data))

    print("[7/8] duplicates.html")
    write("duplicates.html", page_duplicates(attr_data))

    print("[7.5/8] lineage.html")
    write("lineage.html", page_lineage())

    print("[8/8] schema.html")
    write("schema.html", page_schema())

    print("[assets] style.css + audit.js")
    (ASSETS / "style.css").write_text(CSS, encoding="utf-8")
    (ASSETS / "audit.js").write_text(JS, encoding="utf-8")
    print(f"  wrote assets/style.css     {(ASSETS / 'style.css').stat().st_size/1024:8.1f} KB")
    print(f"  wrote assets/audit.js      {(ASSETS / 'audit.js').stat().st_size/1024:8.1f} KB")

    total = sum(s for _, s in pages) + (ASSETS / "style.css").stat().st_size + (ASSETS / "audit.js").stat().st_size
    print(f"\nDone. Total audit/ size: {total/1024/1024:.2f} MB")
    print(f"Patterns generated: {n_patterns}")
    print(f"Attractions missing local hero image: {len(missing_image)}")
    if missing_image:
        print(f"  -> {missing_image[:10]}{'...' if len(missing_image) > 10 else ''}")


if __name__ == "__main__":
    main()
