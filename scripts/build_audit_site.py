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
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRUCT = ROOT / "data" / "structured"
RAW = ROOT / "data" / "raw"
WEB_IMG = ROOT / "web" / "public" / "images"
OUT = ROOT / "audit"
ASSETS = OUT / "assets"

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


def has_numeric_price(A: dict) -> bool:
    """True when the attraction carries at least one numeric ticket tier.

    The mere presence of an ``original_price`` object is not enough — early
    extraction stamped {"age_pricing": {"adult": null, ..., "free_under_age": 5}}
    on rows that only document an under-N free policy, leaving every numeric
    field null. Those should count as missing price on the audit side.
    """
    op = A.get("original_price") or {}
    age = op.get("age_pricing") or {}
    for k in ("adult", "child", "youth", "senior"):
        tier = age.get(k)
        if tier and tier.get("price") is not None:
            return True
    ident = op.get("identity_pricing") or {}
    for tier in ident.values():
        if tier and tier.get("price") is not None:
            return True
    fam = op.get("family")
    if fam and fam.get("price") is not None:
        return True
    return False


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


# ---------- Pattern clustering ----------

CAP_BUCKETS = ["people", "vehicle", "other"]
CAP_LABEL_EN = {"people": "Headcount", "vehicle": "Vehicle", "other": "Other"}
CAP_LABEL_ZH = {"people": "人数",      "vehicle": "车辆",    "other": "其他"}

FORM_BUCKETS = ["percent", "fixed", "free", "vague", "other"]
FORM_LABEL_EN = {
    "percent": "Percent off",
    "fixed":   "Fixed amount",
    "free":    "FREE",
    "vague":   "Vague discount",
    "other":   "Other",
}
FORM_LABEL_ZH = {
    "percent": "百分比",
    "fixed":   "固定金额",
    "free":    "免费",
    "vague":   "模糊优惠",
    "other":   "其他",
}


def cap_bucket(pass_obj: dict) -> str:
    """Capacity dimension: 3 buckets — Headcount (people+ticket), Vehicle, Other."""
    cap = (pass_obj.get("coupon") or {}).get("capacity") or {}
    k = cap.get("kind") or "unspecified"
    if k in ("people", "ticket"): return "people"
    if k == "vehicle":            return "vehicle"
    return "other"


def form_bucket(pass_obj: dict) -> str:
    """Discount form dimension: 5 buckets — derived from the primary audience_policy."""
    aps = (pass_obj.get("coupon") or {}).get("audience_policies") or []
    if not aps:
        return "other"
    f = aps[0].get("form", "discount")
    if f == "percent-off":                            return "percent"
    if f in ("dollar-off", "per-person-price"):       return "fixed"
    if f == "free":                                   return "free"
    if f == "discount":                               return "vague"
    return "other"


def signature(pass_obj: dict) -> tuple[str, str]:
    """Two-dimensional grouping — 3 capacity buckets × 5 form buckets = 15 cells."""
    return (cap_bucket(pass_obj), form_bucket(pass_obj))


def signature_name(sig: tuple[str, str]) -> tuple[str, str]:
    cap, form = sig
    en = f"{FORM_LABEL_EN[form]} · {CAP_LABEL_EN[cap]}"
    zh = f"{FORM_LABEL_ZH[form]} · {CAP_LABEL_ZH[cap]}"
    return en, zh


# ---------- Badges ----------

def badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{esc(text)}</span>'


def compute_dq_counts(libs_data, attr_data, passes_data, raw_coupons_dir) -> dict:
    """Return a dict of {panel_id: count} for each data-quality red-flag panel.

    Mirrors the logic in page_data_quality() so the status banner on index.html
    and data_quality.html agree perfectly. Severity classification (HIGH/MED/LOW)
    matches the summary table in page_data_quality.
    """
    _src = str(ROOT / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)
    from malibbene.build.slug_canonical import canonical  # noqa: WPS433

    passes = passes_data["passes"]
    attrs = attr_data["attractions"]

    # p1: empty coupon
    p1 = 0
    for p in passes:
        coupon = p.get("coupon") or {}
        cap = coupon.get("capacity") or {}
        if (coupon.get("audience_policies") or []) == [] and (cap.get("kind") or "unspecified") == "unspecified":
            p1 += 1
    # p2: cross-library price variance — informational, not a defect
    per_attr_adult: dict = defaultdict(set)
    per_attr_child: dict = defaultdict(set)
    for p in passes:
        slug = p.get("attraction_slug", "")
        for ap in (p.get("coupon") or {}).get("audience_policies") or []:
            if ap.get("form") == "per-person-price" and ap.get("value") is not None:
                if ap.get("audience") == "Adult":
                    per_attr_adult[slug].add(float(ap["value"]))
                elif ap.get("audience") == "Child":
                    per_attr_child[slug].add(float(ap["value"]))
    p2 = sum(1 for s in per_attr_adult if len(per_attr_adult[s]) > 1) + sum(1 for s in per_attr_child if len(per_attr_child[s]) > 1)
    # p3: form=discount + value=null
    p3 = 0
    for p in passes:
        for ap in (p.get("coupon") or {}).get("audience_policies") or []:
            if ap.get("form") == "discount" and ap.get("value") is None:
                p3 += 1
    # p4: age contradicts audience
    p4 = 0
    for p in passes:
        for ap in (p.get("coupon") or {}).get("audience_policies") or []:
            aud = ap.get("audience")
            ar = ap.get("age_range") or {}
            mn = ar.get("min"); mx = ar.get("max")
            if (aud == "Adult" and mn is not None and mn < 13) \
               or (aud == "Senior" and mn is not None and mn < 50) \
               or (aud == "Child" and mn is not None and mn >= 13) \
               or (aud == "Youth" and mx is not None and mx < 5):
                p4 += 1
    # p5: orphan raw coupon files
    consumed: set = set()
    for p in passes:
        coupon = p.get("coupon") or {}
        cap = coupon.get("capacity") or {}
        if coupon.get("audience_policies") or cap.get("n") is not None:
            consumed.add((p.get("library_id", ""), p.get("attraction_slug", "")))
    p5 = 0
    raw_dir = Path(raw_coupons_dir)
    if raw_dir.exists():
        for f in raw_dir.glob("*.json"):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("status") != "ok":
                continue
            stem_parts = f.stem.split("_", 1)
            lib_id = rec.get("library_id") or (stem_parts[0] if stem_parts else "")
            raw_slug = rec.get("attraction_slug") or (stem_parts[1] if len(stem_parts) > 1 else "")
            if (lib_id, canonical(raw_slug)) not in consumed:
                p5 += 1
    # p6: umbrella attractions
    p6 = 0
    for A in attrs:
        hours = A.get("hours") or {}
        op = A.get("original_price") or {}
        ap = (op.get("age_pricing") or {}).get("adult")
        if hours.get("status") == "varies" and (not op or ap is None):
            p6 += 1
    # p7: raw extraction failures
    p7 = 0
    if raw_dir.exists():
        for f in raw_dir.glob("*.json"):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("status") != "ok":
                p7 += 1
    return {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5, "p6": p6, "p7": p7}


# severity classification — must match the summary table in page_data_quality
DQ_SEVERITY = {"p1": "HIGH", "p2": "INFO", "p3": "LOW", "p4": "MED", "p5": "HIGH", "p6": "LOW", "p7": "MED"}


def status_banner_html(counts: dict) -> str:
    """Render the top-of-page green/orange/red status callout."""
    high = sum(counts[k] for k, sev in DQ_SEVERITY.items() if sev == "HIGH")
    med  = sum(counts[k] for k, sev in DQ_SEVERITY.items() if sev == "MED")
    low  = sum(counts[k] for k, sev in DQ_SEVERITY.items() if sev == "LOW")
    info = sum(counts[k] for k, sev in DQ_SEVERITY.items() if sev == "INFO")
    if high > 0:
        cls = "banner-red"; icon = "🔴"; verdict = f"{high} critical issue(s)"
    elif med > 0:
        cls = "banner-amber"; icon = "⚠"; verdict = f"{med} medium issue(s)"
    elif low > 0 or info > 0:
        cls = "banner-amber"; icon = "⚠"; verdict = f"{low} low · {info} info finding(s)"
    else:
        cls = "banner-green"; icon = "✅"; verdict = "all clear"
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f'<section class="status-banner {cls}">'
        f'<span class="banner-icon">{icon}</span>'
        f'<span class="banner-verdict"><b>Data foundation — {verdict}.</b> '
        f'HIGH {high} · MED {med} · LOW {low} · INFO {info}.</span>'
        f'<span class="banner-meta">Built {esc(built)} · '
        f'<a href="#data-quality">see Data Quality</a></span>'
        f'</section>'
    )


def bilingual(label: str) -> str:
    """Split an 'English · 中文' label into an English primary line plus a
    smaller-font Chinese sub-line. If the label has no ' · ' separator, the
    text is returned escaped as-is."""
    if not isinstance(label, str) or " · " not in label:
        return esc(label)
    en, _, zh = label.partition(" · ")
    return f'{esc(en)}<span class="zh-sub">{esc(zh)}</span>'


_PT_DISPLAY_LABEL = {
    "digital": "Email",
    "physical-coupon": "Pickup",
    "physical-circ": "Borrow",
    "unknown": "Pass",
}


def pass_type_badge(pt: str) -> str:
    label = _PT_DISPLAY_LABEL.get(pt, pt)
    return f'<span class="badge badge-pt-{esc(pt)}">{esc(label)}</span>'


# ---------- Page chrome ----------

NAV_LINKS = [
    ("index.html", "Attractions"),
    ("passes.html", "Passes"),
    ("lineage.html", "Lineage"),
    ("schema.html", "Schema"),
    ("data_quality.html", "Data Quality"),
]

# Anchor-based nav used by the single audit.html page.
NAV_ANCHORS = [
    ("#attractions", "Attractions"),
    ("#passes", "Passes"),
    ("#lineage", "Lineage"),
    ("#schema", "Schema"),
    ("#data-quality", "Data Quality"),
]


# Shared helper for histogram tables on detail pages
_TRAILING_KEYS = {"unknown", "unspecified", "other", "others", "未知", "未明示",
                  "未分类", "no_data", "nodata", "bucket_nodata", "none", "(none)",
                  "(unknown)", "(no extraction)", "(unspecified n)"}


def _is_trailing_key(key) -> bool:
    """Sentinel keys (unknown / others / null) belong at the bottom of any
    rank-ordered histogram regardless of count — investment-bank table convention.
    """
    if key is None:
        return True
    s = str(key).strip().lower()
    return s in _TRAILING_KEYS or s == "null" or s == "(none)"


def histogram_table(counter: Counter, total: int, label_map: dict | None = None, max_rows: int | None = None) -> str:
    if not counter:
        return '<p class="honest-gap">无数据</p>'
    items = counter.most_common(max_rows) if max_rows else counter.most_common()
    head = [it for it in items if not _is_trailing_key(it[0])]
    tail = [it for it in items if _is_trailing_key(it[0])]
    most = head + tail
    max_n = most[0][1] if most else 1
    rows = []
    for key, n in most:
        if label_map and key in label_map:
            lab = label_map[key]
        elif isinstance(key, str) and key.startswith("seasonal:"):
            lab = f"Open {key.split(':', 1)[1]}"
        else:
            lab = str(key) if key is not None else "(none)"
        bar_w = round(40 * n / max_n)
        pct = round(100 * n / total) if total else 0
        rows.append(
            f'<tr><td>{bilingual(lab)}</td>'
            f'<td class="bar-cell"><span class="bar">{"█" * bar_w}</span></td>'
            f'<td class="num">{n}</td><td class="pct">{pct}%</td></tr>'
        )
    return f'<table class="histogram">{"".join(rows)}</table>'


