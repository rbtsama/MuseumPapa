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

def signature(pass_obj: dict) -> tuple:
    """Derive a grouping signature from the coupon model (plan-9)."""
    coupon = pass_obj.get("coupon") or {}
    cap = coupon.get("capacity") or {}
    cap_kind = cap.get("kind") or "unspecified"
    cap_n = cap.get("n")  # int or None
    aps = coupon.get("audience_policies") or []
    forms = tuple(sorted({ap.get("form", "discount") for ap in aps}))
    n_tiers = len(aps)
    has_restrictions = bool(pass_obj.get("restrictions"))
    return (cap_kind, cap_n, forms, n_tiers, has_restrictions)


COUPON_FORM_LABEL_EN = {
    "free":             "FREE",
    "percent-off":      "Percent off",
    "dollar-off":       "Dollar off",
    "per-person-price": "Per-person price",
    "discount":         "Generic discount",
}
COUPON_FORM_LABEL_ZH = {
    "free":             "免费",
    "percent-off":      "百分比折扣",
    "dollar-off":       "立减金额",
    "per-person-price": "人头定价",
    "discount":         "笼统折扣",
}
CAP_KIND_LABEL = {
    "people":      "People · 人数",
    "vehicle":     "Vehicle · 车辆",
    "ticket":      "Ticket · 单张票",
    "unspecified": "Unspecified · 未明示",
}


def signature_name(sig: tuple) -> tuple[str, str]:
    cap_kind, cap_n, forms, n_tiers, has_restrictions = sig
    forms_en = " + ".join(COUPON_FORM_LABEL_EN.get(f, f) for f in forms) if forms else "no form"
    forms_zh = " + ".join(COUPON_FORM_LABEL_ZH.get(f, f) for f in forms) if forms else "无 form"
    cap_str = CAP_KIND_LABEL.get(cap_kind, cap_kind)
    if cap_kind == "people" and cap_n is not None:
        cap_str = f"≤{cap_n} people"
    tiers_str = f"{n_tiers}-tier" if n_tiers != 1 else "single-tier"
    restr_str = "w/ restrictions" if has_restrictions else ""
    en_parts = [forms_en, cap_str, tiers_str]
    zh_parts = [forms_zh, cap_str, tiers_str]
    if restr_str:
        en_parts.append(restr_str)
        zh_parts.append("含限制")
    return " · ".join(en_parts), " · ".join(zh_parts)


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
        f'<a href="data_quality.html">see Data Quality</a></span>'
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
    "physical-circ": "Pickup & Return",
    "unknown": "Pass",
}


