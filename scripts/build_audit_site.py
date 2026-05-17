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
    "weekdays_only": "weekdays only · 仅工作日",
    "weekends_only": "weekends only · 仅周末",
    "weekends_excluded": "no weekends · 不接受周末",
    "blackout_dates": "blackout dates · 部分日期黑名单",
    "reservation_required": "reservation needed · 需预约",
    "id_required": "ID at gate · 入场出示证件",
    "residents_only": "residents only · 仅居民",
    "seasonal": "seasonal · 季节性开放(详见原文)",
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


# Shared helper for histogram tables on detail pages
def histogram_table(counter: Counter, total: int, label_map: dict | None = None, max_rows: int | None = None) -> str:
    if not counter:
        return '<p class="honest-gap">无数据</p>'
    most = counter.most_common(max_rows) if max_rows else counter.most_common()
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
            f'<tr><td>{esc(lab)}</td>'
            f'<td class="bar-cell"><span class="bar">{"█" * bar_w}</span></td>'
            f'<td class="num">{n}</td><td class="pct">{pct}%</td></tr>'
        )
    return f'<table class="histogram">{"".join(rows)}</table>'


def half_price_subpattern(raw: str) -> str:
    """Classify a half-price pass into A/B/C/D/E or 'other' by raw text."""
    import re
    r = (raw or "").lower()
    if not r:
        return "none"
    if not ("half" in r or "50%" in r or "1/2 price" in r):
        return "none"
    if re.search(r'one\s+vehicle|per\s+car|per\s+vehicle|in\s+one\s+car|in 1 vehicle', r):
        return "E"
    if re.search(r'\d+\s+adults?.{0,40}\d+\s+children?\s+at\s+\$\d', r):
        return "B"
    if re.search(r'adults?\s+at\s+(?:50%|half|1/2)\s*.{0,80}children?\s+at\s+\$\d', r):
        return "B"
    if re.search(r'only applies to adult|adult and child pricing|adult\s+pricing only', r):
        return "D"
    if re.search(r'under\s+\d+\s+(?:are|admitted)?\s*free|under\s+\d+.*always.*free|children\s+under', r):
        return "C"
    return "A"


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
        "Coupon summary present · 摘要文字已生成": sum(1 for p in passes if (p.get("coupon") or {}).get("summary")),
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

    # Capacity distribution
    cap_kind_counter: Counter = Counter()
    cap_people_n_counter: Counter = Counter()
    for p in passes:
        cap = (p.get("coupon") or {}).get("capacity") or {}
        kind = cap.get("kind") or "unspecified"
        if kind == "people":
            n = cap.get("n")
            if n is not None:
                cap_people_n_counter[n] += 1
            else:
                cap_people_n_counter["(unspecified n)"] += 1
        else:
            cap_kind_counter[kind] += 1

    # Audience-split distribution: how many audience_policies entries per pass
    audience_split_counter: Counter = Counter()
    for p in passes:
        aps = (p.get("coupon") or {}).get("audience_policies") or []
        n = len(aps)
        if n == 0:
            audience_split_counter["0 (no extraction)"] += 1
        elif n == 1:
            audience_split_counter["1 (party-wide single tier)"] += 1
        elif n == 2:
            audience_split_counter["2 (typical mixed)"] += 1
        else:
            audience_split_counter[f"{n} (complex)"] += 1

    def coverage_list(cov: dict, total: int) -> str:
        rows = []
        for k, v in cov.items():
            pct = round(100 * v / total) if total else 0
            rows.append(f'<li><span class="cov-label">{esc(k)}</span><span class="cov-frac">{v}/{total}</span><span class="cov-pct">{pct}%</span></li>')
        return f'<ul class="coverage">{"".join(rows)}</ul>'

    plat_counter = Counter(libcat["libraries"][lid]["platform"] for lid in libcat["libraries"])

    anomalies = []
    # passes with no coupon summary (extraction gap)
    n_no_summary = sum(1 for p in passes if not (p.get("coupon") or {}).get("summary"))
    n_no_coupon = sum(1 for p in passes if not p.get("coupon"))
    anomalies.append(
        f"<li><b>{n_no_coupon}</b> 条 pass 没有 coupon 字段 — "
        f"含义:plan-9 再抽取未覆盖到这些行,需补跑 subagent — "
        f"<a href='policies.html'>see Policies</a></li>"
    )
    anomalies.append(
        f"<li><b>{n_no_summary}</b> 条 pass 的 coupon.summary 为空(含 coupon 字段缺失的) — "
        f"含义:AI 抽出了结构但没生成摘要文字,前端 fallback 会显示 '(no extraction)'</li>"
    )
    n_unknown_pt = sum(1 for p in passes if p.get("pass_type") == "unknown")
    anomalies.append(
        f"<li><b>{n_unknown_pt}</b> 条 pass 的 pass_type 是 unknown(没归类成 digital/physical/loan-card 中的任一个) — "
        f"含义:从原始 HTML 抓不到明确的 pass 类型标识符</li>"
    )
    # plan-10: count only pairs where BOTH slugs are still present as separate entities.
    _attr_slugs = {a["slug"] for a in attr_data["attractions"]}
    n_dup = sum(1 for a, b in KNOWN_DUPLICATES if a in _attr_slugs and b in _attr_slugs)
    anomalies.append(
        f"<li><b>{n_dup}</b> 对 attraction slug 重复(同一景点被存了两条记录) — "
        f"含义:数据建模历史遗留 bug,前端会显示成两张不同的卡,需合并 — "
        f"<a href='duplicates.html'>see Duplicates</a></li>"
    )
    n_missing_price = n_attrs - attr_cov["Ticket price (any tier) · 票价(任一层级)"]
    anomalies.append(
        f"<li><b>{n_missing_price}</b> 个景点没有任何价格层级(adult/child/youth/senior/...)— "
        f"含义:景点官网无公开标价,或票价是 per-show / per-vehicle 浮动 — "
        f"<a href='gaps.html'>see Gaps</a></li>"
    )
    n_missing_desc = n_attrs - attr_cov["Description · 简介"]
    anomalies.append(
        f"<li><b>{n_missing_desc}</b> 个景点没有简介文字 — "
        f"含义:景点官网无 og:description / about 页 抓取失败 / 网站 403 拦截</li>"
    )

    # Precompute histogram HTML (dicts can't be inlined in f-strings)
    _coupon_form_label = {
        "free":             "FREE · 完全免费",
        "percent-off":      "Percent off · 百分比折扣",
        "dollar-off":       "Dollar off · 固定金额减免",
        "per-person-price": "Per-person price · 人头定价",
        "discount":         "Generic discount · 笼统折扣(无数值)",
    }
    _cap_kind_label = {
        "vehicle":     "vehicle · 按车",
        "ticket":      "ticket · 单张票",
        "unspecified": "unspecified · 未明示",
    }
    _coupon_form_html = histogram_table(coupon_form_counter, sum(coupon_form_counter.values()) or 1, _coupon_form_label)
    _cap_people_html = histogram_table(cap_people_n_counter, n_passes)
    _cap_kind_html = histogram_table(cap_kind_counter, n_passes, _cap_kind_label) if cap_kind_counter else ""
    _audience_split_html = histogram_table(audience_split_counter, n_passes)

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
  <p class="methodology">
    Plan-9 将旧版 <code>discount</code> + <code>policy</code> 两个字段合并为统一的 <b>Coupon 模型</b>
    (<code>capacity</code> + <code>audience_policies</code> + <code>summary</code>)。
    以下三个面板展示新 schema 的分布情况,替代了原有的 eligibility-tags / restrictions / bonuses 直方图。
  </p>