def capacity_matrix_html(matrix: dict, total: int) -> str:
    """Render the 3-bucket × n capacity matrix as a single table.

    Buckets: headcount (people + ticket, both are "1 person per unit"),
    vehicle (per-car coupons), other (kind=unspecified / missing).
    """
    all_n: list = sorted(
        {n for b in matrix.values() for n in b if n != "null"},
        key=lambda x: (isinstance(x, str), x),
    )
    cols = all_n + ["null"]
    bucket_label = {
        "headcount": "Headcount · 有人数限制",
        "vehicle":   "Per-vehicle · 按车",
        "other":     "Other · 其他",
    }
    head_cells = "".join(
        f'<th class="num">{esc("∅" if c == "null" else str(c))}</th>'
        for c in cols
    )
    rows = []
    for bucket in ("headcount", "vehicle", "other"):
        counter = matrix[bucket]
        bucket_total = sum(counter.values())
        if bucket_total == 0:
            continue
        cells = "".join(
            f'<td class="num">{counter[c]}</td>' if counter.get(c) else '<td class="num"></td>'
            for c in cols
        )
        pct = round(100 * bucket_total / total) if total else 0
        rows.append(
            f'<tr><td>{bilingual(bucket_label[bucket])}</td>'
            f'{cells}'
            f'<td class="num"><b>{bucket_total}</b></td><td class="pct">{pct}%</td></tr>'
        )
    return (
        f'<table class="data-table capacity-matrix">'
        f'<thead><tr><th>bucket</th>{head_cells}'
        f'<th class="num">total</th><th class="pct">%</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


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


def audit_shell(body: str, data_blob: str = "") -> str:
    """Single-page wrapper with anchor-based nav (used by audit.html)."""
    nav = " · ".join(
        f'<a href="{href}">{label}</a>'
        for href, label in NAV_ANCHORS
    )
    blob = f'<script id="data-blob" type="application/json">{data_blob}</script>' if data_blob else ""
    return f"""<!doctype html>
<html lang="zh"><head>
<meta charset="utf-8">
<title>MuseumPapa Audit</title>
<link rel="stylesheet" href="assets/style.css">
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

def page_index(libs_data, attr_data, passes_data, libcat, status_banner: str = "") -> str:
    libs = libs_data["libraries"]
    attrs = attr_data["attractions"]
    passes = passes_data["passes"]

    n_libs = len(libs)
    n_attrs = len(attrs)
    n_passes = len(passes)

    # coverage stats — labels are bilingual; residency intentionally NOT shown
    # (per product decision: assume all users are MA cardholders).
    lib_cov = {
        "Street address · 街道地址": sum(1 for L in libs if (L.get("address") or {}).get("street")),
        "Geo coordinates · 经纬度": sum(1 for L in libs if L.get("geo")),
        "Card-application page · 办卡说明页 URL": sum(1 for L in libs if L.get("card_page")),
    }
    attr_cov = {
        "Hero image · 封面图": sum(1 for A in attrs if (A.get("hero_image") or {}).get("local_path")),
        "Ticket price (any tier) · 票价(任一层级)": sum(1 for A in attrs if has_numeric_price(A)),
        "Opening hours · 营业时间": sum(1 for A in attrs if A.get("hours")),
        "Description · 简介": sum(1 for A in attrs if A.get("description")),
        "Phone · 电话": sum(1 for A in attrs if A.get("phone")),
        "Geo coordinates · 经纬度": sum(1 for A in attrs if A.get("geo")),
    }
    pass_cov = {
        "Coupon extracted · 优惠已结构化": sum(1 for p in passes if p.get("coupon")),
        "Pass type known · 取券方式已分类": sum(1 for p in passes if p.get("pass_type") not in (None, "unknown")),
        "Availability calendar · 库存日历(空位可见)": sum(1 for p in passes if p.get("availability")),
    }

    # ── Coupon model distributions (plan-9) ──────────────────────────────
    # Coupon form distribution: count every audience_policies[*].form
    coupon_form_counter: Counter = Counter()
    for p in passes:
        for ap in (p.get("coupon") or {}).get("audience_policies") or []:
            f = ap.get("form") or "discount"
            coupon_form_counter[f] += 1

    # Capacity distribution — fold into 3 user-facing buckets.
    # ticket is a degenerate headcount (single-ticket = "1 person max"), so it
    # joins people under the Headcount bucket. Vehicle stays separate; everything
    # else (kind=unspecified, weird/missing) goes to Other.
    def _capacity_bucket(cap: dict) -> str:
        k = (cap or {}).get("kind") or "unspecified"
        if k in ("people", "ticket"): return "headcount"
        if k == "vehicle":            return "vehicle"
        return "other"

    cap_matrix: dict[str, Counter] = {
        "headcount": Counter(), "vehicle": Counter(), "other": Counter(),
    }
    for p in passes:
        cap = (p.get("coupon") or {}).get("capacity") or {}
        b = _capacity_bucket(cap)
        n = cap.get("n")
        cap_matrix[b][n if n is not None else "null"] += 1

    # Audience-split distribution: how many audience_policies entries per pass
    audience_split_counter: Counter = Counter()
    for p in passes:
        aps = (p.get("coupon") or {}).get("audience_policies") or []
        n = len(aps)
        if n == 0:
            audience_split_counter["0 (no extraction)"] += 1
        elif n == 1:
            audience_split_counter["1"] += 1
        elif n == 2:
            audience_split_counter["2"] += 1
        else:
            audience_split_counter[f"{n}"] += 1

    def coverage_list(cov: dict, total: int) -> str:
        rows = []
        for k, v in cov.items():
            pct = round(100 * v / total) if total else 0
            rows.append(f'<li><span class="cov-label">{bilingual(k)}</span><span class="cov-frac">{v}/{total}</span><span class="cov-pct">{pct}%</span></li>')
        return f'<ul class="coverage">{"".join(rows)}</ul>'

    plat_counter = Counter(libcat["libraries"][lid]["platform"] for lid in libcat["libraries"])

    anomalies = []
    n_no_coupon = sum(1 for p in passes if not p.get("coupon"))
    anomalies.append(
        f"<li><b>{n_no_coupon}</b> 条 pass 没有 coupon 字段 — "
        f"<a href='policies.html'>see Policies</a></li>"
    )
    # form=discount with null value — generic discount language we couldn't quantify
    n_disc_null_ap = sum(
        1
        for p in passes
        for ap in (p.get("coupon") or {}).get("audience_policies") or []
        if ap.get("form") == "discount" and ap.get("value") is None
    )
    anomalies.append(
        f"<li><b>{n_disc_null_ap}</b> 条 audience_policy 是 <code>form=discount</code> 且 <code>value=null</code> — "
        f"<a href='data_quality.html#dq3'>see Data Quality §3</a></li>"
    )
    n_unknown_pt = sum(1 for p in passes if p.get("pass_type") == "unknown")
    anomalies.append(
        f"<li><b>{n_unknown_pt}</b> 条 pass 的 pass_type 是 unknown</li>"
    )
    # filter pairs whose slugs already merged
    attr_slugs = {a["slug"] for a in attr_data["attractions"]}
    n_dup = sum(1 for a, b in KNOWN_DUPLICATES if a in attr_slugs and b in attr_slugs)
    anomalies.append(
        f"<li><b>{n_dup}</b> 对 attraction slug 重复 — "
        f"<a href='duplicates.html'>see Duplicates</a></li>"
    )
    n_missing_price = n_attrs - attr_cov["Ticket price (any tier) · 票价(任一层级)"]
    anomalies.append(
        f"<li><b>{n_missing_price}</b> 个景点没有任何价格层级 — "
        f"<a href='gaps.html'>see Gaps</a></li>"
    )
    n_missing_desc = n_attrs - attr_cov["Description · 简介"]
    anomalies.append(
        f"<li><b>{n_missing_desc}</b> 个景点没有简介文字</li>"
    )

    # Precompute histogram HTML (dicts can't be inlined in f-strings)
    _coupon_form_label = {
        "free":             "FREE · 完全免费",
        "percent-off":      "Percent off · 百分比折扣",
        "dollar-off":       "Dollar off · 固定金额减免",
        "per-person-price": "Per-person price · 人头定价",
        "discount":         "Generic discount · 笼统折扣(无数值)",
    }
    _coupon_form_html = histogram_table(coupon_form_counter, sum(coupon_form_counter.values()) or 1, _coupon_form_label)
    _cap_matrix_html = capacity_matrix_html(cap_matrix, n_passes)
    _audience_split_html = histogram_table(audience_split_counter, n_passes)

    body = f"""
<h1 class="page-title">MuseumPapa <span class="font-serif">数据审计 Data Audit</span></h1>
<p class="subtitle">Non-technical verification view of the structured dataset behind the MuseumPapa frontend.</p>

{status_banner}

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
  <h3>Coupon form 分布 · {sum(coupon_form_counter.values())} audience-policy 条目</h3>
  {_coupon_form_html}
</section>

<section class="panel">
  <h3>Capacity 分布 · bucket × n 矩阵</h3>
  {_cap_matrix_html}
</section>

<section class="panel">
  <h3>Audience-split 分布 · audience_policies 条目数 per pass</h3>
  {_audience_split_html}
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
  <h3>数据质量信号 · 优先抽查项</h3>
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

def page_libraries(libs_data, libcat=None, branches_data=None) -> str:
    libs = libs_data["libraries"]
    n_libs = len(libs)
    plat_counter = Counter(L.get("platform") or "(unknown)" for L in libs)
    net_counter = Counter(L.get("network") or "(unknown)" for L in libs)
    res_counter = Counter(L.get("eligibility") or "(unknown)" for L in libs)
    # passes per library (requires catalog)
    pass_count_per_lib = {}
    if libcat:
        for lid, ldata in (libcat.get("libraries") or {}).items():
            pass_count_per_lib[lid] = len((ldata.get("passes") or {}))
    top_libs = sorted(pass_count_per_lib.items(), key=lambda x: -x[1])[:10] if pass_count_per_lib else []

    rows = []
    for L in libs:
        addr = L.get("address") or {}
        residency = esc(L.get("eligibility") or "")
        card_link = ""
        if L.get("card_page"):
            card_link = f'<a href="{esc(L["card_page"])}" target="_blank" rel="noopener">↗</a>'
        n_p = pass_count_per_lib.get(L["id"], "—")
        rows.append(f"""<tr data-search="{esc((L['id']+' '+L['name']+' '+L.get('town','')+' '+L.get('network','')).lower())}">
  <td class="mono">{esc(L['id'])}</td>
  <td>{esc(L['name'])}</td>
  <td>{esc(L.get('town',''))}</td>
  <td>{esc(L.get('network',''))}</td>
  <td><span class="badge badge-plat-{esc(L.get('platform',''))}">{esc(L.get('platform',''))}</span></td>
  <td class="truncate">{residency}</td>
  <td class="num">{n_p}</td>
  <td>{card_link}</td>
</tr>""")

    # Distribution panels (top of page)
    top_libs_html = "".join(
        f'<tr><td class="mono">{esc(lid)}</td>'
        f'<td class="bar-cell"><span class="bar">{"█" * round(40 * n / (top_libs[0][1] or 1))}</span></td>'
        f'<td class="num">{n}</td></tr>'
        for lid, n in top_libs
    ) if top_libs else ""

    body = f"""
<h1 class="page-title">Libraries · 59</h1>

<section class="dist-grid">
  <div class="panel dist-panel dist-wide">
    <h3>Platform · 数据平台分布</h3>
    {histogram_table(plat_counter, n_libs)}
  </div>
</section>

<h2 class="section-title">明细表 · Full table</h2>
<div class="toolbar"><input type="search" class="search-box" placeholder="filter rows... (id / name / town / network)" data-target="libs-table"></div>
<table id="libs-table" class="data-table">
<thead><tr><th>id</th><th>name</th><th>town</th><th>network</th><th>platform</th><th>residency</th><th class="num">passes</th><th>card page</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
<p class="foot-link"><a href="#" class="view-json-link" data-json-key="libraries">View full libraries.json</a></p>

{_multi_branch_panel(branches_data)}
"""
    blob = json.dumps({"libraries": libs_data}, ensure_ascii=False)
    return page_shell("Libraries", body, "libraries.html", data_blob=blob)


def _multi_branch_panel(branches_data) -> str:
    """Render a panel of sub-tables for libraries with >1 branch.

    Serves both audit needs at once (per [[audit-panel-must-serve-real-decision]]):
      (a) data correctness — every branch's name + street is a verifiable claim
      (b) user decision — these are the actual driveable addresses a physical
          pass holder needs.
    Nothing else lives here (no histograms, no branch × pass matrix).
    """
    if not branches_data:
        return ""
    by_parent: dict[str, list[dict]] = {}
    for b in branches_data.get("branches", []):
        by_parent.setdefault(b["parent_lib_id"], []).append(b)
    multi = {lid: bs for lid, bs in by_parent.items() if len(bs) > 1}
    if not multi:
        return ""
    sections = []
    for lid in sorted(multi):
        bs = sorted(multi[lid], key=lambda x: x["id"])
        rows = "".join(
            f'<tr><td class="mono">{esc(b["id"])}</td>'
            f'<td>{esc(b["name"])}</td>'
            f'<td>{esc(b["address"]["street"])}</td>'
            f'<td>{esc(b["address"]["city"])}</td>'
            f'<td>{esc(b["address"].get("zip") or "")}</td>'
            f'<td class="mono">{b["geo"]["lat"]:.4f}, {b["geo"]["lon"]:.4f}</td></tr>'
            for b in bs
        )
        sections.append(f"""
<h3 style="margin-top:18px">{esc(lid)} · {len(bs)} 分馆</h3>
<table class="data-table">
<thead><tr><th>branch_id</th><th>name</th><th>street</th><th>city</th><th>zip</th><th>geo</th></tr></thead>
<tbody>{rows}</tbody>
</table>""")
    return f"""
<h2 class="section-title">多分馆 lib · Branch breakdown</h2>
{"".join(sections)}
"""


# =========================================================================
# PAGE 3 — attractions.html
# =========================================================================

def _derive_coupon_summary(coupon: dict) -> str:
    """Module-level twin of the per-page _derive_summary helper.
    coupon.summary was removed in 6c61620, so we derive it on display."""
    if not coupon:
        return ""
    cap = coupon.get("capacity") or {}
    aps = coupon.get("audience_policies") or []
    parts = []
    n = cap.get("n")
    if cap.get("kind") == "people" and n is not None:
        parts.append(f"Up to {n}")
    elif cap.get("kind") == "vehicle":
        parts.append("Per vehicle")
    elif cap.get("kind") == "ticket" and n is not None:
        parts.append(f"{n} ticket(s)")
    for ap in aps:
        aud = ap.get("audience") or ""
        form = ap.get("form") or ""
        v = ap.get("value")
        if form == "free":
            seg = f"{aud} FREE" if aud and aud != "Everyone" else "FREE"
        elif form == "percent-off" and v is not None:
            seg = f"{aud} {v}% off" if aud and aud != "Everyone" else f"{v}% off"
        elif form == "dollar-off" and v is not None:
            seg = f"{aud} ${v} off" if aud and aud != "Everyone" else f"${v} off"
        elif form == "per-person-price" and v is not None:
            seg = f"{aud} ${v}/person" if aud and aud != "Everyone" else f"${v}/person"
        elif form == "discount":
            seg = f"{aud} discount" if aud and aud != "Everyone" else "discount"
        else:
            continue
        parts.append(seg)
    return " · ".join(parts)


def _build_coupon_compare(slug: str, passes_by_slug: dict, lib_by_id: dict) -> str:
    """Build a <details> coupon comparison table for one attraction (plan-9)."""
    matching = passes_by_slug.get(slug) or []
    if not matching:
        return '<p class="honest-gap">No passes found for this attraction.</p>'
    rows_html = []
    for mp in matching:
        lib_name = (lib_by_id.get(mp["library_id"]) or {}).get("name") or mp["library_id"]
        pickup = mp.get("pickup_method") or ""
        if pickup == "digital":
            method_label = "Email"
        elif pickup == "physical_at_branch":
            branches = mp.get("pickup_branches") or []
            method_label = f"Pickup at {branches[0]}" if branches else "Pickup at branch"
        else:
            method_label = pickup or "(unknown)"
        summary = _derive_coupon_summary(mp.get("coupon") or {}) or "(no extraction)"
        rows_html.append(
            f'<tr><td>{esc(lib_name)}</td>'
            f'<td>{esc(method_label)}</td>'
            f'<td><b>{esc(summary)}</b></td></tr>'
        )
    return (
        f'<details><summary>Coupon comparison · {len(matching)} library option(s)</summary>'
        '<table class="coupon-compare"><thead><tr>'
        '<th>Library</th><th>Pickup</th><th>Coupon</th></tr></thead><tbody>'
        + "".join(rows_html)
        + "</tbody></table></details>"
    )


def page_attractions(attr_data, passes_data=None, libs_data=None) -> str:
    attrs = attr_data["attractions"]
    slug_counts = Counter(A["slug"] for A in attrs)
    all_cats = sorted({c for A in attrs for c in (A.get("categories") or [])})

    # Build lookup tables for coupon comparison panel
    passes_list = (passes_data or {}).get("passes") or []
    # index passes by attraction_slug for O(1) lookup
    passes_by_slug: dict[str, list] = defaultdict(list)
    for _p in passes_list:
        passes_by_slug[_p["attraction_slug"]].append(_p)
    lib_by_id: dict[str, dict] = {}
    for _L in ((libs_data or {}).get("libraries") or []):
        lib_by_id[_L["id"]] = _L

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
        img_html = (
            f'<img class="hero-big" src="{esc(img_path)}" alt="" data-full="{esc(img_path)}">'
            if img_path else
            '<div class="hero-big noimg">封面图未抓取</div>'
        )

        sources = A.get("sources") or []
        n_libs = len(sources)

        dup_warn = ""
        if slug_counts[slug] > 1:
            dup_warn = '<div class="warn-row">⚠ 此 slug 与同一景点的另一条记录重复</div>'

        cats_html = " · ".join(esc(c) for c in (A.get("categories") or [])) or '<span class="honest-gap">未分类</span>'

        # Prices — two-layer schema:
        #   age_pricing: tiers by age (adult/youth/child/senior) — applies to anyone
        #   identity_pricing: tiers by status proof (student/educator/military)
        age_p = (price.get("age_pricing") or {}) if price else {}
        ident_p = (price.get("identity_pricing") or {}) if price else {}

        def _tier_price(layer: dict, key: str):
            t = layer.get(key)
            return t.get("price") if isinstance(t, dict) else None

        any_price = False
        # Main tiers — render only the ones that have a value.
        age_rows_html = []
        for k, label_en, label_zh in [
            ("adult",  "Adult",  "成人"),
            ("youth",  "Youth",  "青少年"),
            ("child",  "Child",  "儿童"),
            ("senior", "Senior", "老人"),
        ]:
            v = _tier_price(age_p, k)
            if v is None:
                continue
            any_price = True
            age_rows_html.append(
                f'<div class="kv"><span class="k">{label_en} · {label_zh}</span>'
                f'<span class="v verified">${esc(str(v))}</span></div>'
            )
        fua = age_p.get("free_under_age")
        if fua is not None:
            any_price = True
            age_rows_html.append(
                f'<div class="kv"><span class="k">Free under · 免费年龄</span>'
                f'<span class="v verified">age &lt; {fua}</span></div>'
            )
        family_v = price.get("family") if price else None
        if family_v is not None:
            any_price = True
            age_rows_html.append(
                f'<div class="kv"><span class="k">Family · 家庭通票</span>'
                f'<span class="v verified">${esc(str(family_v))}</span></div>'
            )

        # Identity-based waivers — show as a one-line note, ONLY entries that exist.
        identity_notes = []
        for k, label_en in [("student", "Student"), ("educator", "Educator"), ("military", "Military")]:
            v = _tier_price(ident_p, k)
            if v is not None:
                any_price = True
                identity_notes.append(f"{label_en} ${esc(str(v))}")
        identity_note_html = (
            f'<p class="price-note"><b>Waivers · 豁免:</b> {" · ".join(identity_notes)}</p>'
            if identity_notes else ""
        )

        notes = price.get("notes") if price else None
        notes_row_html = (
            f'<p class="price-note"><b>Notes · 备注:</b> {esc(notes)}</p>'
            if notes else ""
        )
        price_src = price.get("source_url") if price else None
        price_footer = (
            f'<div class="src-line">↗ 价格数据源: <a href="{esc(price_src)}" target="_blank" rel="noopener">{esc(price_src)}</a></div>'
            if price_src else
            ('<div class="src-line honest-gap">无价格数据(景点官网未公布 / 浮动定价 / 反爬拦截)</div>' if not any_price else '')
        )

        # Hours
        day_pairs = [("mon", "Mon · 周一"), ("tue", "Tue · 周二"), ("wed", "Wed · 周三"),
                     ("thu", "Thu · 周四"), ("fri", "Fri · 周五"),
                     ("sat", "Sat · 周六"), ("sun", "Sun · 周日")]
        hour_rows_html = []
        for k, lab in day_pairs:
            v = rh.get(k)
            if not v:
                hour_rows_html.append(f'<div class="kv kv-gap"><span class="k">{lab}</span><span class="v dash">-</span></div>')
            elif v.lower() == "closed":
                hour_rows_html.append(f'<div class="kv"><span class="k">{lab}</span><span class="v closed">Closed</span></div>')
            else:
                hour_rows_html.append(f'<div class="kv"><span class="k">{lab}</span><span class="v verified">{esc(v)}</span></div>')
        hours_status = hours.get("status") or ""
        hours_notes = hours.get("notes") or ""
        hours_src = hours.get("source_url") or ""
        # only show status row when it's NOT 'ok' (ok = boring, no audit value)
        hours_meta_html = ""
        if hours_status and hours_status != "ok":
            zh = {"varies": "varies · 跨多分馆,小时不一", "seasonal": "seasonal · 季节性开放"}.get(hours_status, "")
            hours_meta_html += f'<div class="kv kv-wide"><span class="k">Status · 状态</span><span class="v" style="color:var(--au)">{esc(hours_status)} · {esc(zh)}</span></div>'
        if hours_notes:
            hours_meta_html += f'<div class="kv kv-wide"><span class="k">Notes · 备注</span><span class="v">{esc(hours_notes)}</span></div>'
        hours_footer = (
            f'<div class="src-line">↗ 小时数据源: <a href="{esc(hours_src)}" target="_blank" rel="noopener">{esc(hours_src)}</a></div>'
            if hours_src else ''
        )

        desc = A.get("description") or ""
        phone = A.get("phone") or ""
        geo = A.get("geo") or {}
        geo_txt = f"{geo.get('lat'):.4f}, {geo.get('lon'):.4f}" if geo.get("lat") is not None else "无数据"
        website = A.get("website") or ""
        addr = A.get("address") or ""

        search_text = (slug + " " + (A.get("museum_name") or "") + " " + " ".join(A.get("categories") or [])).lower()

        sources_html = " · ".join(f'<code>{esc(s)}</code>' for s in sources)

        rows.append(f"""<article class="attr-card" data-search="{esc(search_text)}" data-categories="{esc(','.join(A.get('categories') or []))}">
  <header class="attr-header">
    <h2 class="attr-name">{esc(A.get('museum_name') or '')}</h2>
    <div class="attr-sub">
      <code class="slug">{esc(slug)}</code>
      <span class="meta-divider">·</span>
      <span class="cats">{cats_html}</span>
    </div>
    {dup_warn}
  </header>

  <div class="top-row">
    <div class="hero-side">{img_html}</div>
    <div class="meta-side">
      <div class="kv kv-wide"><span class="k">Address · 地址</span><span class="v">{esc(addr) if addr else '<span class="dash">-</span>'}</span></div>
      <div class="kv kv-wide"><span class="k">Geo · 经纬度</span><span class="v">{esc(geo_txt) if geo_txt != '无数据' else '<span class=dash>-</span>'}</span></div>
      <div class="kv kv-wide"><span class="k">Phone · 电话</span><span class="v">{f'<a href="tel:{esc(phone)}">{esc(phone)}</a>' if phone else '<span class="dash">-</span>'}</span></div>
      <div class="kv kv-wide"><span class="k">Website · 官网</span><span class="v">{f'<a href="{esc(website)}" target="_blank" rel="noopener">{esc(website)} ↗</a>' if website else '<span class="dash">-</span>'}</span></div>
    </div>
  </div>

  <section class="prices-block">
    <h3 class="block-title">Pricing · 票价</h3>
    {('<div class="kv-grid">' + "".join(age_rows_html) + "</div>") if age_rows_html else '<p class="honest-gap">No tier data</p>'}
    {identity_note_html}
    {notes_row_html}
    {price_footer}
  </section>

  <section class="hours-block">
    <h3 class="block-title">Hours · 营业时间</h3>
    <div class="kv-grid">{"".join(hour_rows_html)}</div>
    {hours_meta_html}
    {hours_footer}
  </section>

  <section class="sources-block">
    <h3 class="block-title">提供此 pass 的图书馆 <span class="block-meta">{n_libs} 个馆收录此景点</span></h3>
    <p class="sources-list">{sources_html}</p>
  </section>

  <section class="coupon-compare-block">
    {_build_coupon_compare(slug, passes_by_slug, lib_by_id)}
  </section>
</article>""")

    cat_options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in all_cats)

    # ── Distribution stats ─────────────────────────────────────────────
    n_attrs = len(attrs)
    # Price tier coverage — split into 2 named groups per family-user persona:
    #   CORE: adult / youth / child / student / educator
    #   SECONDARY: senior / military / family
    CORE_TIERS = [("adult","Adult · 成人"), ("youth","Youth · 年轻人"),
                  ("child","Child · 儿童"), ("student","Student · 学生"),
                  ("educator","Educator · 教师")]
    SECONDARY_TIERS = [("senior","Senior · 老人"), ("military","Military · 军人"),
                       ("family","Family · 家庭通票")]
    core_counter = Counter()
    secondary_counter = Counter()
    # Tier lookup map: which layer does each key live in?
    #   age_pricing: adult / youth / child / senior
    #   identity_pricing: student / educator / military
    #   top-level: family
    AGE_KEYS = {"adult", "youth", "child", "senior"}
    IDENT_KEYS = {"student", "educator", "military"}

    def _has_tier(price_block: dict, key: str) -> bool:
        if not price_block:
            return False
        if key == "family":
            return price_block.get("family") is not None
        if key in AGE_KEYS:
            tier = (price_block.get("age_pricing") or {}).get(key)
        elif key in IDENT_KEYS:
            tier = (price_block.get("identity_pricing") or {}).get(key)
        else:
            return False
        return isinstance(tier, dict) and tier.get("price") is not None

    for A in attrs:
        p = A.get("original_price") or {}
        for k, _ in CORE_TIERS:
            if _has_tier(p, k): core_counter[k] += 1
        for k, _ in SECONDARY_TIERS:
            if _has_tier(p, k): secondary_counter[k] += 1
    tier_label_map = {**dict(CORE_TIERS), **dict(SECONDARY_TIERS)}
    # Hours buckets — every attraction lands in exactly one of four buckets,
    # decided by whether we have a usable schedule we can show the user.
    #
    # Rule: status="varies" means we DID scrape the page but it says "no
    # single schedule applies, varies by sub-location" (umbrella attractions
    # like Trustees / MA State Parks, plus performance venues). For the
    # product user that's identical to "no time data" — we can't show them
    # when it's open. So those collapse into the Unknown bucket.
    #
    # A status="ok" record with ALL 7 days closed also lands here as
    # seasonal (some libraries' source data tags summer-only spots as ok).
    hours_status_counter = Counter()
    for A in attrs:
        h = A.get("hours")
        if not h:
            hours_status_counter["bucket_nodata"] += 1
            continue
        st = h.get("status")
        rh = h.get("regular_hours") or {}
        days = ['mon','tue','wed','thu','fri','sat','sun']
        n_closed = sum(1 for d in days if (rh.get(d) or '').lower() in ('closed', '', 'none'))
        if st == "varies":
            # No single schedule we can render — same UX as missing data.
            hours_status_counter["bucket_nodata"] += 1
        elif st == "seasonal" or (st == "ok" and n_closed == 7):
            hours_status_counter["bucket_seasonal"] += 1
        elif st == "ok" and n_closed == 0:
            hours_status_counter["bucket_open_daily"] += 1
        elif st == "ok" and n_closed > 0:
            hours_status_counter["bucket_partial"] += 1
        else:
            hours_status_counter["bucket_nodata"] += 1
    hours_label_map = {
        "bucket_open_daily": "Open daily · 每日开放",
        "bucket_partial":    "Closed days · 每周有休息日",
        "bucket_seasonal":   "Seasonal · 季节性",
        "bucket_nodata":     "Unknown · 无固定时间表",
    }
    # Categories — read straight from data layer (already normalized by build/categories.py)
    cat_canon_counter = Counter()  # canonical 7-class
    cat_counter = Counter()        # raw labels (categories_raw, kept for audit)
    for A in attrs:
        for c in A.get("categories") or []:
            cat_canon_counter[c] += 1
        for c in A.get("categories_raw") or []:
            cat_counter[c] += 1
    # Coverage of non-price fields
    cov_counter = Counter()
    for A in attrs:
        if (A.get("hero_image") or {}).get("local_path"): cov_counter["hero image"] += 1
        if has_numeric_price(A): cov_counter["price (any tier)"] += 1
        if A.get("hours"): cov_counter["hours"] += 1
        if A.get("description"): cov_counter["description"] += 1
        if A.get("phone"): cov_counter["phone"] += 1
        if A.get("geo"): cov_counter["geo"] += 1
        if A.get("address"): cov_counter["address"] += 1

    # Museum-side timed-entry policy — attraction property, NOT pass property.
    # Whether a visitor brings a library pass or pays full price, these
    # museums require an online time-slot reservation before showing up.
    mr_required_attrs = [
        a for a in attrs
        if isinstance(a.get("museum_reservation"), dict)
        and a["museum_reservation"].get("required")
    ]
    mr_rows_html = "".join(
        f'<tr><td class="mono">{esc(a["slug"])}</td>'
        f'<td>{esc((a.get("museum_name") or "")[:55])}</td>'
        f'<td><a href="{esc(a["museum_reservation"].get("url", ""))}" target="_blank" rel="noopener">booking page ↗</a></td></tr>'
        for a in sorted(mr_required_attrs, key=lambda x: x["slug"])
    )

    body = f"""
<h1 class="page-title">Attractions<span class="zh-sub">景点 · {n_attrs} 家可去地点</span></h1>
<p class="subtitle">本页从景点视角看数据:每条记录 = 一家真实世界的可去地点(博物馆、公园、剧院等),已经把不同图书馆对同一家景点的不同写法合并成一条。下方先给 4 张分布,再列出 {n_attrs} 家完整卡片明细。</p>

<section class="dist-grid">
  <div class="panel dist-panel">
    <h3>Price tier coverage · 票价层级覆盖率</h3>
    {histogram_table(core_counter | secondary_counter, n_attrs, tier_label_map)}
  </div>
  <div class="panel dist-panel">
    <h3>Hours · 营业模式分布</h3>
    {histogram_table(hours_status_counter, n_attrs, hours_label_map)}
  </div>
  <div class="panel dist-panel">
    <h3>Categories · 类别分布</h3>
    {histogram_table(cat_canon_counter, n_attrs)}
  </div>
  <div class="panel dist-panel">
    <h3>Field coverage · 字段覆盖率</h3>
    {histogram_table(cov_counter, n_attrs)}
  </div>
</section>

<section class="panel passes-section" id="a-mr">
  <h3>Timed-entry museums<span class="zh-sub">需要时段预约的景点 · {len(mr_required_attrs)} 家</span></h3>
  <p class="section-what"><b>What it is · 这是什么:</b> 这 {len(mr_required_attrs)} 家景点要求所有访客<b>事先在博物馆官网订时段</b>才能进——MFA、ICA、MOS、Children's Museum 等热门馆都是如此。这是 <b>景点的政策</b>,跟用户是否持图书馆 pass 没有关系:即使付全价,也一样要预约时段。Pass 只决定刷卡时付多少钱。</p>
  <table class="data-table">
    <thead><tr><th>slug</th><th>name</th><th>booking</th></tr></thead>
    <tbody>{mr_rows_html}</tbody>
  </table>
  <div class="section-meaning"><b>What it means · 含义:</b> 前端展示这些景点的卡片时,要在显眼处写一句 "⚠ 此馆需先到 [景点官网] 订时段",避免用户拿了 pass 就直奔过去被拦下。预约 URL 在 <code>attraction.museum_reservation.url</code> 字段里已经存好。<b>注意:</b>这跟 Passes 页 §7 "Date restrictions" 是两件事——§7 是图书馆和景点谈下的 pass 专属日期约束(blackout 等),这里是景点对所有人都生效的进馆流程。</div>
</section>

<h2 class="section-title">明细 · Full cards</h2>
<div class="toolbar">
  <input type="search" class="search-box" placeholder="filter (slug / name / category)..." data-target="attr-list">
  <select class="filter-select" data-target="attr-list" data-filter-attr="data-categories">
    <option value="">All categories</option>
    {cat_options}
  </select>
</div>
<div id="attr-list" class="attr-list">{"".join(rows)}</div>
"""
    # The Attractions content is served at both index.html (landing) and used to
    # be at attractions.html — keep the 'current' marker pointing at index.html
    # so the nav highlights correctly on the landing URL.
    return page_shell("Attractions", body, "index.html"), missing_image