def pass_type_badge(pt: str) -> str:
    label = _PT_DISPLAY_LABEL.get(pt, pt)
    return f'<span class="badge badge-pt-{esc(pt)}">{esc(label)}</span>'


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
    ("data_quality.html", "Data Quality"),
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
        "Ticket price (any tier) · 票价(任一层级)": sum(1 for A in attrs if A.get("original_price")),
        "Opening hours · 营业时间": sum(1 for A in attrs if A.get("hours")),
        "Description · 简介": sum(1 for A in attrs if A.get("description")),
        "Phone · 电话": sum(1 for A in attrs if A.get("phone")),
        "Geo coordinates · 经纬度": sum(1 for A in attrs if A.get("geo")),
    }
    pass_cov = {
        "Coupon extracted · 优惠已结构化(plan-9)": sum(1 for p in passes if p.get("coupon")),
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
            dup_warn = '<div class="warn-row">⚠ 此 slug 与同一景点的另一条记录重复(<a href="duplicates.html">见 Duplicates</a>)</div>'

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
    # Hours buckets — 3 user-facing categories + 2 footnote categories.
    # Rule: a status="ok" record with ALL 7 days closed is treated as seasonal
    # (data bug fix — e.g. cohasset whose notes say "summer only" but status was 'ok').
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
            hours_status_counter["bucket_varies"] += 1
        elif st == "seasonal" or (st == "ok" and n_closed == 7):
            hours_status_counter["bucket_seasonal"] += 1
        elif st == "ok" and n_closed == 0:
            hours_status_counter["bucket_open_daily"] += 1
        elif st == "ok" and n_closed > 0:
            hours_status_counter["bucket_partial"] += 1
        else:
            hours_status_counter["bucket_nodata"] += 1
    hours_label_map = {
        "bucket_open_daily": "Open daily year-round · 全年每日开放",
        "bucket_partial":    "Open with weekly closed days · 每周有固定休息日",
        "bucket_seasonal":   "Open only in season · 仅特定月份开放",
        "bucket_varies":     "Multi-site, hours vary · 多址各自不同时刻表",
        "bucket_nodata":     "Unknown · 未知",
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
        if A.get("original_price"): cov_counter["price (any tier)"] += 1
        if A.get("hours"): cov_counter["hours"] += 1
        if A.get("description"): cov_counter["description"] += 1
        if A.get("phone"): cov_counter["phone"] += 1
        if A.get("geo"): cov_counter["geo"] += 1
        if A.get("address"): cov_counter["address"] += 1
    # Top 10 attractions by # libraries offering
    top_attrs = sorted(attrs, key=lambda a: -len(a.get("sources") or []))[:10]
    top_attrs_html = "".join(
        f'<tr><td class="mono">{esc(a["slug"])}</td>'
        f'<td>{esc((a.get("museum_name") or "")[:34])}</td>'
        f'<td class="bar-cell"><span class="bar">{"█" * round(40 * len(a.get("sources") or []) / max(1, len(top_attrs[0].get("sources") or [])))}</span></td>'
        f'<td class="num">{len(a.get("sources") or [])}</td></tr>'
        for a in top_attrs
    )

    body = f"""
<h1 class="page-title">Attractions · {n_attrs}</h1>

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
    return page_shell("Attractions", body, "attractions.html"), missing_image


# =========================================================================
# PAGE 4 — policies.html
# =========================================================================

def page_policies(passes_data, libs_data, attr_data) -> str:
    passes = passes_data["passes"]
    # Compute signatures from coupon model, take top 15 by frequency, rest = P16 Other
    sigs = Counter(signature(p) for p in passes if p.get("coupon"))
    top = sigs.most_common(15)
    sig_to_pid = {sig: f"P{i+1}" for i, (sig, _) in enumerate(top)}

    # Group passes by pid
    by_pid: dict[str, list] = defaultdict(list)
    for p in passes:
        if not p.get("coupon"):
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
    # Pattern frequency table
    pattern_count_table = "".join(
        f'<tr><td class="mono"><a href="#{pid}">{pid}</a></td>'
        f'<td>{esc(en)}</td>'
        f'<td class="bar-cell"><span class="bar">{"█" * round(40 * n / max(1, pattern_meta[0][3]))}</span></td>'
        f'<td class="num">{n}</td><td class="pct">{round(100 * n / n_passes)}%</td></tr>'
        for pid, en, zh, n in pattern_meta
    )
    # Precompute histogram HTML (dicts can't be inlined in f-strings)
    _pt_label = {
        "digital": "Email · 邮件直接收",
        "physical-coupon": "Pickup · 馆里取一次",
        "physical-circ": "Pickup & Return · 馆里取 + 还回去",
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
    <h3>Coupon patterns</h3>
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
        # Reason is identical for every row in a section — surface it once in the
        # section header instead of repeating it in every row.
        section_reason = items[0][2] if items else ""
        rows = "".join(
            f'<tr><td class="mono">{esc(s)}</td><td>{esc(n)}</td><td>—</td></tr>'
            for s, n, _why in items
        )
        reason_html = f' <span class="section-reason" style="font-weight:400;color:var(--ink-3);font-size:13px">· {esc(section_reason)}</span>' if section_reason else ""
        out.append(f'<section class="panel"><h2>{esc(label)} <span class="num-pill">{len(items)}</span>{reason_html}</h2><table class="data-table"><thead><tr><th>slug</th><th>name</th><th>note</th></tr></thead><tbody>{rows}</tbody></table></section>')

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

  <g><rect class="node node-raw" x="240" y="180" width="170" height="60" rx="6"/><text class="label" x="325" y="208" text-anchor="middle">raw/pass_coupons/</text><text class="sub" x="325" y="226" text-anchor="middle">1008 cells</text></g>
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
    <li><b>original_price</b>:景点门市原价,两层模型。
      <ul>
        <li><b>age_pricing</b>:按年龄定价,任何符合年龄的访客都适用。包含 adult / youth / child / senior 四种(每种是 <code>{price, min_age, max_age}</code> 或 null),以及 <code>free_under_age</code>(低于该岁数免费,是年龄阈值数字而非票价)。</li>
        <li><b>identity_pricing</b>:按身份定价,需出示证件。包含 student / educator / military 三种(每种是 <code>{price, requires}</code> 或 null)。</li>
        <li><b>family</b>:家庭通票价(顶层数字)。<b>notes / source_url</b>:备注与数据源。</li>
      </ul>
    </li>
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
        <li><b>digital</b>(显示为 <b>Email</b>)</li>
        <li><b>physical-coupon</b>:门店取纸质券,用完不归还(260 个)。</li>
        <li><b>physical-circ</b>:循环借阅卡,用完需归还图书馆(172 个)。</li>
        <li><b>unknown</b>:未能识别(23 个)。</li>
      </ul>
    </li>
    <li><b>coupon</b>:统一优惠模型:
      <ul>
        <li><b>capacity</b>:<code>{"kind": "people"|"vehicle"|"ticket"|"unspecified", "n": int|null}</code> — 整张 coupon 覆盖的容量上限</li>
        <li><b>audience_policies</b>:数组,每项 = <code>{"audience", "age_range", "count", "form", "value"}</code>。
          <ul>
            <li><b>audience</b>: Everyone / Adult / Child / Youth / Senior / Vehicle / Single ticket</li>
            <li><b>form</b>: <code>free</code> / <code>percent-off</code> / <code>dollar-off</code> / <code>per-person-price</code> / <code>discount</code></li>
            <li><b>value</b>: 数值(如 50 = 50% off, 5 = $5 off),或 null(无数值/笼统)</li>
          </ul>
        </li>
      </ul>
    </li>
    <li><b>restrictions</b>:使用限制 — <code>{"blackout_dates": bool, "weekdays_only": bool, "seasonal": str|null, "reservation_required": bool}</code></li>
    <li><b>availability</b>:未来 30 天的可预订状态字典(museumkey 不可用)。</li>
  </ul>

  <h3>Coupon form 值域</h3>
  <ul class="schema-list">
    <li><b>free</b>:完全免费入场</li>
    <li><b>percent-off</b>:百分比折扣,如 50% off</li>
    <li><b>dollar-off</b>:固定金额减免,如 $5 off</li>
    <li><b>per-person-price</b>:固定人头价,如 Adults $5 / Kids $3</li>
    <li><b>discount</b>:笼统折扣(AI 无法提取具体数值)</li>
  </ul>
</section>

<p class="foot-link"><a href="#" class="view-json-link" data-json-key="schema">查看技术 JSON 结构</a></p>
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
    return page_shell("Schema", body, "schema.html", data_blob=blob)


# =========================================================================
# PAGE 9 — data_quality.html
# =========================================================================

def page_data_quality(libs_data, attr_data, passes_data, raw_coupons_dir, status_banner: str = "") -> str:
    """Data-integrity red-flag dashboard.

    Why this page exists: spot-checking misses defects. The user explicitly
    distrusts抽检 ("抽检永远漏") — we need every category of integrity issue
    listed at once so the auditor can sweep through all defects systematically.
    See feedback_data_audit_over_spotcheck in user memory.

    Each panel surfaces one red-flag category. Severity classification:
      HIGH: empty coupon (panel 1), orphan slugs (panel 5) — real data loss.
      MED:  price disagreement (panel 2), audience/age contradiction (panel 4),
            extraction failures (panel 7) — likely extraction errors.
      LOW:  generic discount with no value (panel 3) — known and acceptable;
            umbrella attractions (panel 6) — structural, not a bug.

    No methodology / explanatory paragraphs in HTML output (per
    feedback_audit_no_transitional_text). Pure data + short labels only.
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

    # ── Summary table ───────────────────────────────────────────────────
    summary = [
        ("1", "HIGH", "Empty coupon where catalog says a pass exists", p1_count),
        ("2", "INFO", "Cross-library price variance", p2_count),
        ("3", "LOW",  "form=discount with null value", p3_count),
        ("4", "MED",  "age_range contradicts the labelled audience", p4_count),
        ("5", "HIGH", "Orphan raw coupon files (slug drift)", p5_count),
        ("6", "LOW",  "Umbrella attractions", p6_count),
        ("7", "MED",  "Raw extraction failures (status != ok)", p7_count),
    ]
    sum_rows = []
    for idx, sev, label, n in summary:
        style = ""
        if n > 0:
            if sev == "HIGH":
                style = ' style="background:var(--rd-pale);color:var(--rd);font-weight:600"'
            elif sev == "MED":
                style = ' style="background:var(--or-pale);color:var(--or)"'
        sum_rows.append(
            f'<tr{style}><td>{idx}</td><td>{sev}</td><td>{esc(label)}</td>'
            f'<td class="num">{n}</td></tr>'
        )
    summary_html = (
        '<table class="data-table"><thead><tr>'
        '<th>#</th><th>severity</th><th>category</th><th>count</th>'
        f'</tr></thead><tbody>{"".join(sum_rows)}</tbody></table>'
    )

    body = f"""
<h1 class="page-title">Data Quality · 数据质量红旗</h1>

{status_banner}

<section class="panel">
  <h3>Summary <span class="num-pill">7 categories</span></h3>
  {summary_html}
</section>

<section class="panel" id="dq1">
  <h3>1. Empty coupon where catalog says a pass exists <span class="num-pill">{p1_count}</span></h3>
  {p1_html}
</section>

<section class="panel" id="dq2">
  <h3>2. Cross-library price variance <span class="num-pill">{p2_count}</span> · informational</h3>
  {p2_html}
</section>

<section class="panel" id="dq3">
  <h3>3. form=discount with null value <span class="num-pill">{p3_count}</span></h3>
  {p3_html}
</section>

<section class="panel" id="dq4">
  <h3>4. age_range contradicts the labelled audience <span class="num-pill">{p4_count}</span></h3>
  {p4_html}
</section>

<section class="panel" id="dq5">
  <h3>5. Orphan raw coupon files <span class="num-pill">{p5_count}</span></h3>
  {p5_html}
</section>

<section class="panel" id="dq6">
  <h3>6. Umbrella attractions <span class="num-pill">{p6_count}</span></h3>
  {p6_html}
</section>

<section class="panel" id="dq7">
  <h3>7. Raw extraction failures <span class="num-pill">{p7_count}</span></h3>
  {p7_html}
</section>
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

main { max-width: 1280px; margin: 0 auto; padding: 28px 24px 80px; }

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
.attr-list { display: flex; flex-direction: column; gap: 28px; }
.attr-card {
  background: var(--white); border: 1px solid var(--rule); border-radius: 10px;
  padding: 24px; font-size: 13px;
}

.attr-card .top-row {
  display: flex; gap: 24px; margin: 14px 0 18px;
  padding-bottom: 18px; border-bottom: 1px solid var(--rule);
}
.attr-card .hero-side { flex: 0 0 250px; }
.attr-card .meta-side { flex: 1 1 auto; min-width: 0; }

.hero-big {
  width: 250px; max-width: 100%; height: auto; max-height: 200px;
  object-fit: cover; border-radius: 8px; cursor: zoom-in; display: block;
  border: 1px solid var(--rule);
}
.hero-big.noimg {
  width: 250px; max-width: 100%; height: 160px;
  background: var(--paper); border: 1px dashed var(--rule-strong); border-radius: 8px;
  display: flex; align-items: center; justify-content: center; color: var(--ink-3);
  font-size: 12px;
}

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

/* Lineage */
.lineage-svg { width: 100%; max-width: 900px; height: auto; display: block; margin: 20px auto; background: var(--white); border: 1px solid var(--rule); border-radius: 8px; padding: 16px; }
.lineage-foot { text-align: center; color: var(--ink-3); }

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

    # Compute red-flag counts once; both index.html and data_quality.html
    # render the same status banner so the verdict is consistent.
    raw_coupons_dir = ROOT / "data" / "raw" / "pass_coupons"
    dq_counts = compute_dq_counts(libs_data, attr_data, passes_data, raw_coupons_dir)
    banner = status_banner_html(dq_counts)

    print("[2/8] index.html")
    write("index.html", page_index(libs_data, attr_data, passes_data, libcat, status_banner=banner))

    print("[3/8] libraries.html")
    write("libraries.html", page_libraries(libs_data, libcat=libcat, branches_data=branches_data))

    print("[4/8] attractions.html")
    attr_html, missing_image = page_attractions(attr_data, passes_data=passes_data, libs_data=libs_data)
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

    print("[9/9] data_quality.html")
    write("data_quality.html", page_shell(
        "Data Quality",
        page_data_quality(libs_data, attr_data, passes_data, raw_coupons_dir, status_banner=banner),
        "data_quality.html",
    ))

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
