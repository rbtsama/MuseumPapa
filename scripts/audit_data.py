"""Comprehensive data-integrity audit for data/structured/*.json.

Read-only. Reports PASS/WARN/FAIL per check. Run before shipping data to the
frontend. Checks: counts, required fields, referential integrity (passes <->
libraries/attractions/branches), enum validity, residency per-library
uniformity, network sanity, coverage, duplicates, orphans.

Usage: python scripts/audit_data.py
Exit code 0 if no FAIL, 1 if any FAIL.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "data/structured"

CARD_ELIG = {"ma_resident", "town_resident", "town_or_works", "network", "none", "unknown"}
PASS_FORM = {"digital_email", "physical_circ", "physical_coupon"}
COUPON_FORM = {"free", "percent-off", "dollar-off", "per-person-price", "bogo", "discount"}
CAP_KIND = {"people", "vehicle", "ticket", "unspecified"}
RES_RESTRICTED = {"yes", "no", "unknown"}
RES_SCOPE = {"town", "ma", None}

results = []  # (level, msg)


def check(cond, ok_msg, fail_msg, level="FAIL"):
    results.append(("PASS", ok_msg) if cond else (level, fail_msg))
    return cond


def load(name):
    d = json.loads((S / f"{name}.json").read_text(encoding="utf-8"))
    return d[name], d.get("_meta", {})


def main():
    libs, lm = load("libraries")
    attrs, am = load("attractions")
    passes, pm = load("passes")
    branches, bm = load("branches")

    lib_ids = {l["id"] for l in libs}
    attr_slugs = {a["slug"] for a in attrs}

    # ---- counts ----
    check(len(libs) == 59, f"libraries=59", f"libraries={len(libs)} (expected 59)")
    check(len(libs) == lm.get("n_libraries"), "libraries _meta count matches", "libraries _meta mismatch")
    check(len(attrs) >= 40, f"attractions={len(attrs)}", f"attractions={len(attrs)} (<40)", "WARN")
    check(len(passes) > 900, f"passes={len(passes)}", f"passes={len(passes)} (<900)")
    check(len(passes) == pm.get("n_passes"), "passes _meta count matches", "passes _meta mismatch")

    # ---- libraries: required fields, enums, dups, zips ----
    dup_lib = [k for k, v in Counter(l["id"] for l in libs).items() if v > 1]
    check(not dup_lib, "no duplicate library ids", f"duplicate library ids: {dup_lib}")
    bad_elig = [l["id"] for l in libs if l.get("card_eligibility") not in CARD_ELIG]
    check(not bad_elig, "all card_eligibility valid", f"bad card_eligibility: {bad_elig}")
    no_zip = [l["id"] for l in libs if not l.get("resident_zips")]
    check(not no_zip, "all libraries have resident_zips", f"libraries missing resident_zips: {no_zip}")
    bad_zip = [l["id"] for l in libs for z in (l.get("resident_zips") or []) if not (isinstance(z, str) and len(z) == 5 and z.isdigit())]
    check(not bad_zip, "all resident_zips are 5-digit", f"bad zips at: {bad_zip[:5]}")
    no_net = [l["id"] for l in libs if not l.get("network")]
    check(not no_net, "all libraries have network", f"libraries missing network: {no_net}")
    # honesty invariant: non-unknown card_eligibility must carry a source phrase
    miss_phrase = [l["id"] for l in libs if l.get("card_eligibility") not in (None, "unknown") and not l.get("eligibility_source_phrase")]
    check(not miss_phrase, "every classified card_eligibility has a source phrase", f"classified WITHOUT phrase: {miss_phrase}", "WARN")

    # ---- attractions: name, dups, slugs ----
    dup_attr = [k for k, v in Counter(a["slug"] for a in attrs).items() if v > 1]
    check(not dup_attr, "no duplicate attraction slugs", f"duplicate attraction slugs: {dup_attr}")
    null_name = [a["slug"] for a in attrs if not a.get("name")]
    check(not null_name, "no attraction has null name", f"attractions with null name: {null_name}")

    # ---- passes: required fields, enums, referential integrity ----
    bad_form = [(p["library_id"], p["attraction_slug"]) for p in passes if p.get("pass_form") not in PASS_FORM]
    check(not bad_form, "all pass_form valid", f"bad pass_form: {bad_form[:5]}")
    orphan_lib = sorted({p["library_id"] for p in passes if p["library_id"] not in lib_ids})
    check(not orphan_lib, "every pass.library_id exists in libraries", f"orphan library_ids: {orphan_lib}")
    orphan_attr = sorted({p["attraction_slug"] for p in passes if p["attraction_slug"] not in attr_slugs})
    check(not orphan_attr, "every pass.attraction_slug exists in attractions",
          f"orphan attraction_slugs ({len(orphan_attr)}): {orphan_attr[:10]}", "WARN")
    # residency_restriction enum
    bad_res = [(p["library_id"], p["attraction_slug"]) for p in passes
               if (p.get("residency_restriction") or {}).get("restricted") not in RES_RESTRICTED]
    check(not bad_res, "all residency_restriction.restricted valid", f"bad restricted: {bad_res[:5]}")
    bad_scope = [(p["library_id"], p["attraction_slug"]) for p in passes
                 if (p.get("residency_restriction") or {}).get("scope") not in RES_SCOPE]
    check(not bad_scope, "all residency_restriction.scope valid", f"bad scope: {bad_scope[:5]}")
    # coupon enum where present
    bad_coupon = []
    for p in passes:
        c = p.get("coupon")
        if not c:
            continue
        if (c.get("capacity") or {}).get("kind") not in CAP_KIND:
            bad_coupon.append((p["library_id"], p["attraction_slug"], "capacity"))
        for ap in c.get("audience_policies", []):
            if ap.get("form") not in COUPON_FORM:
                bad_coupon.append((p["library_id"], p["attraction_slug"], ap.get("form")))
    check(not bad_coupon, "all coupon forms/capacity valid", f"bad coupon enums: {bad_coupon[:5]}")
    # duplicate (lib, slug) pass rows
    dup_pass = [k for k, v in Counter((p["library_id"], p["attraction_slug"]) for p in passes).items() if v > 1]
    check(not dup_pass, "no duplicate (library, attraction) pass rows", f"duplicate pass rows: {dup_pass[:5]}", "WARN")

    # ---- residency per-library uniformity (business doc: per-library policy) ----
    # A MA-party requirement (scope=ma) is ORTHOGONAL to town-residency: a
    # library can legitimately have town-open passes AND passes that need any MA
    # resident in the party. Only flag MIXED when a library actually has both
    # restricted=no AND restricted=yes-with-scope=town (the same town-residency
    # axis pointing both ways) — that's the real per-library inconsistency.
    has_open = defaultdict(bool)      # lib -> any restricted=no
    has_town_yes = defaultdict(bool)  # lib -> any restricted=yes & scope=town
    for p in passes:
        rr = p.get("residency_restriction") or {}
        r = rr.get("restricted")
        if r == "no":
            has_open[p["library_id"]] = True
        elif r == "yes" and rr.get("scope") == "town":
            has_town_yes[p["library_id"]] = True
    mixed = sorted(l for l in lib_ids if has_open[l] and has_town_yes[l])
    check(not mixed, "residency uniform per library (no mixed town-open / town-restricted)",
          f"MIXED residency libraries: {mixed}", "WARN")

    # ---- branches integrity ----
    orphan_branch = sorted({b["library_id"] for b in branches if b["library_id"] not in lib_ids})
    check(not orphan_branch, "every branch.library_id exists", f"orphan branch libs: {orphan_branch}")

    # ---- coverage (informational WARN only) ----
    n_coupon = sum(1 for p in passes if p.get("coupon"))
    n_avail = sum(1 for p in passes if p.get("availability"))
    n_res = sum(1 for p in passes if (p.get("residency_restriction") or {}).get("restricted") in ("yes", "no"))
    n_known_elig = sum(1 for l in libs if l.get("card_eligibility") not in (None, "unknown"))
    n_prices = sum(1 for a in attrs if a.get("prices"))
    n_hours = sum(1 for a in attrs if a.get("hours") and any(v and v != "unknown" for v in a["hours"].values()))

    print("=== COVERAGE (informational) ===")
    print(f"  libraries card_eligibility known: {n_known_elig}/{len(libs)}")
    print(f"  attractions w/ prices: {n_prices}/{len(attrs)} | w/ hours: {n_hours}/{len(attrs)}")
    print(f"  passes w/ coupon: {n_coupon}/{len(passes)} | availability: {n_avail}/{len(passes)} | residency known: {n_res}/{len(passes)}")
    print(f"  branches: {dict(Counter(b['library_id'] for b in branches))}")
    print()

    # ---- report ----
    fails = [m for lv, m in results if lv == "FAIL"]
    warns = [m for lv, m in results if lv == "WARN"]
    npass = sum(1 for lv, _ in results if lv == "PASS")
    print(f"=== AUDIT: {npass} passed, {len(warns)} warnings, {len(fails)} failures ===")
    for m in warns:
        print(f"  WARN: {m}")
    for m in fails:
        print(f"  FAIL: {m}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