# =========================================================================
# PAGE 4 — passes.html  (boss-readable summary, replaces the old policies page)
# =========================================================================

def _bar_row(label_en: str, label_zh: str, count: int, total: int, note: str = "") -> str:
    """Single row in a horizontal-bar distribution table."""
    pct = (count / total * 100) if total else 0
    bar_len = max(1, int(round(pct / 2.5))) if count else 0
    bar = "█" * bar_len
    note_html = f'<div class="meaning-note">{note}</div>' if note else ""
    return (
        f'<tr><td><b>{esc(label_en)}</b>'
        f'<span class="zh-sub">{esc(label_zh)}</span>{note_html}</td>'
        f'<td class="bar-cell"><span class="bar">{bar}</span></td>'
        f'<td class="num">{count}</td><td class="pct">{pct:.0f}%</td></tr>'
    )


def _passes_section(anchor: str, title_en: str, title_zh: str, what: str,
                    bars_html: str, meaning_html: str) -> str:
    """One section on the Passes page — what / distribution / meaning."""
    return f"""
<section class="panel passes-section" id="{anchor}">
  <h3>{esc(title_en)}<span class="zh-sub">{esc(title_zh)}</span></h3>
  <p class="section-what"><b>What it is · 这是什么:</b> {what}</p>
  <table class="histogram passes-dist">{bars_html}</table>
  <div class="section-meaning"><b>What it means · 含义:</b>{meaning_html}</div>
</section>
"""


def page_passes(passes_data, libs_data, attr_data) -> str:
    """Boss-readable summary of the 1026 pass rows.

    Each section answers three questions, in this order:
      1. What is this dimension?
      2. How is it distributed across the 1026 passes?
      3. What does that distribution mean for the product?

    No per-row tables — those belong on Data Quality for actionable items.
    """
    passes = passes_data["passes"]
    libs = libs_data["libraries"]
    n_passes = len(passes)
    lib_platform = {L["id"]: L.get("platform") for L in libs}

    n_libs_with_passes = len({p["library_id"] for p in passes})
    n_attrs_with_passes = len({p["attraction_slug"] for p in passes})
    passes_per_lib = n_passes / n_libs_with_passes if n_libs_with_passes else 0
    attrs_per_lib_mean = n_passes / n_libs_with_passes if n_libs_with_passes else 0
    libs_per_attr_mean = n_passes / n_attrs_with_passes if n_attrs_with_passes else 0

    # === Section 1: 什么是一张 Pass ===
    s1_what = (
        "每条 pass = 一家图书馆 × 一家景点 × 一份优惠条件。同一家景点可能在多个图书馆出现,"
        "但每条 pass 的取卡方式、折扣力度、能用几人都可能不同——所以不会被去重成一条。"
    )
    n_attrs_total = len(attr_data["attractions"])
    s1_bars = (
        f'<tr><td><b>Total passes</b><span class="zh-sub">优惠券总数</span></td>'
        f'<td></td><td class="num">{n_passes}</td><td class="pct">—</td></tr>'
        f'<tr><td><b>Libraries covered</b><span class="zh-sub">覆盖图书馆</span></td>'
        f'<td></td><td class="num">{n_libs_with_passes} / {len(libs)}</td>'
        f'<td class="pct">{n_libs_with_passes/len(libs)*100:.0f}%</td></tr>'
        f'<tr><td><b>Attractions covered</b><span class="zh-sub">覆盖景点</span></td>'
        f'<td></td><td class="num">{n_attrs_with_passes} / {n_attrs_total}</td>'
        f'<td class="pct">{n_attrs_with_passes/n_attrs_total*100:.0f}%</td></tr>'
    )
    s1_meaning = (
        "<ul>"
        "<li><b>分布是稠密的</b>——59 个馆里 100% 都至少有 pass,97 个景点平均每个被 10.6 个馆覆盖。"
        "对持单卡用户来说,你能用的 pass 平均有 17 张;对持多卡(运营方 5 张)用户,数量乘到 ~85 张。</li>"
        "<li><b>同景点跨馆条件不同是常态</b>——比如 Salem Witch Museum 在 12 个馆,实际折后价有 4 档($13.25 / $13.5 / $13.75 / $14)。"
        "Pass 不去重正是为了让多卡用户能横向对比。</li>"
        "</ul>"
    )

    # === Section 2: 取卡途径 · Platform ===
    plat_passes = Counter(lib_platform.get(p["library_id"], "unknown") for p in passes)
    plat_libs = Counter(L.get("platform") for L in libs)
    s2_what = (
        "数据从 3 个图书馆系统抓回来。哪个馆走哪个平台不是我们选的——"
        "是图书馆自己买的产品。这一点决定了 <b>能不能拿到实时库存</b>。"
    )
    s2_bars = ""
    for plat_id, plat_en, plat_zh in [
        ("assabet", "Assabet", "Assabet"),
        ("libcal", "LibCal", "LibCal · Springshare"),
        ("museumkey", "MuseumKey", "MuseumKey"),
    ]:
        n_p = plat_passes.get(plat_id, 0)
        n_l = plat_libs.get(plat_id, 0)
        s2_bars += _bar_row(
            f"{plat_en}  ({n_l} libraries)",
            f"{plat_zh}  ·  {n_l} 家馆",
            n_p, n_passes,
        )
    s2_meaning = (
        "<ul>"
        "<li><b>Assabet Interactive</b> · 全 MA 公共图书馆通用的 pass 预订平台,覆盖 52 家小型馆。"
        "HTML 暴露日历,我们能解析出 <code>available / limited / booked</code> 三态。<b>有实时库存。</b></li>"
        "<li><b>LibCal (Springshare)</b> · 中大型馆产品。BPL、Cambridge、Brookline、Braintree、Milton 用。"
        "日历通过 institution 端点取,3 种状态合并为 available/booked。<b>有实时库存。</b></li>"
        "<li><b>MuseumKey</b> · 商业 SaaS,要图书馆卡登录才能看 pass。Cohasset 和 Hingham 用。"
        "我们只能拿到 catalog(景点列表、benefit 文本),<b>没有实时库存</b>——用户看到这两个馆的 pass 时,"
        "日历位置是空白,要打电话或上馆里现场查。</li>"
        "</ul>"
    )

    # === Section 3: 怎么取 (pass_type) ===
    pt = Counter(p["pass_type"] for p in passes)
    s3_what = (
        "<code>pass_type</code> 描述用户怎么把券拿到手——纯线上、还是要去馆里。"
        "这个差异直接影响产品体验:digital 是抢菜模式,physical 是有提前量但更稳。"
    )
    s3_bars = (
        _bar_row("digital · Email-delivered", "邮件即时收券码 / PDF",
                 pt.get("digital", 0), n_passes)
        + _bar_row("physical-coupon · Pick up paper coupon", "去馆领纸券",
                   pt.get("physical-coupon", 0), n_passes)
        + _bar_row("physical-circ · Borrow physical pass", "借实体卡,看完归还",
                   pt.get("physical-circ", 0), n_passes)
    )
    s3_meaning = (
        "<ul>"
        "<li><b>57% 是 digital</b>——填表后邮件秒到,可以当天预约当天用。"
        "前端配实时日历后,这部分是体验最好的 pass。</li>"
        "<li><b>26% 是 physical-coupon</b>(纸券)——一般要 24-48h 才能拿到,适合提前 1-2 天规划。"
        "<li><b>17% 是 physical-circ</b>(实体卡)——占用图书馆的循环库存,看完要还,适合提前 3-7 天约。"
        "在我们的库存逻辑里,这种 pass 看完没还回来之前,日历就是 'booked'。</li>"
        "</ul>"
    )

    # === Section 4: 给什么折扣 (form) ===
    forms = Counter()
    n_ap = 0
    for p in passes:
        for ap in p["coupon"]["audience_policies"]:
            forms[ap["form"]] += 1
            n_ap += 1
    s4_what = (
        "每条 pass 的 <code>audience_policies</code> 列表里有 1-3 条折扣描述(共 "
        f"<b>{n_ap}</b> 条),每条用 <code>form</code> 字段标明折扣类型。"
        "前端就是根据这 5 类决定怎么把优惠串成一句话给用户。"
    )
    s4_bars = (
        _bar_row("Per-person price", "固定金额 · 如 $10/人",
                 forms.get("per-person-price", 0), n_ap)
        + _bar_row("Percent off", "百分比折扣 · 如 50% off",
                   forms.get("percent-off", 0), n_ap)
        + _bar_row("FREE", "完全免费",
                   forms.get("free", 0), n_ap)
        + _bar_row("Vague discount", "笼统折扣 · 原文无具体数值",
                   forms.get("discount", 0), n_ap)
        + _bar_row("Dollar off", "减额 · 如 $5 off",
                   forms.get("dollar-off", 0), n_ap)
    )
    s4_meaning = (
        "<ul>"
        "<li><b>前两类合计 71%(per-person 37% + percent-off 34%)</b>——这部分我们能直接给出"
        "'每人多少钱'或'省百分之几',用户心算对比原价,决策成本最低。</li>"
        "<li><b>FREE 20%</b>——pass 类型里最强的优惠形态,值得在 UI 上突出。</li>"
        "<li><b>vague discount 6%(90 条)</b>——图书馆原文只说 'discounted admission' 或 'family rate',"
        "上游本来就没数字。属表达问题不是抽取 bug;前端只能显示'有折扣',无法说省多少。</li>"
        "<li><b>$N off 仅 2%</b>——固定减额罕见,通常出现在低价景点(Concord Museum $5 off 这种)。</li>"
        "</ul>"
    )

    # === Section 5: capacity ===
    # Bucketing rule (display only — does not mutate passes.json):
    #   "Headcount"   = kind=people, OR kind=ticket with n=1 (a single ticket
    #                   is functionally the same as admitting 1 person).
    #   "Per vehicle" = kind=vehicle (all default to n=1).
    #   "Tickets"     = kind=ticket with n>=2 (theater pairs, $N tickets).
    #   "Unspecified" = kind=unspecified.
    head_n_dist = Counter()      # n → count for the Headcount bucket
    n_head = n_vehicle = n_ticket = n_unspec = 0
    for p in passes:
        c = p["coupon"]["capacity"]
        k, n = c["kind"], c["n"]
        if k == "people" or (k == "ticket" and n == 1):
            n_head += 1
            if n is not None:
                head_n_dist[n] += 1
        elif k == "vehicle":
            n_vehicle += 1
        elif k == "ticket":  # n != 1
            n_ticket += 1
        else:
            n_unspec += 1
    s5_what = (
        "<code>capacity</code> 描述一次能带几个人。两个字段:"
        "<code>kind</code>(算人 / 算车 / 算票 / 未明示)和 <code>n</code>(数量)。"
        "用户看到 'Up to 4' 那个数字就是从这来的。<b>单张票 (ticket n=1) 等同于 1 人,并入 Headcount 桶。</b>"
    )
    s5_bars = (
        _bar_row("Headcount",
                 f"按人数 · 集中在 2/4/6 三档(各 {head_n_dist.get(2,0)} / {head_n_dist.get(4,0)} / {head_n_dist.get(6,0)} 条)",
                 n_head, n_passes)
        + _bar_row("Per vehicle",
                   "按车 · MA State Parks 等户外公园场景",
                   n_vehicle, n_passes)
        + _bar_row("Tickets (≥ 2)",
                   "按张 · 剧院/演出常见(2-4 张戏票)",
                   n_ticket, n_passes)
        + _bar_row("Unspecified",
                   "未明示 · 上游原文没说人数",
                   n_unspec, n_passes)
    )
    s5_meaning = (
        "<ul>"
        f"<li><b>{n_head}/{n_passes} 是按人数</b>(已并入单张票 n=1 的 27 条),"
        f"其中 'Up to 4' 是众数({head_n_dist.get(4,0)} 条,占 Headcount 桶 {head_n_dist.get(4,0)/max(n_head,1)*100:.0f}%)——"
        "对应典型的两大一小家庭出行规模。'Up to 6' 排第二。</li>"
        f"<li><b>Per vehicle {n_vehicle} 张</b>全部默认 1 辆车(原文从不写数字)。"
        "用于 MA State Parks 这种户外公园场景。</li>"
        f"<li><b>Tickets {n_ticket} 张</b>限张数 ≥ 2 · 多见于剧院/演出(2-4 张戏票)。</li>"
        f"<li><b>Unspecified {n_unspec} 张</b>——经子代理逐条复核(见 Data Quality §unspec),"
        "35 条是 by-audience(各受众自己带 count,全局 n 无意义),9 条是 family-tier 整张通票,"
        "16 条是上游原文真模糊。这部分不是抽取 bug,是 schema 设计选择 / 上游限制。</li>"
        "</ul>"
    )

    # === Section 6: audience-split ===
    # Three product-relevant buckets (the boss only cares about adult-vs-kid):
    #   1. All same        — single audience_policy, everyone gets identical terms
    #   2. Adult / Child differ — two policies that effectively split adult vs.
    #      child. Captures (Adult, Child), (Adult, Youth), (Child, Everyone),
    #      (Everyone, Youth) — Youth is functionally a teen-kid label.
    #   3. Other            — everything else (Senior tiers, Student/Military
    #      specials, 3+ audience policies). Low signal for the kids-out product.
    ADULT_CHILD_PAIRS = {
        frozenset(("Adult", "Child")),
        frozenset(("Adult", "Youth")),
        frozenset(("Child", "Everyone")),
        frozenset(("Everyone", "Youth")),
    }
    n_same = n_ac = n_other = 0
    for p in passes:
        aps = p["coupon"]["audience_policies"]
        if len(aps) <= 1:
            n_same += 1
        elif len(aps) == 2 and frozenset(ap.get("audience") for ap in aps) in ADULT_CHILD_PAIRS:
            n_ac += 1
        else:
            n_other += 1
    s6_what = (
        "我们关心的不是 audience_policies 列表有多长,而是这张 pass <b>对大人和小孩的折扣是否一样</b>。"
        "据此把所有 pass 分三类。"
    )
    s6_bars = (
        _bar_row("Everyone same", "所有人享同折扣 · 不区分大小",
                 n_same, n_passes)
        + _bar_row("Adult / Child differ", "成人 / 小孩待遇不同 · 典型 Adult $X + Child <18 free",
                   n_ac, n_passes)
        + _bar_row("Other", "其他 · Senior / Student / Military 等专门档,或 3+ 档拆分",
                   n_other, n_passes)
    )
    s6_meaning = (
        "<ul>"
        f"<li><b>{n_same/n_passes*100:.0f}% Everyone same</b>——一刀切,UI 一句话说清。</li>"
        f"<li><b>{n_ac/n_passes*100:.0f}% Adult/Child differ</b>——产品最有信号的形态。"
        "能告诉用户\"大人 $X、孩子免费\",带娃出行的决策价值远大于\"大家都 50%\"。"
        "前端值得在卡片上把这层差异显式渲染。</li>"
        f"<li><b>{n_other/n_passes*100:.0f}% Other</b>——Senior / Student / Military 等专门档,"
        "或 3+ 档复合拆分。在当前 NorthShore 带娃用户场景下信号偏弱,UI 上折叠展示即可。</li>"
        "</ul>"
    )

    # === Section 7: date restrictions (pass-side rules) ===
    # blackout / weekdays-only / seasonal are pass-side rules negotiated
    # between the library and the attraction. Museum-side timed-entry
    # (museum requires reservation regardless of pass) is an attraction
    # property, surfaced on the Attractions page, not here.
    restr_counter = Counter()
    n_date_restricted = 0
    for p in passes:
        r = p.get("restrictions") or {}
        if r.get("blackout_dates"): restr_counter["blackout"] += 1
        if r.get("weekdays_only"): restr_counter["weekdays_only"] += 1
        if r.get("seasonal"): restr_counter["seasonal"] += 1
        if r.get("blackout_dates") or r.get("weekdays_only") or r.get("seasonal"):
            n_date_restricted += 1
    s7_what = (
        "这一维度回答<b>哪些日期能用这张 pass</b>。三种形态:整段季节才开放、特定黑名单日不让用、仅工作日。"
        f"全部 {n_passes} 张中 <b>{n_date_restricted}</b> 张带日期约束;其余任何一天都可用。"
        "前端会把这些日子在日历上标 ⚠ 但不会把 pass 整张藏掉。"
    )
    denom_7 = n_date_restricted if n_date_restricted else 1
    s7_bars = (
        _bar_row("Seasonal · 季节性",
                 "夏/秋限定开放 · 户外岛屿、季节公园",
                 restr_counter["seasonal"], denom_7)
        + _bar_row("Blackout dates · 黑名单日",
                   "特定日期禁用 · 节假日 / 特展日",
                   restr_counter["blackout"], denom_7)
        + _bar_row("Weekdays only · 仅工作日",
                   "周末不可用 · 多见于剧院 / 教育型场所",
                   restr_counter["weekdays_only"], denom_7)
    )
    s7_meaning = (
        "<ul>"
        f"<li><b>{n_date_restricted} / {n_passes} 张({n_date_restricted/n_passes*100:.1f}%)</b>带日期约束——比例不高,但每条都是日历层面的硬约束,前端不能不展示。</li>"
        f"<li><b>Seasonal {restr_counter['seasonal']} 张</b>占多数,典型场景:Boston Harbor Islands、Crane Beach 这种夏/秋限定的户外目的地。winter 时用户能看到 pass 但日历全灰。</li>"
        f"<li><b>Blackout {restr_counter['blackout']} 张</b>——通常是图书馆和景点谈下\"特定日子不让用\"的协议(节假日、特展开幕)。前端把这些日期日历格变 ⚠,点开告诉用户原因。</li>"
        f"<li><b>Weekdays only {restr_counter['weekdays_only']} 张</b>——周末不可用,常见于剧院或教育型场所。</li>"
        "</ul>"
    )


    body = f"""
<h1 class="page-title">Passes<span class="zh-sub">优惠券 · 7 个角度看 {n_passes} 条 pass</span></h1>
<p class="subtitle">每张 pass = 1 家图书馆 × 1 家景点 × 1 份优惠条件。本页从 7 个维度告诉你这 {n_passes} 条 pass 是什么、分布怎样、对产品意味着什么。下方每节按 <b>What it is · 分布 · What it means</b> 三段写,跳过 ID 字段——明细查 <a href="#schema">Schema</a>,边界案例查 <a href="#data-quality">Data Quality</a>。"博物馆是否需要时段预约"是景点属性、不是 pass 属性(无论持券与否都得预约),所以它放在 <a href="#attractions">Attractions</a> 页。</p>

{_passes_section("p1", "1 · What is a Pass", "什么是一张 Pass", s1_what, s1_bars, s1_meaning)}
{_passes_section("p2", "2 · Acquisition path (Platform)", "取卡途径 · 数据来自哪 3 个系统", s2_what, s2_bars, s2_meaning)}
{_passes_section("p3", "3 · How the user picks it up", "怎么取 · digital / physical-coupon / physical-circ", s3_what, s3_bars, s3_meaning)}
{_passes_section("p4", "4 · What discount form", "给什么折扣 · 5 类 form 分布", s4_what, s4_bars, s4_meaning)}
{_passes_section("p5", "5 · How many people fit", "能用几人 · capacity", s5_what, s5_bars, s5_meaning)}
{_passes_section("p6", "6 · Audience split", "人群拆分 · 1 / 2 / 3 类各享不同待遇", s6_what, s6_bars, s6_meaning)}
{_passes_section("p7", "7 · Date restrictions", "日期约束 · 哪些日子能用这张 pass", s7_what, s7_bars, s7_meaning)}
"""
    return page_shell("Passes", body, "passes.html")