</section>

<section class="panel">
  <h3>Coupon form 分布 · {sum(coupon_form_counter.values())} audience-policy 条目(含多条目 pass)</h3>
  <p class="methodology">
    <b>口径</b>:每条 pass 的 <code>coupon.audience_policies</code> 数组中每个条目各计一次,分母是条目总数。
  </p>
  {_coupon_form_html}
</section>

<section class="panel">
  <h3>Capacity 分布 · people(n) 明细</h3>
  <p class="methodology">
    <b>口径</b>:分母 = 全部 {n_passes} 条 pass。<code>people</code> 类按具体 n 值展开;其它 kind 合并显示。
  </p>
  {_cap_people_html}
  {_cap_kind_html}
</section>

<section class="panel">
  <h3>Audience-split 分布 · audience_policies 条目数 per pass</h3>
  <p class="methodology">
    <b>1 条</b>= party-wide 统一优惠(无需按大人/小孩分价);<b>2+ 条</b>= 多层级 (adult / child / ...) 各自有不同优惠,前端需逐行渲染。
  </p>
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
  <p class="methodology">
    这一节列出 AI 抽取过程中可能值得人工抽查的"可疑点"。每条都说明了"是什么/含义/怎么追溯"。
    数字旁的链接跳转到相应专题页,可逐条核对 raw 原文与 AI 输出。
  </p>
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

