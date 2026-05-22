"""从 data/structured/* 选出 testgame 的真实抽样子集并规范成前端数据形状。

铁律：只搬运真实数据，绝不补值。coupon 缺失 -> summary=None；residency 原样透传。
"""
from __future__ import annotations

# 9 馆，跨 NOBLE/Minuteman/MVLC/MBLN/OCLN 5 联盟，居民/开放/未标注混合
SAMPLE_LIB_IDS = [
    "lynn", "lynnfield", "belmont", "acton",
    "chelmsford", "andover", "malden", "quincy", "lexington",
]
# 7 景点；blithewold 是全库唯一"仅 resident-only 馆提供"的景点 -> 状态 4 锚点
SAMPLE_ATTRACTION_SLUGS = [
    "new-england-aquarium", "museum-of-science", "isabella-stewart-gardner-museum",
    "zoo-new-england", "boston-childrens-museum", "peabody-essex-museum", "blithewold",
]
# 抽样范围外的镇，用作非居民 Home Town
EXTRA_TOWNS = ["Salem", "Worcester"]


def _adult_price(attraction: dict):
    for pr in attraction.get("prices") or []:
        if pr.get("audience") == "adult" and pr.get("price") is not None:
            return pr["price"]
    return None


def select_sample(libraries: list[dict], attractions: list[dict], passes: list[dict]) -> dict:
    lib_by_id = {l["id"]: l for l in libraries}
    attr_by_slug = {a["slug"]: a for a in attractions}

    missing_libs = [i for i in SAMPLE_LIB_IDS if i not in lib_by_id]
    missing_attrs = [s for s in SAMPLE_ATTRACTION_SLUGS if s not in attr_by_slug]
    if missing_libs or missing_attrs:
        raise ValueError(f"样本不在数据集中: libs={missing_libs} attractions={missing_attrs}")

    out_libs = [
        {"id": l["id"], "name": l["name"], "town": l["town"], "network": l["network"]}
        for l in (lib_by_id[i] for i in SAMPLE_LIB_IDS)
    ]
    out_attrs = []
    for s in SAMPLE_ATTRACTION_SLUGS:
        a = attr_by_slug[s]
        booking = (a.get("reservation") or {}).get("booking_url")
        out_attrs.append({
            "slug": a["slug"],
            "name": a["name"],
            "website": a.get("website"),
            "booking_url": booking or a.get("website"),
            "price_adult": _adult_price(a),
        })

    lib_set = set(SAMPLE_LIB_IDS)
    attr_set = set(SAMPLE_ATTRACTION_SLUGS)
    out_passes = []
    for p in passes:
        if p["library_id"] not in lib_set or p["attraction_slug"] not in attr_set:
            continue
        l = lib_by_id[p["library_id"]]
        rr = p.get("residency_restriction") or {}
        coupon = p.get("coupon") or {}
        out_passes.append({
            "library_id": p["library_id"],
            "attraction_slug": p["attraction_slug"],
            "network": l["network"],
            "library_name": l["name"],
            "library_town": l["town"],
            "residency": rr.get("restricted", "unknown"),
            "scope": rr.get("scope"),
            "summary": coupon.get("summary"),  # 可能为 None，原样保留
        })

    towns = sorted({l["town"] for l in out_libs}) + list(EXTRA_TOWNS)
    return {"towns": towns, "libraries": out_libs, "attractions": out_attrs, "passes": out_passes}