# =========================================================================
# PAGE 4 (legacy) — policies.html
# =========================================================================

def page_policies(passes_data, libs_data, attr_data) -> str:
    passes = passes_data["passes"]
    # Group passes by (capacity-bucket, form-bucket) — 3 × 5 = 15 cells.
    by_pid: dict[str, list] = defaultdict(list)
    cell_counts: dict[tuple[str, str], int] = {}
    for p in passes:
        sig = signature(p)
        pid = f"P_{sig[0]}_{sig[1]}"
        by_pid[pid].append(p)
        cell_counts[sig] = cell_counts.get(sig, 0) + 1

    # Pattern metadata in matrix order, only non-empty cells.
    pattern_meta = []
    for cap in CAP_BUCKETS:
        for form in FORM_BUCKETS:
            n = cell_counts.get((cap, form), 0)
            if n == 0: continue
            pid = f"P_{cap}_{form}"
            en, zh = signature_name((cap, form))
            pattern_meta.append((pid, en, zh, n))

    # TOC
    toc_items = "".join(
        f'<a href="#{pid}" class="toc-item">{pid}<br><small>{esc(en)}</small><span class="toc-n">{n}</span></a>'
        for pid, en, zh, n in pattern_meta
    )

    def _derive_summary(coupon: dict) -> str:
        """Build a one-line human summary from the coupon structure.
        coupon.summary is no longer stored (removed in 6c61620) — derive on display."""
        if not coupon:
            return ""
        cap = coupon.get("capacity") or {}
        aps = coupon.get("audience_policies") or []
        parts = []
        n = cap.get("n")
        if cap.get("kind") == "people" and n is not None:
            parts.append(f"Up to {n}")
        elif cap.get("kind") == "vehicle":
            parts.append("Per vehicle")
        elif cap.get("kind") == "ticket" and n is not None:
            parts.append(f"{n} ticket(s)")
        for ap in aps:
            aud = ap.get("audience") or ""
            form = ap.get("form") or ""
            v = ap.get("value")
            if form == "free":
                seg = f"{aud} FREE" if aud and aud != "Everyone" else "FREE"
            elif form == "percent-off" and v is not None:
                seg = f"{aud} {v}% off" if aud and aud != "Everyone" else f"{v}% off"
            elif form == "dollar-off" and v is not None:
                seg = f"{aud} ${v} off" if aud and aud != "Everyone" else f"${v} off"
            elif form == "per-person-price" and v is not None:
                seg = f"{aud} ${v}/person" if aud and aud != "Everyone" else f"${v}/person"
            elif form == "discount":
                seg = f"{aud} discount" if aud and aud != "Everyone" else "discount"
            else:
                continue
            parts.append(seg)
        return " · ".join(parts)

    def render_pass_article(p: dict, idx: int) -> str:
        lib = p["library_id"]
        slug = p["attraction_slug"]
        coupon = p.get("coupon") or {}
        summary = _derive_summary(coupon)
        aps = coupon.get("audience_policies") or []
        cap = coupon.get("capacity") or {}
        restrictions = p.get("restrictions") or {}

        # Build coupon details
        cap_str = ""
        if cap:
            kind = cap.get("kind", "unspecified")
            n = cap.get("n")
            cap_str = f'<span class="ext">capacity <b>{esc(kind)}{(" ×"+str(n)) if n is not None else ""}</b></span>'

        ap_parts = []
        for ap in aps:
            audience = ap.get("audience", "")
            form = ap.get("form", "")
            value = ap.get("value")
            if form == "free":
                amount = "FREE"
            elif form == "percent-off" and value is not None:
                amount = f"{value}% off"
            elif form == "dollar-off" and value is not None:
                amount = f"${value} off"
            elif form == "per-person-price" and value is not None:
                amount = f"${value}"
            else:
                amount = "discount"
            ap_parts.append(f'<span class="ext badge badge-disc-{esc(form)}">{esc(audience)} {esc(amount)}</span>')

        restr_parts = []
        if restrictions:
            for k, v in restrictions.items():
                if v:
                    restr_parts.append(f'<span class="badge badge-excl">{esc(k)}</span>')

        src_link = ""
        if p.get("source_url"):
            src_link = f'<a href="{esc(p["source_url"])}" target="_blank" rel="noopener">↗ source</a>'

        search_text = (lib + " " + slug + " " + summary).lower()[:400]
        return f"""<article class="policy-row" data-search="{esc(search_text)}">
  <header>
    <span class="lib-arrow-slug"><b>{esc(lib)}</b> → <code>{esc(slug)}</code></span>
    {pass_type_badge(p.get("pass_type", "unknown"))}
    {"".join(restr_parts)}
  </header>
  <p class="raw"><b>{esc(summary) if summary else '<i class="honest-gap">(no extraction)</i>'}</b></p>
  <p class="extracted">{cap_str} {"".join(ap_parts)}</p>
  <p class="src-link">{src_link}</p>
</article>"""

    # Collapse helper: render first 10 rows inline, rest inside <details>.
    # Keeps the page scan-able while preserving every row for drill-down.
    PREVIEW_N = 10
    def render_collapsed(plist: list) -> str:
        if not plist:
            return ""
        head_html = "".join(render_pass_article(p, i) for i, p in enumerate(plist[:PREVIEW_N]))
        if len(plist) <= PREVIEW_N:
            return head_html
        rest_html = "".join(render_pass_article(p, i) for i, p in enumerate(plist[PREVIEW_N:], start=PREVIEW_N))
        return (
            head_html
            + f'<details class="more-rows"><summary>+{len(plist) - PREVIEW_N} more rows</summary>'
            + rest_html
            + "</details>"
        )

    # Build sections (By Pattern view)
    pattern_sections = []
    for pid, en, zh, n in pattern_meta:
        rows = render_collapsed(by_pid.get(pid, []))
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
        rows = render_collapsed(plist)
        attr_sections.append(f'<section class="pattern-section" id="A_{esc(slug)}"><h2 class="pattern-header"><code>{esc(slug)}</code> <span class="pattern-meta">{len(plist)} passes</span></h2><div class="pattern-rows">{rows}</div></section>')

    # By Library view
    by_lib: dict[str, list] = defaultdict(list)
    for p in passes:
        by_lib[p["library_id"]].append(p)
    lib_sections = []
    for lid in sorted(by_lib.keys()):
        plist = by_lib[lid]
        rows = render_collapsed(plist)
        lib_sections.append(f'<section class="pattern-section" id="L_{esc(lid)}"><h2 class="pattern-header"><b>{esc(lid)}</b> <span class="pattern-meta">{len(plist)} passes</span></h2><div class="pattern-rows">{rows}</div></section>')

    # ── Distribution stats for policies page (plan-9 coupon model) ───────
    n_passes = len(passes)
    pt_counter = Counter(p.get("pass_type") or "(unknown)" for p in passes)
    # coupon form distribution (per audience_policy entry)
    pol_form_counter: Counter = Counter()
    for p in passes:
        for ap in (p.get("coupon") or {}).get("audience_policies") or []:
            pol_form_counter[ap.get("form", "discount")] += 1
    # capacity bucket × n matrix (people+ticket → headcount, vehicle, other)
    pol_cap_matrix: dict[str, Counter] = {
        "headcount": Counter(), "vehicle": Counter(), "other": Counter(),
    }
    for p in passes:
        cap = (p.get("coupon") or {}).get("capacity") or {}
        k = cap.get("kind") or "unspecified"
        bucket = "headcount" if k in ("people", "ticket") else ("vehicle" if k == "vehicle" else "other")
        n = cap.get("n")
        pol_cap_matrix[bucket][n if n is not None else "null"] += 1
    # restrictions distribution
    restr_counter: Counter = Counter()
    for p in passes:
        r = p.get("restrictions") or {}
        for k, v in r.items():
            if v:
                restr_counter[k] += 1
    max_n = max((n for _, _, _, n in pattern_meta), default=1)
    pattern_count_table = "".join(
        f'<tr><td class="mono"><a href="#{pid}">{pid}</a></td>'
        f'<td>{esc(en)}</td>'
        f'<td class="bar-cell"><span class="bar">{"█" * round(40 * n / max(1, max_n))}</span></td>'
        f'<td class="num">{n}</td><td class="pct">{round(100 * n / n_passes)}%</td></tr>'
        for pid, en, zh, n in pattern_meta
    )

    # 3 × 5 matrix view — quick visual summary above the pattern detail list.
    matrix_html_rows = []
    matrix_html_rows.append(
        '<tr><th></th>'
        + ''.join(f'<th class="num">{FORM_LABEL_EN[f]}<span class="zh-sub">{FORM_LABEL_ZH[f]}</span></th>' for f in FORM_BUCKETS)
        + '<th class="num">total</th></tr>'
    )
    for cap in CAP_BUCKETS:
        cells = []
        row_total = 0
        for form in FORM_BUCKETS:
            n = cell_counts.get((cap, form), 0)
            row_total += n
            pid = f"P_{cap}_{form}"
            cells.append(
                f'<td class="num"><a href="#{pid}">{n}</a></td>' if n else '<td class="num"></td>'
            )
        if row_total == 0: continue
        label = f'<th>{CAP_LABEL_EN[cap]}<span class="zh-sub">{CAP_LABEL_ZH[cap]}</span></th>'
        matrix_html_rows.append(f'<tr>{label}{"".join(cells)}<td class="num"><b>{row_total}</b></td></tr>')
    pattern_matrix_html = (
        '<table class="data-table capacity-matrix">'
        f'<thead>{matrix_html_rows[0]}</thead>'
        f'<tbody>{"".join(matrix_html_rows[1:])}</tbody>'
        '</table>'
    )
    # Precompute histogram HTML (dicts can't be inlined in f-strings)
    _pt_label = {
        "digital": "Email · 邮件直接收",
        "physical-coupon": "Pickup · 馆里取一次",
        "physical-circ": "Borrow · 馆里借,看完还回去",
        "unknown": "Pass · 未分类",
    }
    _form_label = {
        "free":             "FREE · 完全免费",
        "percent-off":      "Percent off · 百分比折扣",
        "dollar-off":       "Dollar off · 固定金额减免",
        "per-person-price": "Per-person price · 人头定价",
        "discount":         "Generic discount · 笼统折扣(无数值)",
    }
    _pol_pt_html = histogram_table(pt_counter, n_passes, _pt_label)
    _pol_form_html = histogram_table(pol_form_counter, sum(pol_form_counter.values()) or 1, _form_label)
    _pol_cap_html = capacity_matrix_html(pol_cap_matrix, n_passes)
    _pol_restr_html = histogram_table(restr_counter, n_passes)

    body = f"""
<h1 class="page-title">Policies · {n_passes} passes · {len(pattern_meta)} patterns</h1>

<section class="dist-grid">
  <div class="panel dist-panel dist-wide">
    <h3>Pass 形式</h3>
    {_pol_pt_html}
  </div>
  <div class="panel dist-panel">
    <h3>Coupon form 分布</h3>
    {_pol_form_html}
  </div>
  <div class="panel dist-panel">
    <h3>Capacity 分布 · bucket × n 矩阵</h3>
    {_pol_cap_html}
  </div>
  <div class="panel dist-panel">
    <h3>Restrictions 分布</h3>
    {_pol_restr_html}
  </div>
  <div class="panel dist-panel dist-wide">
    <h3>Coupon patterns · 限制 × 优惠</h3>
    {pattern_matrix_html}
  </div>
  <div class="panel dist-panel dist-wide">
    <h3>Coupon patterns · ranked</h3>
    <table class="histogram"><thead><tr><th>id</th><th>name</th><th></th><th class="num">n</th><th class="pct">%</th></tr></thead><tbody>{pattern_count_table}</tbody></table>
  </div>
</section>

<h2 class="section-title">明细 · Full pattern sections</h2>

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

    # Build minimal data blob: per-pass coupon raw JSON, key="cou_<lib>_<slug>"
    blob_d = {}
    for p in passes:
        rp = read_raw("pass_coupons", f"{p['library_id']}_{p['attraction_slug']}")
        if rp:
            blob_d[f"cou_{p['library_id']}_{p['attraction_slug']}"] = rp
    blob = json.dumps(blob_d, ensure_ascii=False)
    return page_shell("Policies", body, "policies.html", data_blob=blob), len(pattern_meta)


# =========================================================================
# PAGE 5 — gaps.html
# =========================================================================

def page_gaps(attr_data, libs_data, passes_data=None) -> str:
    attrs = attr_data["attractions"]
    slug_counts = Counter(A["slug"] for A in attrs)
    n_attrs = len(attrs)
    passes = (passes_data or {}).get("passes", []) if passes_data else []
    n_passes = len(passes)

    # Each entry: key -> (en_title, zh_title, denominator, zh_business_impact)
    GAP_META = {
        "Missing price data": (
            "Attractions missing original_price",
            "缺失票价的景点",
            n_attrs,
            "用户在前端看不到原价对比,coupon 的价值无法直观判断,降低成交信心。",
        ),
        "Missing description": (
            "Attractions missing description",
            "缺失简介的景点",
            n_attrs,
            "卡片上没有一句话介绍,用户难以判断是否值得点进去,影响点击率。",
        ),
        "Missing phone": (
            "Attractions missing phone",
            "缺失联系电话的景点",
            n_attrs,
            "用户想电话确认是否需要预约或当天是否开放时无法直接联系景点。",
        ),
        "Geo geocode failure": (
            "Attractions missing geo coordinates",
            "缺失经纬度的景点",
            n_attrs,
            "无法按距离排序,持卡用户在远郊看到的优先级次序会失真。",
        ),
        "Hours vary by location / season": (
            "Attractions with non-fixed hours",
            "营业时间随场地/季节变动的景点",
            n_attrs,
            "页面无法给出固定开放时间,需要额外提示用户出门前自查。",
        ),
        "Duplicate slug pairs": (
            "Attractions appearing under duplicate slugs",
            "存在重复 slug 的景点",
            n_attrs,
            "同一家场馆出现在两个 ID 下,会被前端误显示成两条独立景点,稀释优惠。",
        ),
        "Missing hero image": (
            "Attractions missing hero image",
            "缺失封面图的景点",
            n_attrs,
            "卡片上只能显示分类占位 SVG,视觉冲击力弱,用户停留时间下降。",
        ),
        "Passes missing source_url": (
            "Passes missing source_url",
            "缺失来源 URL 的 pass 行",
            n_passes,
            "审核时无法一键回链到图书馆原页面,影响数据可追溯性。",
        ),
    }

    sections = defaultdict(list)
    for A in attrs:
        slug = A["slug"]
        name = A.get("museum_name") or ""
        if not has_numeric_price(A):
            sections["Missing price data"].append((slug, name))
        if not A.get("description"):
            sections["Missing description"].append((slug, name))
        if not A.get("phone"):
            sections["Missing phone"].append((slug, name))
        if not A.get("geo"):
            sections["Geo geocode failure"].append((slug, name))
        if (A.get("hours") or {}).get("status") and (A.get("hours") or {})["status"] != "ok":
            sections["Hours vary by location / season"].append((slug, name))
        if slug_counts[slug] > 1:
            sections["Duplicate slug pairs"].append((slug, name))
        if not (A.get("hero_image") or {}).get("local_path"):
            sections["Missing hero image"].append((slug, name))

    for p in passes:
        if not p.get("source_url"):
            sections["Passes missing source_url"].append((
                f'{p.get("library_id","")} → {p.get("attraction_slug","")}',
                "",
            ))

    out = []
    # Order: preserve insertion order from GAP_META so visual layout is stable
    for label, meta in GAP_META.items():
        items = sections.get(label) or []
        if not items:
            continue
        en_title, zh_title, denom, zh_impact = meta
        pct = round(100 * len(items) / max(denom, 1))
        rows = "".join(
            f'<tr><td class="mono">{esc(s)}</td><td>{esc(n)}</td></tr>'
            for s, n in items
        )
        pill = (
            f'<span class="num-pill">{len(items)} / {denom} · {pct}%</span>'
        )
        out.append(f"""