<section class="panel" style="border-left: 4px solid var(--rd); background: var(--rd-pale);">
  <h3 style="color: var(--rd); margin-top:0">⚠ lib_id 是数据爬取模型,不是用户产品概念</h3>
  <p class="methodology">
    <b>本期 lib_id 设计</b>:每个 id = 一个发券组织(例如 <code>bpl</code> 代表整个 BPL 系统,即使它下辖 25+ 物理分馆)。
    这只在<b>数据爬取层</b>有意义 — 用于聚合从同一平台/账号爬下来的 passes。
  </p>
  <p class="methodology">
    <b>但对用户产品体验,lib_id 没有正确语义</b>:
    <br>① <b>电子券(digital pass)</b>:用户只关心折扣 — "MFA 半价" — 无需任何"组织"前缀。展示 "by BPL" 或 "by Wakefield Library" 是噪音
    <br>② <b>实体券(physical / loan-card)</b>:用户需要<b>具体物理地址</b>开车去取 — "BPL 总部" 这个抽象不能告诉用户去 Copley Square 还是 East Boston;前者 Back Bay 后者隔海港
  </p>
  <p class="methodology" style="color: var(--g);">
    <b>✅ plan-6 已落地</b>:passes.json 现已带 <code>pickup_method</code>(digital | physical_at_branch)+ <code>pickup_branches[]</code>;
    BPL/Cambridge/Brookline 三家多分馆 lib 的 branch 明细见<b>本页底部的"多分馆 lib"面板</b>。
    单分馆 lib 自动合成 <code>&lt;lib_id&gt;--main</code> branch(地址 = 该 lib 自己的地址)。
  </p>
</section>

<p class="methodology">
  下面这张表是<b>本期数据爬取层</b>的视图:59 个 lib_id 各自唯一,无重复。
  BPL/Cambridge/Brookline 三家的 branch 拆分见底部"多分馆 lib"面板。
</p>

<section class="dist-grid">
  <div class="panel dist-panel dist-wide">
    <h3>数据爬取平台 · Scraping platform <span class="block-meta">基础设施视角 · 不直接对用户暴露</span></h3>
    {histogram_table(plat_counter, n_libs)}
    <p class="methodology" style="margin-top:8px">
      <b>这一项是 ops/审计视角,不是产品决策</b>。Assabet / LibCal / MuseumKey 是图书馆使用的 pass 管理后端系统,用户感知不到。<br>
      <b>价值</b>:① <b>数据脆弱性</b> — 88% 数据靠 Assabet 单一来源,若失效或收费,影响面广;② <b>功能差异</b> — 不同平台暴露的字段不同(库存日历 / 还回规则等),影响下游能爬到多少元数据。
    </p>
  </div>
</section>

<p class="methodology" style="background: var(--g-pale); border-left-color: var(--g);">
  <b>本页不展示"馆际网络分布"等组织抽象</b> — 网络归属与 lib_id 一样,只在数据建模层有意义,不是用户做"我能不能用这张 pass"决策时关心的事。
  网络字段仍保留在下方明细表的 <code>network</code> 列里供审计核对,但不再单独建直方图占面板位置。
</p>

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
<p class="methodology">
  这张表服务两件事:① <b>数据正确性</b> — 审计可以直接对照官网核对每个 branch 的地址;
  ② <b>用户决策</b> — 持实体券的用户必须开车到这里取卡,这是 plan-6 的核心交付。
  其余 56 个 lib 自动合成 <code>&lt;lib_id&gt;--main</code> branch,不再单独列。
</p>
{"".join(sections)}
"""


# =========================================================================
# PAGE 3 — attractions.html
# =========================================================================

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
            method_label = "E-pass"
        elif pickup == "physical_at_branch":
            branches = mp.get("pickup_branches") or []
            method_label = f"Pickup at {branches[0]}" if branches else "Pickup at branch"
        else:
            method_label = pickup or "(unknown)"
        summary = (mp.get("coupon") or {}).get("summary") or "(no extraction)"
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
        age_rows_html = []
        for k, label_en, label_zh in [
            ("adult",  "Adult",  "成人"),
            ("youth",  "Youth",  "青少年 (11-17)"),
            ("child",  "Child",  "儿童"),
            ("senior", "Senior", "老人 (65+)"),
        ]:
            v = _tier_price(age_p, k)
            if v is None:
                age_rows_html.append(
                    f'<div class="kv kv-gap"><span class="k">{label_en} · {label_zh}</span>'
                    f'<span class="v dash">-</span></div>'
                )
            else:
                any_price = True
                age_rows_html.append(
                    f'<div class="kv"><span class="k">{label_en} · {label_zh}</span>'
                    f'<span class="v verified">${esc(str(v))}</span></div>'
                )
        fua = age_p.get("free_under_age")
        if fua is not None:
            age_rows_html.append(
                f'<div class="kv"><span class="k">Free under · 免费年龄</span>'
                f'<span class="v verified">N &lt; {fua}</span></div>'
            )

        identity_rows_html = []
        for k, label_en, label_zh in [
            ("student",  "Student",  "学生"),
            ("educator", "Educator", "教师"),
            ("military", "Military", "军人"),
        ]:
            v = _tier_price(ident_p, k)
            if v is None:
                identity_rows_html.append(
                    f'<div class="kv kv-gap"><span class="k">{label_en} · {label_zh}</span>'
                    f'<span class="v dash">-</span></div>'
                )
            else:
                any_price = True
                identity_rows_html.append(
                    f'<div class="kv"><span class="k">{label_en} · {label_zh}</span>'
                    f'<span class="v verified">${esc(str(v))}</span></div>'
                )

        family_v = price.get("family") if price else None
        family_row_html = ""
        if family_v is None:
            family_row_html = (
                '<div class="kv kv-gap"><span class="k">Family · 家庭通票</span>'
                '<span class="v dash">-</span></div>'
            )
        else:
            any_price = True
            family_row_html = (
                f'<div class="kv"><span class="k">Family · 家庭通票</span>'
                f'<span class="v verified">${esc(str(family_v))}</span></div>'
            )

        notes = price.get("notes") if price else None
        notes_row_html = ""
        if notes:
            notes_row_html = (
                f'<div class="kv kv-wide"><span class="k">Notes · 备注</span>'
                f'<span class="v">{esc(notes)}</span></div>'
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
    <h3 class="block-title">Prices · 票价层级 <span class="block-meta">两层模型 · 年龄定价 + 身份定价 · 有数据绿色 · 无数据灰色短划</span></h3>
    <h4 class="block-subtitle">年龄定价 · Age-based pricing <span class="block-meta">适用任何符合年龄的访客</span></h4>
    <div class="kv-grid">{"".join(age_rows_html)}</div>
    <h4 class="block-subtitle">身份定价 · Identity-based pricing <span class="block-meta">需出示证件(学生证 / 教师 ID / 军人证)</span></h4>
    <div class="kv-grid">{"".join(identity_rows_html)}</div>
    <h4 class="block-subtitle">Family / Notes</h4>
    <div class="kv-grid">{family_row_html}{notes_row_html}</div>
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
        "bucket_open_daily": "Open every day · 全周开放",
        "bucket_partial":    "Partially closed · 部分天关闭(博物馆主流模式)",
        "bucket_seasonal":   "Seasonal · 仅特定月份开放",
        "bucket_varies":     "Varies by property · 景点本身有多 property(非图书馆分馆问题)",
        "bucket_nodata":     "No data · 无数据",
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
    <h3>Price tier 覆盖率 · 核心 5 类</h3>
    <p class="methodology" style="margin-bottom:8px">
      <b>家庭用户核心关注</b>:成人 / 年轻人 / 儿童 / 学生 / 教师。<br>
      schema 升级方向(plan-7):分成两层 = <b>年龄定价</b>(adult/youth/child 带具体年龄区间,如 "3-7 岁 $14",不模糊到"儿童")+ <b>身份定价</b>(student/educator)。
    </p>
    {histogram_table(core_counter, n_attrs, tier_label_map)}
  </div>
  <div class="panel dist-panel">
    <h3>Price tier 覆盖率 · 次级 3 类</h3>
    <p class="methodology" style="margin-bottom:8px">
      Senior / Military / Family-套票 — 数据仍抓,但前端不放主视觉。<br>
      <b>军人免费</b>本身是博物馆固有政策,与领 coupon 决策无关。<b>EBT / 互惠会员 / 本校学生 / 本镇居民</b> 等边缘群体不进 schema,留 notes 兜底或让用户去官网核实。
    </p>
    {histogram_table(secondary_counter, n_attrs, tier_label_map)}
  </div>
  <div class="panel dist-panel">
    <h3>Hours 分布 · 3 大类</h3>
    {histogram_table(hours_status_counter, n_attrs, hours_label_map)}
    <p class="methodology" style="margin-top:8px">
      <b>用户视角 3 类</b>:<br>
      ① <b>Open every day</b> — 任何时候都行<br>
      ② <b>Partially closed</b> — 一周有 1+ 天关(博物馆主流,典型 Tue closed 或 weekends-only);用户必须看具体哪天关<br>
      ③ <b>Seasonal</b> — 仅特定月份开放<br>
      <i>Varies by property</i> 指<b>景点本身有多 property</b>(Trustees of Reservations 100+ properties / Mass Audubon 80+ / 剧院按演出日期排时间)— 不是图书馆分馆问题(那个 plan-6 已经解决)。这 11 个目前以聚合方式保留,详情需查景点官网。
    </p>
  </div>
  <div class="panel dist-panel">
    <h3>类别分布 · Categories(7 个粗类)</h3>
    {histogram_table(cat_canon_counter, n_attrs)}
    <p class="methodology" style="margin-top:8px">
      <b>显示规则</b>:原 21 个 Assabet 标签按"本质归属"合并到 7 个干净的粗类(每个 1 个英文单词)。
      合并规则不按数量、按主题:<br>
      ① <b>Tours / Recreation 被吸收</b> — Tours 4 条 100% 同时标 History(导览只是表现形式),Recreation 7/10 同时标 Nature(都是户外空间)<br>
      ② <b>Sports 保留</b> — 虽然仅 2 条(Naismith / Patriots Hall of Fame),但体育主题独特,sports-fan 家庭会专门搜<br>
      ③ <b>Family ↔ Children 合并</b> — 我们产品本来就是给家庭用户,Family 标签信息量低<br>
      合并映射表:Art ← Art+Crafts · Children ← Family+Children · History ← History+Architecture+Governance+Military+Tours · Nature ← Nature+Ocean+Sky+Zoo+Recreation · Performance ← Music+Theatre+Dance+Entertainment · Science ← Science+Technology · Sports ← Sports
    </p>
  </div>
  <div class="panel dist-panel">
    <h3>字段覆盖率</h3>
    {histogram_table(cov_counter, n_attrs)}
    <p class="methodology" style="margin-top:8px">
      Hero image / hours / geo 接近全覆盖。Price 76%、Phone 90%、Description 93% — 剩余为诚实失败(theater / no_website / 403)。
    </p>
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

    def render_pass_article(p: dict, idx: int) -> str:
        lib = p["library_id"]
        slug = p["attraction_slug"]
        coupon = p.get("coupon") or {}
        summary = coupon.get("summary") or ""
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
            val_str = f" {value}" if value is not None else ""
            form_label = COUPON_FORM_LABEL_EN.get(form, form)
            ap_parts.append(f'<span class="ext badge badge-disc-{esc(form)}">{esc(audience)}: {esc(form_label)}{esc(str(val_str))}</span>')

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

    # ── Distribution stats for policies page (plan-9 coupon model) ───────
    n_passes = len(passes)
    pt_counter = Counter(p.get("pass_type") or "(unknown)" for p in passes)
    # pickup_method distribution
    pm_counter = Counter(p.get("pickup_method") or "(unknown)" for p in passes)
    n_multi_branch = sum(1 for p in passes if p.get("pickup_method") == "physical_at_branch" and len(p.get("pickup_branches") or []) > 1)
    # coupon form distribution (per audience_policy entry)
    pol_form_counter: Counter = Counter()
    for p in passes:
        for ap in (p.get("coupon") or {}).get("audience_policies") or []:
            pol_form_counter[ap.get("form", "discount")] += 1
    # capacity n distribution (people kind only)
    pol_cap_counter: Counter = Counter()
    for p in passes:
        cap = (p.get("coupon") or {}).get("capacity") or {}
        if cap.get("kind") == "people":
            pol_cap_counter[cap.get("n") if cap.get("n") is not None else "(unspecified n)"] += 1
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
        "digital": "E-pass · 在线即取(无需开车)",
        "physical-coupon": "Pickup · 去馆里取一次,不用还",
        "physical-circ": "Pickup &amp; Return · 去馆里取 + 还回去",
        "unknown": "Pass · 未分类(数据 bug,审计追)",
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
    _pol_cap_html = histogram_table(pol_cap_counter, n_passes, max_rows=10)
    _pol_restr_html = histogram_table(restr_counter, n_passes)

    body = f"""