<section class="panel">
  <h2>{esc(en_title)} {pill}<span class="zh-sub">{esc(zh_title)}</span></h2>
  <p class="gap-impact">{esc(zh_impact)}</p>
  <table class="data-table">
    <thead><tr><th>slug / lib → slug</th><th>name</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>""")

    body = f"""
<h1 class="page-title">Data gaps<span class="zh-sub">数据缺口 · 哪些字段当前还没拿到</span></h1>
<p class="subtitle">每个分组列出未能自动采集到对应字段的景点或 pass。百分比基于该字段的全集(景点共 {n_attrs} 条 / pass 共 {n_passes} 条)。处理方式:人工补录 (<code>manual_overrides.json</code>) 或接受当前缺口。</p>
{"".join(out)}
"""
    return page_shell("Gaps", body, "gaps.html")


# =========================================================================
# PAGE 6 — duplicates.html
# =========================================================================

def page_duplicates(attr_data) -> str:
    attrs = {A["slug"]: A for A in attr_data["attractions"]}
    # filter pairs whose slugs already merged
    active_pairs = [(a, b) for a, b in KNOWN_DUPLICATES if a in attrs and b in attrs]

    def render_record(A: dict) -> str:
        if not A:
            return "<i>(not found in dataset)</i>"
        price = A.get("original_price") or {}
        # Flatten two-layer price into "k=v" tokens for the dup audit summary.
        _parts = []
        for _k, _tier in (price.get("age_pricing") or {}).items():
            if _k == "free_under_age":
                if _tier is not None:
                    _parts.append(f"free_under_age={_tier}")
            elif isinstance(_tier, dict) and _tier.get("price") is not None:
                _parts.append(f"{_k}={_tier['price']}")
        for _k, _tier in (price.get("identity_pricing") or {}).items():
            if isinstance(_tier, dict) and _tier.get("price") is not None:
                _parts.append(f"{_k}={_tier['price']}")
        if price.get("family") is not None:
            _parts.append(f"family={price['family']}")
        if price.get("notes"):
            _parts.append(f"notes={price['notes']}")
        price_str = "·".join(_parts) or "—"
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
    for a, b in active_pairs:
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
    resolved_note = (
        "<p><i>All known duplicate pairs have been collapsed to canonical entities. "
        "Mapping table: <code>src/malibbene/build/slug_canonical.py</code>.</i></p>"
        if not active_pairs else ""
    )
    body = f"""
<h1 class="page-title">Duplicates · {len(active_pairs)} pairs</h1>
<p>Pairs of attraction slugs that refer to the same real-world venue. Goal: pick one canonical slug, migrate libraries, retire the other.</p>
{resolved_note}
{"".join(pairs_html)}
"""
    return page_shell("Duplicates", body, "duplicates.html")


# =========================================================================
# PAGE 7 — lineage.html
# =========================================================================

def page_lineage(libs_data, attr_data, passes_data) -> str:
    n_libs = len(libs_data["libraries"])
    n_attrs = len(attr_data["attractions"])
    n_passes = len(passes_data["passes"])
    n_with_avail = sum(
        1 for p in passes_data["passes"]
        if (p.get("availability") or {}) and len(p.get("availability") or {}) > 0
    )

    stages = [
        {
            "n": "1",
            "en_title": "Collect from library websites",
            "zh_title": "从图书馆网站采集",
            "in_": "Library pass-program pages — public URLs we visit on a schedule",
            "do": "Scrape every page, save the raw HTML and the listing JSON",
            "out": "Raw page snapshots, one folder per library",
            "metric": f"{n_libs} library websites scraped",
            "zh": "我们按计划访问每家图书馆的 museum-pass 页面,把原始 HTML 和列表数据原样存档,作为后续抽取的唯一真相来源。",
            "tech": {
                "entry": "python scripts/scrape_static.py",
                "modules": [
                    ("src/malibbene/sources/assabet/index_page.py", "Assabet platform — 52 libraries"),
                    ("src/malibbene/sources/libcal/index_page.py", "LibCal platform — 5 libraries (BPL, Cambridge, Brookline, Braintree, Milton)"),
                    ("src/malibbene/sources/museumkey/index_page.py", "MuseumKey platform — 2 libraries (Cohasset, Hingham)"),
                    ("src/malibbene/common/http.py", "HTTP fetcher with retry, UA, and 24h disk cache"),
                ],
                "combine": "Each platform module reads its library list from <code>config/library_seeds.json</code>, walks every pass URL, and writes one file per library. Cache hits within 24h short-circuit the network call.",
                "output_path": "data/raw/{assabet,libcal,museumkey}/index/{lib_id}.json",
                "audit_hooks": "Re-run safely — output is idempotent. Inspect <code>meta.status_summary</code> in any output file to see <code>ok</code> / <code>empty</code> / <code>failed</code> counts; failed cells carry a reason string instead of being silently dropped.",
            },
        },
        {
            "n": "2",
            "en_title": "Catalog the attractions",
            "zh_title": "建立景点目录",
            "in_": "Raw library listings naming hundreds of museums, parks, theaters",
            "do": "Deduplicate name variants into one canonical attraction record per real-world venue, enrich with phone / address / hours / hero image / price from each attraction's official site",
            "out": "One row per unique attraction",
            "metric": f"{n_attrs} unique attractions catalogued",
            "zh": "把不同图书馆对同一家博物馆的不同写法合并成一条规范记录,再从景点官网补齐电话、地址、营业时间、票价、封面图,形成统一目录。",
            "tech": {
                "entry": "python scripts/build.py  (catalog + attractions phases)",
                "modules": [
                    ("src/malibbene/build/catalog.py", "Merge 3 platform raw indexes into one nested library_catalog.json"),
                    ("src/malibbene/build/slug_canonical.py", "Legacy-slug → canonical-slug mapping (e.g. <code>museum-of-fine-arts</code> → <code>mfa</code>)"),
                    ("src/malibbene/build/attractions.py", "Group catalog passes by canonical slug, attach price/image/geo/hours enrichments"),
                    ("src/malibbene/build/categories.py", "Normalize 21 raw category labels into a 9-bucket scheme"),
                    ("src/malibbene/common/normalize.py", "Lex-table that turns free-text benefit strings into short labels (FREE / 50% off / $5 off / discount / unknown)"),
                ],
                "combine": "<code>library_catalog.json</code> is keyed by lib_id; <code>attractions.py</code> inverts it — for each canonical slug it collects every library that lists that slug, then merges in side-files <code>data/raw/attractions/{prices,images,geo,hours}/&lt;slug&gt;.json</code> produced by the attraction-side scrapers and subagent extractors.",
                "output_path": "data/structured/library_catalog.json · data/structured/attractions.json",
                "audit_hooks": "Slug-collision check: see <code>n_unmapped_passes_per_platform</code> in catalog meta. If any platform reports unmapped passes, the slug map missed a legacy alias. Attractions <code>_meta.n_with_price</code> uses <code>_has_numeric_price()</code> — a non-empty original_price object alone does NOT count.",
            },
        },
        {
            "n": "3",
            "en_title": "Structure each pass into a clean record",
            "zh_title": "把每张 pass 整理成结构化记录",
            "in_": "Free-text benefit descriptions written by each library in their own style",
            "do": "Read the natural language and extract who the pass covers, what discount it gives, how it is delivered, and any usage restrictions",
            "out": "One row per (library × attraction) combination, with a uniform discount summary",
            "metric": f"{n_passes} attraction/library pass combinations",
            "zh": "每家图书馆描述福利的文字风格都不一样,我们把它们翻译成统一的字段:覆盖人群、折扣形式、取卡方式、使用限制,让前端可以横向对比。",
            "tech": {
                "entry": "python scripts/build.py  (passes phase)",
                "modules": [
                    ("src/malibbene/build/passes.py", "Flatten library_catalog into one row per (lib_id, canonical_slug); resolve pickup method and pass_type"),
                    ("src/malibbene/build/coupons.py", "Attach <code>capacity</code> + <code>audience_policies</code> blocks from per-pass coupon files"),
                    ("src/malibbene/build/museum_policy.py", "Drop audience_policies that merely restate the museum's own free-under-N policy (avoids double-counting)"),
                    ("data/raw/pass_coupons/{lib}_{slug}.json", "1008 per-pass coupon extractions produced by plan-9 Sonnet subagents reading the raw HTML — carries <code>source_phrases</code> for provenance"),
                ],
                "combine": "<code>passes.py</code> iterates every (lib_id × raw_slug) in the catalog, maps raw_slug → canonical via <code>slug_canonical.py</code>, looks up the coupon file with the raw key first (then canonical fallback), and emits one passes.json row. Vehicle capacity defaults <code>n=1</code> in <code>coupons.py</code> when the extractor returned null.",
                "output_path": "data/structured/passes.json",
                "audit_hooks": "<code>coupon.summary</code> is intentionally NOT stored — it's derived on display via <code>_derive_coupon_summary()</code> (build_audit_site.py line ~723). Re-extraction status of edge cases lives in <code>data/structured/_audit_unspecified_reclassification.json</code> (16 corrected, 35 by-audience, 9 family, 45 vague).",
            },
        },
        {
            "n": "4",
            "en_title": "Attach live booking availability",
            "zh_title": "接入实时预订日历",
            "in_": "Each library's reservation system (Assabet, LibCal, MuseumKey)",
            "do": "Refresh near-term slots daily so users see what is bookable right now",
            "out": "Per-pass availability calendar refreshed on a schedule",
            "metric": f"{n_with_avail} with live booking calendar",
            "zh": "每天自动刷新近期预订位,用户打开页面看到的是接近实时的可借状态,不是静态截图。",
            "tech": {
                "entry": "python scripts/scrape_dynamic.py",
                "modules": [
                    ("src/malibbene/sources/assabet/availability.py", "Walks 3 month-pages per pass (<code>base/ · next/ · next/next/</code>), parses <code>day-has-openings</code> / <code>day-no-openings</code> / <code>time-partially-available</code> CSS classes"),
                    ("src/malibbene/sources/libcal/availability.py", "Calls LibCal's institution endpoint with the current and next month's first-day-of-month parameter; collapses 3 LibCal states to <code>available</code> / <code>booked</code>"),
                    ("(MuseumKey not scraped)", "Cohasset + Hingham require library-card login; documented as catalog-only in BRD §A.3"),
                ],
                "combine": "Per-pass calendar dicts (<code>YYYY-MM-DD → available|limited|booked</code>) are written to <code>data/raw/{assabet,libcal}/availability/{lib_id}.json</code>, then merged into <code>passes.json</code>'s <code>availability</code> field at next build. ~2900 HTTP requests per full refresh; 24h cache TTL short-circuits within-day re-runs.",
                "output_path": "data/raw/{assabet,libcal}/availability/{lib_id}.json → passes.json:availability",
                "audit_hooks": "Front-end's <code>AttractionDetail.tsx</code> uses an explicit-only predicate (<code>availability[date] === 'available'</code>) — <code>undefined</code> does NOT default to available, so unscraped months stay blank instead of faking green. Month-pill row is capped at <code>dataHorizon</code> (max date across all this attraction's passes).",
            },
        },
        {
            "n": "5",
            "en_title": "Ship to the live site",
            "zh_title": "推送到线上站点",
            "in_": "Structured library / attraction / pass records + live calendar",
            "do": "Bundle the four data files and publish them to the consumer-facing web app",
            "out": "What the cardholder sees in the browser",
            "metric": "Live product",
            "zh": "把整理好的数据打包推送到面向用户的网站,持卡人打开页面就能查到自己手里的卡能用在哪、当天能不能预订。",
            "tech": {
                "entry": "cd web && pnpm run build  (Vite + React + TypeScript)",
                "modules": [
                    ("web/src/data/load.ts", "Bundles the 4 structured JSONs at build time (no runtime fetch)"),
                    ("web/src/pages/AttractionDetail.tsx", "Detail page — month pills, calendar, per-date coupon ranking"),
                    ("web/src/pages/AttractionsList.tsx", "List page — tag picker via <code>lib/tag-algorithm.ts</code>"),
                    ("web/src/lib/dates.ts · lib/restrictions.ts · lib/tag-algorithm.ts", "Date math, seasonal-window matching, coupon-ranking logic"),
                ],
                "combine": "Build pipeline writes <code>data/structured/{libraries,attractions,passes,branches}.json</code>; <code>load.ts</code> imports them, the components render. <code>data/static/images/</code> is gitignored; production images are mirrored into <code>web/public/images/</code> for Vite bundling.",
                "output_path": "web/dist/ → static hosting",
                "audit_hooks": "Test surface: <code>pnpm test</code> runs 102 vitest specs covering coupon ranking, restrictions, distance/geo, and the tag algorithm. Type safety: <code>pnpm tsc --noEmit</code> must be clean before release.",
            },
        },
    ]

    def _tech_block(tech: dict) -> str:
        mod_rows = "".join(
            f'<tr><td class="mono">{esc(path)}</td><td>{role}</td></tr>'
            for path, role in tech["modules"]
        )
        return f"""
    <details class="lineage-tech">
      <summary>Technical lineage<span class="zh-sub">技术血缘 · 给审计 / 工程团队</span></summary>
      <dl class="lineage-tech-dl">
        <dt>Entry</dt><dd class="mono">{esc(tech['entry'])}</dd>
        <dt>Modules</dt><dd><table class="lineage-tech-modules">{mod_rows}</table></dd>
        <dt>How combined</dt><dd>{tech['combine']}</dd>
        <dt>Output path</dt><dd class="mono">{esc(tech['output_path'])}</dd>
        <dt>Audit hooks</dt><dd>{tech['audit_hooks']}</dd>
      </dl>
    </details>"""

    stage_html_parts = []
    for s in stages:
        stage_html_parts.append(f"""
<section class="lineage-stage">
  <div class="lineage-num">{s['n']}</div>
  <div class="lineage-body">
    <h3 class="lineage-stage-title">{esc(s['en_title'])}<span class="zh-sub">{esc(s['zh_title'])}</span></h3>
    <p class="lineage-zh">{esc(s['zh'])}</p>
    <dl class="lineage-io">
      <dt>In</dt><dd>{esc(s['in_'])}</dd>
      <dt>We do</dt><dd>{esc(s['do'])}</dd>
      <dt>Out</dt><dd>{esc(s['out'])}</dd>
    </dl>
    <div class="lineage-metric">{esc(s['metric'])}</div>
    {_tech_block(s['tech'])}
  </div>