<h1 class="page-title">Policies · {n_passes} passes · {len(pattern_meta)} patterns (plan-9 coupon model)</h1>

<section class="dist-grid">
  <div class="panel dist-panel dist-wide">
    <h3>Pass 形式 · 3 种取券方式(与前端术语一致)</h3>
    {_pol_pt_html}
    <p class="methodology" style="margin-top:8px">
      <b>用户决策核心维度</b>:三种取券方式与前端 PassTypeLabel 完全对齐:<br>
      ① <b>E-pass</b>:邮件/promo code 在家就拿到 — 最低摩擦<br>
      ② <b>Pickup</b>:去分馆领纸券或 promo paper,不用还 — 中等摩擦<br>
      ③ <b>Pickup &amp; Return</b>:去分馆借实体券/卡,用完次日要还回 — 最高摩擦<br>
      其中 <b>{n_multi_branch} 条 physical pass 可在 ≥2 个分馆取</b>(BPL/Cambridge/Brookline 的 fan-out),用户可选最近的。
    </p>
  </div>
  <div class="panel dist-panel">
    <h3>Coupon form 分布(plan-9 · audience_policy 条目)</h3>
    {_pol_form_html}
    <p class="methodology" style="margin-top:8px">
      每条 pass 的 coupon.audience_policies 数组中每个条目各计一次。
    </p>
  </div>
  <div class="panel dist-panel">
    <h3>Capacity n 分布(people kind · {sum(pol_cap_counter.values())} passes)</h3>
    {_pol_cap_html}
    <p class="methodology" style="margin-top:8px">
      "4 人" 是行业默认配置;前端价格估算应缺省按 4 人。
    </p>
  </div>
  <div class="panel dist-panel">
    <h3>Restrictions 分布(plan-9 side-channel)</h3>
    {_pol_restr_html}
    <p class="methodology" style="margin-top:8px">
      reservation_required / blackout_dates 是用户体验上最敏感的限制 — 卡片上要明确展示。
    </p>
  </div>
  <div class="panel dist-panel dist-wide">
    <h3>{len(pattern_meta)} 个 Coupon Pattern 占比(按 capacity/form/tiers 分组)</h3>
    <table class="histogram"><thead><tr><th>id</th><th>name</th><th></th><th class="num">n</th><th class="pct">%</th></tr></thead><tbody>{pattern_count_table}</tbody></table>
    <p class="methodology" style="margin-top:8px">
      点击 P1/P2... 直接跳转到该模式 section。前 5 个模式覆盖大约 ~70% passes,产品 UI 优先支持这几种。
    </p>
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
    # plan-10: filter to only pairs where BOTH slugs still exist as separate entities.
    # Once a legacy slug is collapsed to its canonical winner, the pair is resolved.
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
    body = f"""
<h1 class="page-title">Duplicates · {len(active_pairs)} pairs</h1>
<p>Pairs of attraction slugs that refer to the same real-world venue. Goal: pick one canonical slug, migrate libraries, retire the other.</p>
{"<p><i>All known duplicate pairs have been collapsed to canonical entities (plan-10). Mapping table: <code>src/malibbene/build/slug_canonical.py</code>.</i></p>" if not active_pairs else ""}
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
        <li><b>digital</b>:邮件即时发送的电子券,用户可立即下载并使用(553 个)。</li>
        <li><b>physical-coupon</b>:门店取纸质券,用完不归还(260 个)。</li>
        <li><b>physical-circ / loan-card</b>:循环借阅卡,用完需归还图书馆(172 个)。</li>
        <li><b>unknown</b>:未能识别(23 个)。</li>
      </ul>
    </li>
    <li><b>coupon</b>(plan-9):统一优惠模型,替代旧版 discount + policy 两个字段:
      <ul>
        <li><b>capacity</b>:<code>{"kind": "people"|"vehicle"|"ticket"|"unspecified", "n": int|null}</code> — 整张 coupon 覆盖的容量上限</li>
        <li><b>audience_policies</b>:数组,每项 = <code>{"audience", "age_range", "count", "form", "value"}</code>。
          <ul>
            <li><b>audience</b>: Everyone / Adult / Child / Youth / Senior / Vehicle / Single ticket</li>
            <li><b>form</b>: <code>free</code> / <code>percent-off</code> / <code>dollar-off</code> / <code>per-person-price</code> / <code>discount</code></li>
            <li><b>value</b>: 数值(如 50 = 50% off, 5 = $5 off),或 null(无数值/笼统)</li>
          </ul>
        </li>
        <li><b>summary</b>:人可读摘要,如 "Up to 4 · 50% off" — 前端展示核心字段</li>
      </ul>
    </li>
    <li><b>restrictions</b>(side-channel):使用限制 — <code>{"blackout_dates": bool, "weekdays_only": bool, "seasonal": str|null, "reservation_required": bool}</code></li>
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
            "coupon_keys": ["capacity", "audience_policies", "summary"],
            "audience_policy_keys": ["audience", "age_range", "count", "form", "value"],
            "coupon_forms": ["free", "percent-off", "dollar-off", "per-person-price", "discount"],
            "capacity_kinds": ["people", "vehicle", "ticket", "unspecified"],
            "pass_types": ["digital", "physical-coupon", "physical-circ", "unknown"],
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

    print("[2/8] index.html")
    write("index.html", page_index(libs_data, attr_data, passes_data, libcat))

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