</section>""")

    volumes_html = f"""
<section class="lineage-volumes panel">
  <h2>By the numbers<span class="zh-sub">关键产出量</span></h2>
  <ol class="lineage-flow-line">
    <li><b>{n_libs}</b> library websites scraped<span class="zh-sub">家图书馆官网</span></li>
    <li><b>{n_attrs}</b> unique attractions catalogued<span class="zh-sub">条独立景点记录</span></li>
    <li><b>{n_passes}</b> attraction × library pass rows<span class="zh-sub">条 景点×图书馆 组合</span></li>
    <li><b>{n_with_avail}</b> with live booking calendar<span class="zh-sub">条带实时预订日历</span></li>
  </ol>
</section>
"""

    body = f"""
<h1 class="page-title">Data lineage<span class="zh-sub">数据血缘 · 从图书馆官网到用户屏幕</span></h1>
<p class="subtitle">How a single fact — for example "Acton library offers half-price admission for 4 people at the children's museum" — travels from a library website to the cardholder's screen. 一条优惠从图书馆官网走到用户眼前要经过 5 个阶段,下面逐步说明每个阶段做了什么、产出了多少。</p>

{volumes_html}

<div class="lineage-flow">
{''.join(stage_html_parts)}
</div>

<p class="lineage-foot">数据结构字段定义请见 <a href="#schema">schema</a>;质量检查项请见 <a href="#data-quality">data quality</a>。</p>
"""
    return page_shell("Lineage", body, "lineage.html")


# =========================================================================
# PAGE 8 — schema.html
# =========================================================================

def page_schema() -> str:
    # Each entity is a list of field tuples:
    #   (field_name, type_str, en_desc, zh_desc, why)
    LIBRARY_FIELDS = [
        ("id", "string", "Short library code used in cross-references.",
         "图书馆短代码,所有外键都用它,如 wakefield。",
         "Stable join key between libraries and passes."),
        ("name", "string", "Formal library name as it appears on signage.",
         "图书馆正式名称,如 Lucius Beebe Memorial Library。",
         "Shown to the cardholder on the library card chip."),
        ("town", "string", "Town the library serves.",
         "图书馆所在市镇。",
         "Used for distance grouping and town-level filters."),
        ("network", "string", "Library consortium membership (NOBLE / MLN / Minuteman ...).",
         "图书馆所属网络/联盟,如 NOBLE、MLN、Minuteman。",
         "Determines reciprocal borrowing rights for the cardholder."),
        ("platform", "enum", "Pass-booking backend: assabet / libcal / museumkey.",
         "通行证后台平台:Assabet(52 馆)/ LibCal(5 馆)/ MuseumKey(2 馆)。",
         "Selects the scraper and decides whether live availability is available."),
        ("card_page", "url", "Public page describing how to get a library card.",
         "本馆的办卡说明页 URL。",
         "Drives the 'how to get a card' deep-link on the frontend."),
        ("eligibility", "enum", "Who may obtain a card: open_ma_resident or residents_only.",
         "办卡资格:open_ma_resident 麻州居民均可 / residents_only 仅本镇居民。",
         "Tells the user whether they can sign up for this card at all."),
        ("supports_availability", "bool", "Whether the platform exposes next-30-day slot data.",
         "本馆所属平台是否能查未来 30 天的预订情况(MuseumKey 不支持)。",
         "Controls whether the live calendar UI shows for this library."),
        ("address", "object", "Street / city / state / zip / formatted.",
         "街道地址,拆成 5 个字段。",
         "Powers the map pin and walking-distance card."),
        ("geo", "object {lat,lon}", "Geocoded coordinates from OSM Nominatim.",
         "经纬度,由 OSM Nominatim 解析得到,缓存在 data/.cache/geocode.json。",
         "Enables distance-based sort against the user's home."),
    ]

    ATTRACTION_FIELDS = [
        ("slug", "string", "URL-safe stable ID for the attraction.",
         "景点的 URL 友好稳定 ID,如 boston-childrens-museum。",
         "Foreign key used by every pass row."),
        ("museum_name", "string", "Formal venue name.",
         "景点正式名称。",
         "Headline shown on the attraction card."),
        ("address / website / phone", "string", "Contact and locator info, mostly from the official site.",
         "联系地址、官网、电话,主要来自景点官网。",
         "Lets the user verify or call ahead before visiting."),
        ("description", "string", "One-paragraph plain-text intro to the venue.",
         "景点简介,纯文本一段。",
         "Drives whether a user clicks into detail; missing = cold card."),
        ("categories", "array of string", "Tag list (Children / Family / Science / Art / Nature / History ...).",
         "分类标签数组(儿童 / 家庭 / 科学 / 艺术 / 自然 / 历史 等)。",
         "Powers category filter and placeholder-image fallback."),
        ("sources", "array of library_id", "Libraries currently offering a pass to this attraction.",
         "数组,列出所有提供本景点 pass 的图书馆 id。",
         "Lets the UI surface 'X of your libraries offer this'."),
        ("original_price", "object", "Two-layer pricing model: age_pricing + identity_pricing + family.",
         "景点门市原价,两层:age_pricing 按年龄、identity_pricing 按身份、family 家庭票。",
         "The number the user mentally compares the coupon against."),
        ("original_price.age_pricing", "object", "adult / youth / child / senior tiers, each {price, min_age, max_age}, plus free_under_age (age threshold, not a price).",
         "按年龄定价:adult/youth/child/senior 各一档,以及 free_under_age(低于该岁数免费,是年龄阈值数字而非价格)。",
         "Anyone meeting the age band qualifies — no proof needed."),
        ("original_price.identity_pricing", "object", "student / educator / military tiers, each {price, requires}.",
         "按身份定价:student/educator/military,需出示证件。",
         "Some coupons stack with identity tiers; we keep the base price for comparison."),
        ("hero_image", "object", "Cover image scraped from the attraction's og:image, cached locally.",
         "景点封面图,来自官网 og:image,本地缓存(gitignored)。",
         "Drives card visual impact; falls back to category placeholder SVG."),
        ("hours", "object", "Mon–Sun opening hours plus a status field (ok / varies / seasonal / missing).",
         "周一至周日营业时间,加 status 标识(ok / varies / seasonal / missing)。",
         "Tells the UI whether to show hard hours or a 'check with venue' warning."),
        ("geo", "object {lat,lon}", "Geocoded attraction coordinates.",
         "景点经纬度,用于距离排序。",
         "Sorts attractions by distance from the user."),
    ]

    PASS_FIELDS = [
        ("library_id", "string", "Foreign key to libraries.id.",
         "外键指向 libraries.id。",
         "Identifies which library issues this pass."),
        ("attraction_slug", "string", "Foreign key to attractions.slug.",
         "外键指向 attractions.slug。",
         "Identifies which venue the pass admits the user to."),
        ("pass_type", "enum", "digital (Email) / physical-coupon (Pickup) / physical-circ (Borrow) / unknown.",
         "通行证形态:digital 邮件 / physical-coupon 门店取一次性纸券 / physical-circ 循环借阅卡 / unknown 未分类。",
         "Determines pickup workflow shown to the user."),
        ("source_url", "url", "Library page where this pass is described.",
         "本 pass 在图书馆官网上的来源页面 URL。",
         "Lets the auditor and the curious user verify against the original."),
        ("coupon", "object", "Unified discount model — what the user actually gets.",
         "统一优惠模型 — 这张 pass 实际能给用户什么。",
         "Single source of truth for the discount summary on every card."),
        ("coupon.capacity", "object {kind,n}", "Coverage cap: kind in people / vehicle / ticket / unspecified, plus headcount.",
         "整张 coupon 的容量上限,kind: people / vehicle / ticket / unspecified,n 为人数或车数。",
         "Tells the user how many people / vehicles fit under one coupon."),
        ("coupon.audience_policies", "array of object", "Per-audience policy rows: {audience, age_range, count, form, value}.",
         "数组,每项是一个人群规则:{audience 人群, age_range 年龄区间, count 人数, form 优惠形式, value 数值}。",
         "Drives the per-audience discount lines on the card."),
        ("coupon.audience_policies[].form", "enum", "free / percent-off / dollar-off / per-person-price / discount.",
         "优惠形式:free 免费 / percent-off 百分比 / dollar-off 固定减免 / per-person-price 人头价 / discount 笼统折扣。",
         "Controls the badge color and short label shown to the user."),
        ("coupon.summary", "string", "Mobile-ecommerce-style short string (FREE / 50% off / $5 off / $9 / person).",
         "电商风短字符串,如 FREE / 50% off / $5 off / $9/人。",
         "The single line the cardholder reads — they mentally compare it against original_price."),
        ("restrictions", "object", "Pass-side date rules: {blackout_dates, weekdays_only, seasonal}. Museum-side timed-entry lives on attraction.museum_reservation.",
         "Pass 自身的日期约束:节假日 blackout、仅工作日、季节性。博物馆要不要时段预约属于景点属性,见 attraction.museum_reservation。",
         "Surfaces ⚠ warning icons on dates the pass cannot be used."),
        ("availability", "object", "Next 30 days bookable-status map per slot (MuseumKey libraries: empty).",
         "未来 30 天的可预订状态字典,MuseumKey 平台为空。",
         "Powers the live calendar; tells the user if today is bookable."),
    ]

    COUPON_FORMS = [
        ("free", "Free admission for the audience tier.", "该人群完全免费入场。"),
        ("percent-off", "Percentage off the gate price, e.g. 50.", "门市价百分比折扣,如 50 表示 50% off。"),
        ("dollar-off", "Fixed dollar amount off, e.g. 5 = $5 off.", "固定金额减免,如 5 表示 $5 off。"),
        ("per-person-price", "Flat per-head price negotiated with the library, e.g. $5 / person.", "与图书馆协商的固定人头价,如每人 $5。"),
        ("discount", "Free-text discount language the extractor could not quantify.", "原文是笼统折扣描述,抽取器无法提取具体数值。"),
    ]

    def render_field_rows(fields):
        rows = []
        for name, typ, en, zh, why in fields:
            rows.append(f"""
<div class="schema-row">
  <div class="schema-fname"><code>{esc(name)}</code></div>
  <div class="schema-fbody">
    <div class="schema-ftype">{esc(typ)}</div>
    <div class="schema-fdesc">{esc(en)}<span class="zh-sub">{esc(zh)}</span></div>
    <div class="schema-fwhy"><b>Why</b> — {esc(why)}</div>
  </div>
</div>""")
        return "".join(rows)

    forms_rows = "".join(
        f'<tr><td class="mono">{esc(f)}</td><td>{esc(en)}<span class="zh-sub">{esc(zh)}</span></td></tr>'
        for f, en, zh in COUPON_FORMS
    )

    body = f"""
<h1 class="page-title">Schema<span class="zh-sub">数据结构 · 字段对照</span></h1>
<p class="subtitle schema-banner">本文档解释 backend → frontend 的字段定义,运营 / 审计可对照确认数据是否覆盖业务需求。字段名(field names)是 API 契约,保留英文不翻译;描述和"为什么需要这个字段"提供中英双语。</p>

<section class="panel schema-entity">
  <h2>Library<span class="zh-sub">图书馆 · {len(LIBRARY_FIELDS)} 个字段</span></h2>
  <div class="schema-fields">{render_field_rows(LIBRARY_FIELDS)}</div>
</section>

<section class="panel schema-entity">
  <h2>Attraction<span class="zh-sub">景点 · {len(ATTRACTION_FIELDS)} 个字段</span></h2>
  <div class="schema-fields">{render_field_rows(ATTRACTION_FIELDS)}</div>
</section>

<section class="panel schema-entity">
  <h2>Pass<span class="zh-sub">通行证 · 每行 = 一个 library × attraction 组合 · {len(PASS_FIELDS)} 个字段</span></h2>
  <div class="schema-fields">{render_field_rows(PASS_FIELDS)}</div>
</section>

<section class="panel schema-entity">
  <h2>Coupon form values<span class="zh-sub">优惠形式枚举</span></h2>
  <table class="data-table">
    <thead><tr><th>form</th><th>meaning</th></tr></thead>
    <tbody>{forms_rows}</tbody>
  </table>
</section>

<p class="foot-link"><a href="#" class="view-json-link" data-json-key="schema">查看完整 JSON 字段清单</a></p>
"""
    blob = json.dumps({
        "schema": {
            "passes_row_keys": ["library_id", "attraction_slug", "pass_type", "pass_type_raw",
                                "pickup_method", "pickup_branches", "coupon", "restrictions",
                                "source_url", "availability"],
            "coupon_keys": ["capacity", "audience_policies"],
            "audience_policy_keys": ["audience", "age_range", "count", "form", "value"],
            "coupon_forms": ["free", "percent-off", "dollar-off", "per-person-price", "discount"],
            "capacity_kinds": ["people", "vehicle", "ticket", "unspecified"],
            "pass_types": ["digital", "physical-coupon", "physical-circ", "unknown"],
        }
    }, ensure_ascii=False)
    return page_shell("Schema", body, "schema.html", data_blob=blob), blob


# =========================================================================
# PAGE 9 — data_quality.html
# =========================================================================

def page_data_quality(libs_data, attr_data, passes_data, raw_coupons_dir, status_banner: str = "") -> str:
    """Boss-readable data-quality page.

    Opens with a plain-language explanation of what we audit, then a
    severity-sorted red-flag summary, then per-flag detail, and finally
    the Data gaps section (which fields are still missing). No ID dumps
    without short context; copy is written for the boss / consultant.
    """
    _src = str(ROOT / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)
    from malibbene.build.slug_canonical import canonical, LEGACY_TO_CANONICAL  # noqa: F401

    passes = passes_data["passes"]
    attrs = attr_data["attractions"]
    attr_by_slug = {A["slug"]: A for A in attrs}

    def empty_state(n: int) -> str:
        return '<p class="honest-gap">all clear · 0</p>' if n == 0 else ""

    def table(headers: list[str], rows: list[list[str]], max_rows: int) -> str:
        n_total = len(rows)
        clipped = rows[:max_rows]
        head = "".join(f"<th>{esc(h)}</th>" for h in headers)
        body_rows = "".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in r) + "</tr>"
            for r in clipped
        )
        more = ""
        if n_total > max_rows:
            more = f'<tr><td colspan="{len(headers)}" class="honest-gap">+{n_total - max_rows} more</td></tr>'
        return (
            f'<table class="data-table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{body_rows}{more}</tbody></table>'
        )

    # ── Panel 1: empty coupon where catalog says a pass exists ──────────
    # Why: extraction may have failed silently, leaving coupon empty even
    # though the library catalog page lists this pass.
    p1_rows = []
    for p in passes:
        coupon = p.get("coupon") or {}
        cap = coupon.get("capacity") or {}
        if (coupon.get("audience_policies") or []) == [] and (cap.get("kind") or "unspecified") == "unspecified":
            p1_rows.append([
                esc(p.get("library_id", "")),
                esc(p.get("attraction_slug", "")),
                esc(p.get("pass_type", "")),
            ])
    p1_count = len(p1_rows)
    p1_html = (
        empty_state(p1_count) or
        table(["library_id", "attraction_slug", "pass_type"], p1_rows, 50)
    )

    # ── Panel 2: cross-library price variance (informational) ───────────
    # Each library negotiates its own coupon rate with the attraction, so the
    # same attraction can carry different "discounted price" values across
    # libraries — this is real product info, not a data bug. Listed here so a
    # cardholder can see which of their cards gives the best price.
    def collect_price_disagreements(audience_label: str):
        per_attr: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for p in passes:
            slug = p.get("attraction_slug", "")
            for ap in (p.get("coupon") or {}).get("audience_policies") or []:
                if ap.get("audience") == audience_label and ap.get("form") == "per-person-price":
                    v = ap.get("value")
                    if v is not None:
                        per_attr[slug].append((p.get("library_id", ""), float(v)))
        out = []
        for slug, recs in per_attr.items():
            distinct = sorted({v for _, v in recs})
            if len(distinct) > 1:
                rng = distinct[-1] - distinct[0]
                out.append((slug, distinct, len(recs), rng))
        out.sort(key=lambda x: x[3], reverse=True)
        return out

    p2_adult = collect_price_disagreements("Adult")
    p2_child = collect_price_disagreements("Child")
    p2_count = len(p2_adult) + len(p2_child)

    def disag_rows(records):
        rows = []
        for slug, distinct, n_libs, _rng in records:
            prices_str = ", ".join(f"${v:g}" for v in distinct)
            rows.append([
                f'<code class="mono">{esc(slug)}</code>',
                esc(prices_str),
                esc(str(n_libs)),
            ])
        return rows

    p2_inner = []
    if p2_adult:
        p2_inner.append("<h4>Adult price</h4>")
        p2_inner.append(table(
            ["attraction_slug", "distinct adult prices", "n libs reporting"],
            disag_rows(p2_adult), 30,
        ))
    if p2_child:
        p2_inner.append("<h4>Child price</h4>")
        p2_inner.append(table(
            ["attraction_slug", "distinct child prices", "n libs reporting"],
            disag_rows(p2_child), 30,
        ))
    p2_html = "".join(p2_inner) if p2_inner else empty_state(0)

    # ── Panel 3: form=discount with null value ──────────────────────────
    # Why: a generic "discount" with no numeric value is intentionally kept
    # (free-text discount language) but worth surfacing for awareness.
    p3_rows = []
    for p in passes:
        for ap in (p.get("coupon") or {}).get("audience_policies") or []:
            if ap.get("form") == "discount" and ap.get("value") is None:
                p3_rows.append([
                    esc(p.get("library_id", "")),
                    esc(p.get("attraction_slug", "")),
                ])
    p3_count = len(p3_rows)
    p3_html = (
        empty_state(p3_count) or
        table(["library_id", "attraction_slug"], p3_rows, 30)
    )

    # ── Panel 4: age_range contradicts the labelled audience ────────────
    # Why: an "Adult" tier with min_age=2 or a "Child" tier with min_age=18
    # is almost certainly an extraction bug.
    p4_rows = []
    for p in passes:
        for ap in (p.get("coupon") or {}).get("audience_policies") or []:
            aud = ap.get("audience")
            ar = ap.get("age_range") or {}
            mn = ar.get("min")
            mx = ar.get("max")
            flag = False
            if aud == "Adult" and mn is not None and mn < 13:
                flag = True
            elif aud == "Senior" and mn is not None and mn < 50:
                flag = True
            elif aud == "Child" and mn is not None and mn >= 13:
                flag = True
            elif aud == "Youth" and mx is not None and mx < 5:
                flag = True
            if flag:
                ar_str = f"[{mn if mn is not None else '·'}–{mx if mx is not None else '·'}]"
                fv = f"{ap.get('form','')}"
                if ap.get("value") is not None:
                    fv += f"={ap['value']}"
                p4_rows.append([
                    esc(p.get("library_id", "")),
                    esc(p.get("attraction_slug", "")),
                    esc(str(aud)),
                    esc(ar_str),
                    esc(fv),
                ])
    p4_count = len(p4_rows)
    p4_html = (
        empty_state(p4_count) or
        table(["library_id", "attraction_slug", "audience", "age_range", "form+value"], p4_rows, 50)
    )

    # ── Panel 5: orphan raw coupon files ────────────────────────────────
    # Why: if a raw extraction succeeded but the slug doesn't appear in
    # passes.json, the file is orphaned by a slug-naming drift.
    # Same logic as tests/test_coupon_orphans.py — list instead of fail.
    consumed: set[tuple[str, str]] = set()
    for p in passes:
        coupon = p.get("coupon") or {}
        cap = coupon.get("capacity") or {}
        if coupon.get("audience_policies") or cap.get("n") is not None:
            consumed.add((p.get("library_id", ""), p.get("attraction_slug", "")))

    raw_dir = Path(raw_coupons_dir)
    p5_rows = []
    if raw_dir.exists():
        for f in sorted(raw_dir.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("status") != "ok":
                continue
            stem_parts = f.stem.split("_", 1)
            lib_id = rec.get("library_id") or (stem_parts[0] if stem_parts else "")
            raw_slug = rec.get("attraction_slug") or (stem_parts[1] if len(stem_parts) > 1 else "")
            canon = canonical(raw_slug)
            if (lib_id, canon) not in consumed:
                suggested = canon if canon != raw_slug else ""
                p5_rows.append([
                    f'<code class="mono">{esc(f.name)}</code>',
                    f'<code class="mono">{esc(suggested)}</code>' if suggested else esc("—"),
                ])
    p5_count = len(p5_rows)
    p5_html = (
        empty_state(p5_count) or
        table(["filename", "suggested canonical"], p5_rows, 30)
    )

    # ── Panel 6: umbrella attractions ────────────────────────────────────
    # Why: hours.status='varies' AND no adult original_price means the
    # entity covers multiple sub-venues — the "1 attraction = 1 price"
    # model doesn't apply structurally.
    p6_rows = []
    for A in attrs:
        hours = A.get("hours") or {}
        op = A.get("original_price") or {}
        ap = (op.get("age_pricing") or {}).get("adult")
        if hours.get("status") == "varies" and (not op or ap is None):
            notes = hours.get("notes") or ""
            # Long-text cell: no truncation. Short notes inline; long notes
            # collapsed into a <details> so the table stays scan-able but the
            # auditor can drill in to see the full text.
            if not notes:
                notes_cell = ""
            elif len(notes) <= 100:
                notes_cell = f'<span class="notes">{esc(notes)}</span>'
            else:
                head = esc(notes[:90].rstrip()) + "…"
                full = esc(notes)
                notes_cell = (
                    f'<details class="notes-details"><summary>{head}</summary>'
                    f'<div class="notes-full">{full}</div></details>'
                )
            p6_rows.append([
                f'<code class="mono">{esc(A.get("slug",""))}</code>',
                esc(A.get("museum_name", "")),
                f'<span class="num">{esc(str(len(A.get("sources") or [])))}</span>',
                notes_cell,
            ])
    p6_count = len(p6_rows)
    p6_html = (
        empty_state(p6_count) or
        table(["slug", "museum_name", "n libs offering", "hours.notes"], p6_rows, 30)
    )

    # ── Panel 7: raw extraction failures ────────────────────────────────
    # Why: status != 'ok' means the subagent extractor gave up on this file.
    p7_rows = []
    p7_statuses: Counter = Counter()
    if raw_dir.exists():
        for f in sorted(raw_dir.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            st = rec.get("status")
            if st != "ok":
                p7_statuses[st or "(null)"] += 1
                p7_rows.append([
                    f'<code class="mono">{esc(f.name)}</code>',
                    esc(str(st)),
                ])
    p7_count = len(p7_rows)
    p7_html = (
        empty_state(p7_count) or
        table(["filename", "status"], p7_rows, 30)
    )

    # ── Panel metadata (severity, bilingual title, why-paragraph) ───────
    # NOTE: panel order in the rendered page is driven by severity (HIGH→MED→
    # LOW→INFO) then descending count, then by panel id. All-clear (count==0)
    # panels sink to the bottom of their severity bucket.
    # Per panel: short, boss-readable rationale that says what could go wrong
    # if this number isn't watched. No academic prose, no "we watch this to
    # make sure" hedging. Umbrella attractions + cross-library variance moved
    # to the Attractions page — those are attraction properties, not defects.
    PANELS = [
        {
            "id": "dq1", "sev": "HIGH", "count": p1_count, "html": p1_html,
            "en": "Passes whose coupon block came out empty",
            "zh": "空 coupon · 图书馆说有 pass,我们抽出来是空的",
            "why": "If this number is non-zero, that many passes show up in the product with no discount info at all — a row in the UI that says nothing. Should stay at 0.",
            "why_zh": "图书馆目录说有 pass,但我们抽取出来的折扣字段是空的。每多一条就有一条 pass 在产品里显示为空白,用户看不到任何优惠信息。必须为 0。",
        },
        {
            "id": "dq5", "sev": "HIGH", "count": p5_count, "html": p5_html,
            "en": "Orphan raw coupon files (slug renamed but not re-wired)",
            "zh": "孤立的原始 coupon 文件 · slug 改名后没接回",
            "why": "When an attraction's canonical slug changes, old extraction files can be left dangling. Each orphan = one real library discount that exists upstream but isn't visible on the live site. Should stay at 0.",
            "why_zh": "景点 slug 改名后,旧的抽取文件没被接回主表,等于这条真实存在的优惠在产品里消失了。必须为 0。",
        },
        {
            "id": "dq4", "sev": "MED", "count": p4_count, "html": p4_html,
            "en": "Audience label contradicts its age range",
            "zh": "受众标签和年龄区间矛盾 · 几乎都是抽取出错",
            "why": "An 'Adult' tier marked for under-13s, or a 'Child' tier for 18+, almost certainly means the extractor put the wrong row in the wrong bucket. UI ends up showing nonsensical age bands.",
            "why_zh": "标着 Adult 却写 13 岁以下,或者 Child 却写 18 岁以上,几乎肯定是抽取放错位置。前端会显示前后矛盾的年龄区间,直接打击用户信任。",
        },
        {
            "id": "dq7", "sev": "MED", "count": p7_count, "html": p7_html,
            "en": "Raw extractions where the AI extractor gave up",
            "zh": "AI 抽取失败的原始文件 · status != ok",
            "why": "These never make it into the live data. Each one = one discount the user never sees. Either re-run the extractor on these, or add a manual override.",
            "why_zh": "AI 抽取器在这些文件上放弃了,对应的优惠从来没进过产品。每多一条就少一条用户能看到的折扣。要么重跑,要么人工补录。",
        },
        {
            "id": "dq3", "sev": "LOW", "count": p3_count, "html": p3_html,
            "en": "Discount marked but no number — upstream is vague",
            "zh": "标着有折扣但抽不到数值 · 上游原文本来就模糊",
            "why": "The library wrote things like 'discounted admission' or 'family rate' with no number. The discount is real but we can't show '$X off' or '50% off' to the user. Not a bug — an upstream limitation.",
            "why_zh": "图书馆原文写的是 'discounted admission' / 'family rate' 这种模糊语,折扣是真的存在,但拿不到具体数字。属上游限制不是抽取 bug,前端只能显示\"有折扣\"。",
        },
    ]
    SEV_RANK = {"HIGH": 0, "MED": 1, "LOW": 2, "INFO": 3}

    def panel_sort_key(p):
        # 1. severity rank; 2. all-clear last within severity;
        # 3. descending count; 4. panel id for stability
        return (SEV_RANK[p["sev"]], 0 if p["count"] > 0 else 1, -p["count"], p["id"])

    PANELS_SORTED = sorted(PANELS, key=panel_sort_key)

    SEV_BADGE = {
        "HIGH": '<span class="sev-badge sev-high">HIGH</span>',
        "MED":  '<span class="sev-badge sev-med">MED</span>',
        "LOW":  '<span class="sev-badge sev-low">LOW</span>',
        "INFO": '<span class="sev-badge sev-info">INFO</span>',
    }

    # ── Summary table — ordered by severity, then descending count ──────
    sum_rows = []
    for p in PANELS_SORTED:
        style = ""
        if p["count"] > 0:
            if p["sev"] == "HIGH":
                style = ' style="background:var(--rd-pale);color:var(--rd);font-weight:600"'
            elif p["sev"] == "MED":
                style = ' style="background:var(--or-pale);color:var(--or)"'
        sum_rows.append(
            f'<tr{style}><td>{SEV_BADGE[p["sev"]]}</td>'
            f'<td><a href="#{p["id"]}">{esc(p["en"])}</a>'
            f'<span class="zh-sub">{esc(p["zh"])}</span></td>'
            f'<td class="num">{p["count"]}</td></tr>'
        )
    summary_html = (
        '<table class="data-table"><thead><tr>'
        '<th>severity</th><th>category</th><th>count</th>'
        f'</tr></thead><tbody>{"".join(sum_rows)}</tbody></table>'
    )

    severity_caption = """
<p class="sev-caption">
  <span class="sev-badge sev-high">HIGH</span> 立即修复,影响用户决策<br>
  <span class="sev-badge sev-med">MED</span> 关注,可能影响用户信任<br>
  <span class="sev-badge sev-low">LOW</span> 已知可接受,标识为参考<br>
  <span class="sev-badge sev-info">INFO</span> 数据信号,非缺陷
</p>"""

    panel_sections = []
    for p in PANELS_SORTED:
        sev_b = SEV_BADGE[p["sev"]]
        pill_class = "num-pill"
        if p["count"] == 0:
            pill_class += " num-pill-zero"
        panel_sections.append(f"""
<section class="panel dq-panel" id="{p['id']}">
  <h3>{sev_b} {esc(p['en'])} <span class="{pill_class}">{p['count']}</span>
      <span class="zh-sub">{esc(p['zh'])}</span></h3>
  <p class="dq-why">{esc(p['why'])}<br><span class="dq-why-zh">{esc(p['why_zh'])}</span></p>
  {p['html']}
</section>""")

    # ── Data gaps section (folded in from the retired Gaps page) ────────
    # Same logic as the old page_gaps body: list every field whose attraction
    # or pass coverage isn't 100%, with a one-line "what the user misses".
    gap_meta = {
        "Missing price data":            ("Attractions missing original_price", "缺失票价的景点", len(attrs),
                                          "用户看不到原价对比 · coupon 的价值难以判断 · 降低成交信心。"),
        "Missing description":           ("Attractions missing description", "缺失简介的景点", len(attrs),
                                          "卡片上没有一句话介绍 · 用户难判断是否值得点进去 · 影响点击率。"),
        "Missing phone":                 ("Attractions missing phone", "缺失联系电话的景点", len(attrs),
                                          "用户想电话确认是否需预约或当天是否开放时无法直接联系景点。"),
        "Geo geocode failure":           ("Attractions missing geo coordinates", "缺失经纬度的景点", len(attrs),
                                          "无法按距离排序 · 持卡用户在远郊看到的优先级次序失真。"),
        "Hours vary by location / season": ("Attractions with non-fixed hours", "营业时间随场地/季节变动的景点", len(attrs),
                                            "页面无法给出固定开放时间 · 需额外提示用户出门前自查。"),
        "Missing hero image":            ("Attractions missing hero image", "缺失封面图的景点", len(attrs),
                                          "卡片上只能显示分类占位 SVG · 视觉冲击弱 · 用户停留时间下降。"),
        "Passes missing source_url":     ("Passes missing source_url", "缺失来源 URL 的 pass 行", len(passes),
                                          "审核时无法一键回链到图书馆原页面 · 影响数据可追溯性。"),
    }
    gap_buckets = defaultdict(list)
    slug_count = Counter(A["slug"] for A in attrs)
    for A in attrs:
        slug = A["slug"]
        name = A.get("museum_name") or ""
        if not has_numeric_price(A):                                gap_buckets["Missing price data"].append((slug, name))
        if not A.get("description"):                                gap_buckets["Missing description"].append((slug, name))
        if not A.get("phone"):                                      gap_buckets["Missing phone"].append((slug, name))
        if not A.get("geo"):                                        gap_buckets["Geo geocode failure"].append((slug, name))
        h = A.get("hours") or {}
        if h.get("status") and h["status"] != "ok":                 gap_buckets["Hours vary by location / season"].append((slug, name))
        if not (A.get("hero_image") or {}).get("local_path"):       gap_buckets["Missing hero image"].append((slug, name))
    for p in passes:
        if not p.get("source_url"):
            gap_buckets["Passes missing source_url"].append((f'{p.get("library_id","")} → {p.get("attraction_slug","")}', ""))

    gap_sections = []
    for label, (en_title, zh_title, denom, zh_impact) in gap_meta.items():
        items = gap_buckets.get(label) or []
        if not items:
            continue
        pct = round(100 * len(items) / max(denom, 1))
        rows_html = "".join(f'<tr><td class="mono">{esc(s)}</td><td>{esc(n)}</td></tr>' for s, n in items)
        gap_sections.append(f"""
<section class="panel gap-section">
  <h3>{esc(en_title)} <span class="num-pill">{len(items)} / {denom} · {pct}%</span><span class="zh-sub">{esc(zh_title)}</span></h3>
  <p class="gap-impact">{esc(zh_impact)}</p>
  <table class="data-table">
    <thead><tr><th>slug / lib → slug</th><th>name</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</section>""")
    gaps_html = "".join(gap_sections) if gap_sections else '<p class="honest-gap">All tracked fields are 100% populated — no gaps to list.</p>'

    body = f"""
<h1 class="page-title">Data quality<span class="zh-sub">数据质量 · 我们到底审了什么</span></h1>

<section class="panel">
  <h3>What this page audits<span class="zh-sub">这页在审什么 · 一句话讲清</span></h3>
  <p style="font-size:13.5px;line-height:1.75;margin:6px 0 4px;">
    The 1026 passes in this dataset went through a 5-stage pipeline
    (<a href="#lineage">see Lineage</a>). At each stage, something can go wrong — a library
    page changes shape, the AI extractor misreads a sentence, a slug gets renamed without re-wiring.
    This page lists every category where that has actually happened, with a count and the affected rows.
  </p>
  <p style="font-size:13px;line-height:1.75;margin:6px 0 0;color:var(--ink-3);">
    简而言之,这页在审三件事:
    <b>① 每条记录是否完整</b>(coupon 空不空、source_url 在不在)、
    <b>② 字段值是否前后一致</b>(标着 Adult 却写 12 岁以下、价格出现负数)、
    <b>③ 我们抽出来的数字原文是否真的支持</b>(原文写 "discounted admission" 不能被抽成具体百分比)。
    数据 gaps(哪些字段还没抓到)放在本页最后一节。
  </p>
</section>

{status_banner}

<section class="panel">
  <h3>Red-flag summary<span class="zh-sub">红旗汇总 · 按严重程度排序</span></h3>
  {summary_html}
  {severity_caption}
</section>

{"".join(panel_sections)}

<h2 class="section-title" style="margin-top:32px">Data gaps<span class="zh-sub">数据缺口 · 哪些字段还没拿到</span></h2>
<p class="subtitle">下面每一节列出某个字段未能采集到的景点或 pass。百分比基于该字段的全集(景点 {len(attrs)} 条 / pass {len(passes)} 条)。处理方式只有两种:用 <code>config/manual_overrides.json</code> 人工补录,或者接受当前缺口。</p>
{gaps_html}
"""
    return body


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

main { max-width: 1024px; margin: 0 auto; padding: 28px 24px 80px; }

.page-title { font-family: 'Libre Baskerville', Georgia, serif; font-size: 28px; margin: 0 0 6px; color: var(--ink); font-weight: 700; }
.subtitle { color: var(--ink-3); margin: 0 0 28px; }

.panel { background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 18px 22px; margin-bottom: 20px; }
.panel h2, .panel h3 { margin: 0 0 12px; font-size: 15px; color: var(--ink); }

/* Distribution grid (used at top of libraries / attractions / policies) */
.dist-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 28px; }
.dist-panel { margin-bottom: 0; }
.dist-panel.dist-wide { grid-column: 1 / -1; }
.dist-panel h3 { font-family: 'Libre Baskerville', Georgia, serif; font-size: 14px; color: var(--ink); border-bottom: 1px dotted var(--rule); padding-bottom: 6px; }
.dist-panel .methodology { margin: 8px 0 0; background: var(--paper); }

.section-title { font-family: 'Libre Baskerville', Georgia, serif; font-size: 18px; color: var(--ink); margin: 36px 0 14px; padding-bottom: 6px; border-bottom: 2px solid var(--g); }

.cards-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.num-card { background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 22px; text-align: center; }
.num-card .num { font-size: 42px; font-weight: 700; color: var(--g); font-family: 'Libre Baskerville', Georgia, serif; }
.num-card .label { color: var(--ink-3); font-size: 13px; margin-top: 6px; }

.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
.coverage { list-style: none; padding: 0; margin: 0; }
.coverage li { display: grid; grid-template-columns: 1fr auto auto; gap: 14px; align-items: center; padding: 8px 0; border-bottom: 1px dotted var(--rule); }
.coverage .cov-label { line-height: 1.35; }
.coverage .cov-frac { color: var(--ink-3); font-size: 12px; font-variant-numeric: tabular-nums; }
.cov-pct { color: var(--g); font-weight: 600; font-variant-numeric: tabular-nums; min-width: 3em; text-align: right; }

.histogram { width: 100%; border-collapse: collapse; }
.histogram td, .histogram th { padding: 8px 10px; border-bottom: 1px dotted var(--rule); }
.histogram th { text-align: left; font-size: 11.5px; color: var(--ink-3); font-weight: 600; }
.histogram .bar-cell { width: 60%; }
.histogram .bar { color: var(--g); font-family: monospace; letter-spacing: -2px; }
.histogram .num, .histogram .pct { text-align: right; font-variant-numeric: tabular-nums; }
.histogram .num { color: var(--ink-2); font-weight: 600; }
.histogram .pct { color: var(--ink-3); }
.histogram tbody tr:nth-child(odd) { background: color-mix(in srgb, var(--paper) 35%, transparent); }

.platform-row { list-style: none; padding: 0; margin: 0; display: flex; gap: 32px; }
.platform-row .num { color: var(--g); font-weight: 700; font-size: 24px; margin: 0 8px; }

.anomaly-list { padding-left: 18px; margin: 0; }
.anomaly-list li { padding: 6px 0; line-height: 1.7; }
.anomaly-list li b { color: var(--rd); font-weight: 700; }

.methodology { color: var(--ink-3); font-size: 11.5px; line-height: 1.6; margin: 0 0 12px; padding: 8px 12px; background: var(--paper); border-left: 3px solid var(--rule-strong); border-radius: 0 4px 4px 0; }
.methodology b { color: var(--ink-2); }

.page-foot { color: var(--ink-3); margin-top: 32px; font-size: 12px; text-align: center; }

.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.search-box, .filter-select { padding: 8px 12px; border: 1px solid var(--rule-strong); border-radius: 6px; background: var(--white); font-size: 13px; }
.search-box { min-width: 280px; }

.data-table { width: 100%; border-collapse: collapse; background: var(--white); border: 1px solid var(--rule); border-radius: 8px; overflow: hidden; }
.data-table thead { background: var(--paper); }
.data-table th, .data-table td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--rule); font-size: 12.5px; vertical-align: top; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tbody tr:nth-child(odd) { background: color-mix(in srgb, var(--paper) 35%, transparent); }
.data-table .truncate { max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.data-table .own { color: var(--au); font-size: 16px; text-align: center; }
.data-table td.num, .data-table th.num,
.data-table td.pct, .data-table th.pct {
  text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap;
}
.data-table td .num { font-variant-numeric: tabular-nums; }
/* Long-text cell: wrap, give it room, never truncate. */
.data-table td .notes,
.data-table td.notes,
.data-table td .notes-details {
  display: block; max-width: 38rem; overflow-wrap: break-word; word-break: break-word;
}
.data-table td .notes-details > summary { cursor: pointer; color: var(--ink-2); }
.data-table td .notes-details > summary::marker { color: var(--ink-3); }
.data-table td .notes-details .notes-full {
  margin-top: 6px; padding: 6px 10px; background: var(--paper); border-left: 3px solid var(--rule-strong);
  border-radius: 0 4px 4px 0; max-width: 42rem; overflow-wrap: break-word;
}

/* Bilingual labels — Chinese sub-line below the English primary line. */
.zh-sub {
  display: block; font-size: 10.5px; color: var(--ink-3); font-weight: 400;
  line-height: 1.4; margin-top: 1px;
}

/* Status banner at the top of index.html / data_quality.html */
.status-banner {
  display: flex; align-items: center; gap: 14px;
  border-radius: 8px; padding: 14px 20px; margin: 0 0 24px;
  font-size: 13.5px; line-height: 1.5; border: 1px solid var(--rule);
}
.status-banner .banner-icon { font-size: 20px; flex: 0 0 auto; }
.status-banner .banner-verdict { flex: 1 1 auto; }
.status-banner .banner-meta { color: var(--ink-3); font-size: 12px; flex: 0 0 auto; }
.banner-green { background: var(--g-pale); border-color: var(--g-light); color: var(--g); }
.banner-green .banner-verdict b { color: var(--g); }
.banner-amber { background: var(--or-pale); border-color: var(--or); color: var(--au); }
.banner-amber .banner-verdict b { color: var(--or); }
.banner-red { background: var(--rd-pale); border-color: var(--rd); color: var(--rd); }
.banner-red .banner-verdict b { color: var(--rd); }

/* policies.html — collapse "+N more rows" toggle */
.more-rows { margin-top: 8px; padding: 8px 12px; background: var(--paper); border-radius: 6px; border: 1px dashed var(--rule-strong); }
.more-rows > summary { cursor: pointer; color: var(--ink-3); font-size: 12px; font-weight: 600; padding: 2px 0; }
.more-rows > summary:hover { color: var(--g); }
.more-rows[open] > summary { color: var(--g); margin-bottom: 8px; border-bottom: 1px dotted var(--rule); padding-bottom: 6px; }

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
/* Attractions — header + (image | meta) two-col top + full-width sections below */
/* Two-column card grid: each card sits roughly the same width as a panel
   in the 2-up dist-grid above, so the page reads as aligned vertically
   instead of "narrow tiles on top, wide cards below". */
.attr-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.attr-card {
  background: var(--white); border: 1px solid var(--rule); border-radius: 10px;
  padding: 18px; font-size: 13px;
}

.attr-card .top-row {
  display: flex; gap: 16px; margin: 10px 0 14px;
  padding-bottom: 14px; border-bottom: 1px solid var(--rule);
}
.attr-card .hero-side { flex: 0 0 140px; }
.attr-card .meta-side { flex: 1 1 auto; min-width: 0; }

.hero-big {
  width: 140px; max-width: 100%; height: auto; max-height: 140px;
  object-fit: cover; border-radius: 8px; cursor: zoom-in; display: block;
  border: 1px solid var(--rule);
}
.hero-big.noimg {
  width: 140px; max-width: 100%; height: 110px;
  background: var(--paper); border: 1px dashed var(--rule-strong); border-radius: 8px;
  display: flex; align-items: center; justify-content: center; color: var(--ink-3);
  font-size: 11px; text-align: center; padding: 0 6px;
}

.attr-card .attr-name { font-size: 18px !important; }

.v.closed { color: var(--rd); font-weight: 600; }
.v.dash { color: var(--rule-strong); }

.attr-card .attr-header { border-bottom: 1px solid var(--rule); padding-bottom: 12px; margin-bottom: 14px; }
.attr-card .attr-name {
  font-family: 'Libre Baskerville', Georgia, serif; font-size: 22px;
  margin: 0 0 4px; color: var(--ink); font-weight: 700; line-height: 1.3;
}
.attr-card .attr-sub { font-size: 12px; color: var(--ink-3); }
.attr-card .attr-sub .slug { background: var(--paper); padding: 1px 6px; border-radius: 3px; color: var(--ink-2); }
.attr-card .attr-sub .meta-divider { margin: 0 8px; }
.attr-card .attr-sub .cats { color: var(--g-2); }
.warn-row { color: var(--rd); margin-top: 6px; font-size: 12px; }
.warn-row a { color: var(--rd); text-decoration: underline; }

.attr-card section { margin-bottom: 18px; }
.attr-card section:last-child { margin-bottom: 0; }
.attr-card .block-title {
  font-family: 'Libre Baskerville', Georgia, serif; font-size: 13.5px;
  color: var(--ink); margin: 0 0 8px; padding-bottom: 4px;
  border-bottom: 1px dotted var(--rule); font-weight: 700;
}
.attr-card .block-meta { color: var(--ink-3); font-size: 11.5px; font-family: 'DM Sans', sans-serif; font-weight: 400; margin-left: 8px; }
.attr-card .block-subtitle {
  font-family: 'DM Sans', sans-serif; font-size: 12px; font-weight: 600;
  color: var(--ink-2); margin: 12px 0 6px; text-transform: uppercase; letter-spacing: 0.04em;
}

/* Definition list rows: label left, value right */
.kv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 24px; }
.kv {
  display: flex; justify-content: space-between; gap: 12px;
  padding: 3px 0; border-bottom: 1px dotted var(--rule);
}
.kv-wide { grid-column: 1 / -1; }
.kv .k { color: var(--ink-3); font-size: 12px; }
.kv .v { color: var(--ink-2); font-size: 12.5px; text-align: right; }
.kv .v.verified { color: var(--g); font-weight: 600; }
.kv .v.honest-gap { color: var(--ink-3); }
.kv-gap .k { color: var(--ink-3); opacity: 0.7; }
.price-note { font-size: 11.5px; color: var(--ink-3); margin: 6px 0 0; line-height: 1.4; }
.price-note b { color: var(--ink-2); font-weight: 600; }

.src-line { margin-top: 8px; font-size: 11.5px; color: var(--ink-3); }
.src-line a { color: var(--g); }

.attr-card .desc-text { margin: 0; line-height: 1.7; }

.sources-list { font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: var(--ink-3); margin: 0; line-height: 1.9; }
.sources-list code { background: var(--paper); padding: 1px 5px; border-radius: 3px; }

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

/* Lineage — boss-readable 5-stage flow */
.lineage-svg { width: 100%; max-width: 900px; height: auto; display: block; margin: 20px auto; background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 16px; }
.lineage-foot { color: var(--ink-3); font-size: 12px; margin-top: 24px; }
.lineage-volumes { padding: 18px 22px; }
.lineage-volumes h2 { margin: 0 0 12px; font-family: 'Libre Baskerville', Georgia, serif; font-size: 16px; }
.lineage-flow-line { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.lineage-flow-line li { background: var(--paper); border-left: 3px solid var(--g); padding: 10px 12px; border-radius: 0 6px 6px 0; font-size: 12.5px; color: var(--ink-2); }
.lineage-flow-line li b { display: block; font-size: 22px; color: var(--g); font-family: 'Libre Baskerville', Georgia, serif; line-height: 1.1; margin-bottom: 2px; }
.lineage-flow { display: flex; flex-direction: column; gap: 16px; margin-top: 24px; }
.lineage-stage { background: var(--white); border: 1px solid var(--rule); border-radius: 10px; padding: 18px 22px; display: grid; grid-template-columns: 48px 1fr; gap: 18px; }
.lineage-num { font-family: 'Libre Baskerville', Georgia, serif; font-size: 30px; font-weight: 700; color: var(--g); line-height: 1; text-align: center; }
.lineage-stage-title { margin: 0 0 6px; font-family: 'Libre Baskerville', Georgia, serif; font-size: 17px; color: var(--ink); }
.lineage-zh { color: var(--ink-3); font-size: 12.5px; line-height: 1.7; margin: 0 0 12px; }
.lineage-io { display: grid; grid-template-columns: 80px 1fr; gap: 6px 14px; margin: 0 0 10px; font-size: 12.5px; }
.lineage-io dt { color: var(--ink-3); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; font-size: 11px; padding-top: 2px; }
.lineage-io dd { margin: 0; color: var(--ink-2); }
.lineage-metric { display: inline-block; background: var(--g-pale); color: var(--g); padding: 4px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 600; }
.lineage-tech { margin-top: 12px; border-top: 1px dashed var(--rule); padding-top: 8px; }
.lineage-tech > summary { cursor: pointer; color: var(--ink-3); font-size: 11.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; list-style: none; padding: 4px 0; }
.lineage-tech > summary::-webkit-details-marker { display: none; }
.lineage-tech > summary::before { content: '▸  '; color: var(--ink-3); font-size: 10px; }
.lineage-tech[open] > summary::before { content: '▾  '; }
.lineage-tech-dl { display: grid; grid-template-columns: 100px 1fr; gap: 6px 14px; margin: 8px 0 0; font-size: 11.5px; color: var(--ink-3); }
.lineage-tech-dl dt { font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; font-size: 10.5px; padding-top: 2px; color: var(--ink-3); }
.lineage-tech-dl dd { margin: 0; color: var(--ink-2); line-height: 1.55; }
.lineage-tech-dl dd.mono { font-family: 'SF Mono', Menlo, Consolas, monospace; color: var(--ink-2); background: var(--g-pale); padding: 2px 6px; border-radius: 4px; display: inline-block; }
.lineage-tech-modules { font-size: 11.5px; border-collapse: collapse; width: 100%; }
.lineage-tech-modules td { padding: 3px 0; border: 0; vertical-align: top; }
.lineage-tech-modules td.mono { font-family: 'SF Mono', Menlo, Consolas, monospace; color: var(--ink); padding-right: 14px; white-space: nowrap; }
.lineage-tech-modules td code { background: transparent; padding: 0; }

/* Passes page — what / distribution / meaning sections */
.passes-section { padding: 18px 22px; }
.passes-section h3 { font-family: 'Libre Baskerville', Georgia, serif; font-size: 16px; color: var(--ink); margin: 0 0 12px; }
.passes-section .section-what { margin: 0 0 12px; font-size: 13px; color: var(--ink-2); line-height: 1.6; }
.passes-section .section-what b { color: var(--ink); }
.passes-section .section-meaning { margin-top: 12px; padding: 12px 14px; background: var(--g-pale); border-left: 3px solid var(--g); font-size: 12.5px; color: var(--ink-2); line-height: 1.65; border-radius: 4px; }
.passes-section .section-meaning b { color: var(--ink); }
.passes-section .section-meaning ul { margin: 6px 0 0; padding-left: 18px; }
.passes-section .section-meaning li { margin-bottom: 6px; }
.passes-section .section-meaning li:last-child { margin-bottom: 0; }
.passes-dist td { vertical-align: middle; padding: 5px 8px; }
.passes-dist td:first-child { width: 32%; line-height: 1.4; }
.passes-dist .meaning-note { font-size: 11px; color: var(--ink-3); margin-top: 1px; }
.passes-dist .bar { color: var(--g); letter-spacing: -1px; }
.passes-dist .num { color: var(--ink); font-weight: 600; }
.passes-dist .pct { color: var(--ink-3); font-size: 11.5px; }
@media (max-width: 720px) {
  .lineage-flow-line { grid-template-columns: 1fr 1fr; }
}

/* Gaps — business-impact subtitle */
.gap-impact { color: var(--ink-3); font-size: 12px; margin: -4px 0 10px; padding: 6px 10px; background: var(--paper); border-left: 3px solid var(--rule-strong); border-radius: 0 4px 4px 0; line-height: 1.6; }

/* Schema — entity sections with field rows */
.schema-banner { background: var(--g-pale); border-left: 3px solid var(--g); padding: 10px 14px; border-radius: 0 4px 4px 0; color: var(--ink-2); font-size: 12.5px; }
.schema-entity h2 { font-family: 'Libre Baskerville', Georgia, serif; font-size: 18px; padding-bottom: 6px; border-bottom: 2px solid var(--g); }
.schema-fields { display: flex; flex-direction: column; gap: 0; }
.schema-row { display: grid; grid-template-columns: 220px 1fr; gap: 16px; padding: 12px 0; border-bottom: 1px dotted var(--rule); }
.schema-row:last-child { border-bottom: none; }
.schema-fname code { font-family: 'JetBrains Mono', 'Courier New', monospace; background: var(--paper); padding: 2px 8px; border-radius: 4px; color: var(--ink); font-size: 12px; word-break: break-all; }
.schema-fbody { font-size: 12.5px; line-height: 1.7; }
.schema-ftype { display: inline-block; background: var(--au-pale); color: var(--au); padding: 1px 8px; border-radius: 10px; font-family: 'JetBrains Mono', monospace; font-size: 11px; margin-bottom: 6px; }
.schema-fdesc { color: var(--ink-2); margin-bottom: 4px; }
.schema-fwhy { color: var(--ink-3); font-size: 12px; }
.schema-fwhy b { color: var(--g); font-weight: 600; }

/* Data quality — severity badges + why paragraphs */
.sev-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10.5px; font-weight: 700; letter-spacing: 0.05em; margin-right: 6px; font-family: 'DM Sans', sans-serif; vertical-align: middle; }
.sev-high { background: var(--rd); color: var(--white); }
.sev-med  { background: var(--or); color: var(--white); }
.sev-low  { background: var(--paper); color: var(--ink-3); border: 1px solid var(--rule-strong); }
.sev-info { background: var(--g-pale); color: var(--g); }
.sev-caption { color: var(--ink-3); font-size: 12px; line-height: 2; margin: 12px 0 0; padding: 10px 14px; background: var(--paper); border-radius: 6px; }
.dq-panel h3 { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.dq-why { color: var(--ink-3); font-size: 12px; line-height: 1.7; margin: -4px 0 12px; padding: 8px 12px; background: var(--paper); border-left: 3px solid var(--rule-strong); border-radius: 0 4px 4px 0; }
.dq-why-zh { display: block; color: var(--ink-3); margin-top: 4px; }
.num-pill-zero { background: var(--g-pale); color: var(--g); }

/* Modal */
.modal-root { position: fixed; inset: 0; z-index: 100; }
.modal-root.hidden { display: none; }
.modal-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.45); }
.modal-box { position: relative; background: var(--white); max-width: 720px; max-height: 80vh; overflow: auto; margin: 5vh auto; padding: 24px; border-radius: 8px; }
.modal-close { position: absolute; top: 8px; right: 12px; background: none; border: none; font-size: 22px; cursor: pointer; color: var(--ink-3); }
.modal-body img { max-width: 900px; max-height: 70vh; height: auto; display: block; margin: 0 auto; }
.modal-box { max-width: 950px; }
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
  document.querySelectorAll('.hero-big, .hero-thumb').forEach(function (el) {
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
# Single-page audit — audit.html (anchor nav, all 5 sections in one file)
# =========================================================================

def _extract_main_body(full_html: str) -> str:
    """Extract content between <main> and </main> from a page_shell result."""
    start = full_html.find("<main>")
    end = full_html.find("</main>")
    if start == -1 or end == -1:
        return full_html  # fallback: return as-is
    return full_html[start + len("<main>"):end]


def page_audit_single(libs_data, attr_data, passes_data, raw_coupons_dir, status_banner: str = "") -> tuple[str, list]:
    """Build a single audit.html containing all 5 audit sections with anchor nav.

    Returns (html, missing_image) so caller can report missing hero images.
    """
    # Section 1 — Attractions
    attr_full, missing_image = page_attractions(attr_data, passes_data=passes_data, libs_data=libs_data)
    attractions_body = _extract_main_body(attr_full)

    # Section 2 — Passes
    passes_full = page_passes(passes_data, libs_data, attr_data)
    passes_body = _extract_main_body(passes_full)

    # Section 3 — Lineage
    lineage_full = page_lineage(libs_data, attr_data, passes_data)
    lineage_body = _extract_main_body(lineage_full)

    # Section 4 — Schema (also returns blob for the JSON-view modal)
    schema_full, schema_blob = page_schema()
    schema_body = _extract_main_body(schema_full)

    # Section 5 — Data Quality (already returns body, not full page)
    dq_body = page_data_quality(libs_data, attr_data, passes_data, raw_coupons_dir, status_banner=status_banner)

    body = f"""<section id="attractions">
{attractions_body}
</section>

<section id="passes">
{passes_body}
</section>

<section id="lineage">
{lineage_body}
</section>

<section id="schema">
{schema_body}
</section>

<section id="data-quality">
{dq_body}
</section>
"""
    return audit_shell(body, data_blob=schema_blob), missing_image


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
    branches_path = STRUCT / "branches.json"
    branches_data = load_json(branches_path) if branches_path.exists() else None

    pages = []

    def write(name: str, content: str):
        p = OUT / name
        p.write_text(content, encoding="utf-8")
        size_kb = p.stat().st_size / 1024
        print(f"  wrote {name:18s}  {size_kb:8.1f} KB")
        pages.append((name, p.stat().st_size))

    # Compute red-flag counts once; data_quality.html renders the status banner.
    raw_coupons_dir = ROOT / "data" / "raw" / "pass_coupons"
    dq_counts = compute_dq_counts(libs_data, attr_data, passes_data, raw_coupons_dir)
    banner = status_banner_html(dq_counts)

    # Delete obsolete pages from previous nav layouts. Idempotent — missing is fine.
    for stale in (
        "libraries.html", "duplicates.html", "gaps.html",
        "policies.html", "audit_review.html",
        "attractions.html",  # content now lives at index.html (landing tab)
        # C3 consolidation: 5 standalone pages replaced by audit.html
        "index.html", "passes.html", "lineage.html", "schema.html", "data_quality.html",
    ):
        try:
            (OUT / stale).unlink()
            print(f"  removed {stale}")
        except FileNotFoundError:
            pass

    print("[1/1] audit.html (single-page, 5 anchor sections)")
    n_patterns = 0  # legacy page_policies retired; no pattern matrix to count
    audit_html, missing_image = page_audit_single(
        libs_data, attr_data, passes_data, raw_coupons_dir, status_banner=banner
    )
    write("audit.html", audit_html)

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
