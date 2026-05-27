from __future__ import annotations

import csv
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from malibbene.sources_v2.assabet.booking_probe import probe_card, _date_path

TODAY = "2026-05-27"
SEED = 20260527

NETWORK_CARD = {
    "NOBLE": ("WAKEFIELD_BARCODE", "wakefield"),
    "MVLC": ("WILMINGTON_BARCODE", "wilmington"),
    "Minuteman": ("SOMERVILLE_BARCODE", "somerville"),
    "MBLN": ("BPL_BARCODE", "bpl"),
}
PROBER_OVERRIDE = {
    "wakefield": ("READING_BARCODE", "reading"),
}
UNTESTABLE = {"wilmington", "somerville"}
MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


@dataclass(frozen=True)
class Candidate:
    pool: str
    library_id: str
    attraction_slug: str


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prober_for(library_id: str, network: str) -> tuple[str, str] | None:
    if library_id in UNTESTABLE:
        return None
    if library_id in PROBER_OVERRIDE:
        return PROBER_OVERRIDE[library_id]
    return NETWORK_CARD.get(network)


def available_dates(pass_row: dict, limit: int = 4) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for iso, status in sorted((pass_row.get("availability") or {}).items()):
        if iso >= TODAY and status == "available":
            y, m, d = iso.split("-")
            out.append((f"{y}-{MONTHS[int(m) - 1]}", d))
            if len(out) >= limit:
                break
    return out


def expected_verdict(pass_row: dict) -> str | None:
    rr = pass_row.get("residency_restriction") or {}
    if pass_row.get("requires_own_card"):
        return "rejected_resident"
    if rr.get("restricted") == "yes" and rr.get("scope") == "town":
        return "rejected_resident"
    if rr.get("restricted") == "no":
        return "accepted"
    if rr.get("restricted") == "yes" and rr.get("scope") == "ma":
        return "accepted"
    return None


def build_pools(passes: list[dict], libraries: dict[str, dict]) -> dict[str, list[Candidate]]:
    wanted = {"Minuteman", "NOBLE", "MVLC", "MBLN"}
    by_pool: dict[str, list[Candidate]] = {
        "s1_minuteman": [],
        "s2_noble": [],
        "s3_mvlc": [],
        "s5_noble_detail": [],
        "extra_assabet": [],
    }
    for row in passes:
        lib = libraries[row["library_id"]]
        if lib["platform"] != "assabet" or lib["network"] not in wanted:
            continue
        if not available_dates(row):
            continue
        if prober_for(lib["id"], lib["network"]) is None:
            continue
        cand = Candidate("", lib["id"], row["attraction_rawslug"])
        if lib["network"] == "Minuteman":
            by_pool["s1_minuteman"].append(cand)
        elif lib["network"] == "NOBLE":
            by_pool["s2_noble"].append(cand)
            by_pool["s5_noble_detail"].append(cand)
        elif lib["network"] == "MVLC":
            by_pool["s3_mvlc"].append(cand)
        by_pool["extra_assabet"].append(cand)
    return by_pool


def sample_from_pool(name: str, pool: list[Candidate], take: int, used: set[tuple[str, str]]) -> list[Candidate]:
    rng = random.Random(f"{SEED}:{name}")
    candidates = [c for c in pool if (c.library_id, c.attraction_slug) not in used]
    rng.shuffle(candidates)
    picked = []
    for cand in candidates:
        picked.append(Candidate(name, cand.library_id, cand.attraction_slug))
        used.add((cand.library_id, cand.attraction_slug))
        if len(picked) >= take:
            break
    return picked


def main() -> None:
    out_root = ROOT / "audit" / "strict_audit_20260527" / "outputs"
    out_root.mkdir(parents=True, exist_ok=True)

    env = load_env()
    seeds = {row["id"]: row for row in load_json(ROOT / "config" / "library_seeds.json")["libraries"]}
    passes = load_json(ROOT / "data" / "structured" / "passes.json")["passes"]
    libraries = {row["id"]: row for row in load_json(ROOT / "data" / "structured" / "libraries.json")["libraries"]}
    pass_index = {(row["library_id"], row["attraction_rawslug"]): row for row in passes}

    pools = build_pools(passes, libraries)
    used: set[tuple[str, str]] = set()
    sample: list[Candidate] = []
    sample += sample_from_pool("s1_minuteman", pools["s1_minuteman"], 12, used)
    sample += sample_from_pool("s2_noble", pools["s2_noble"], 12, used)
    sample += sample_from_pool("s3_mvlc", pools["s3_mvlc"], 12, used)
    sample += sample_from_pool("s5_noble_detail", pools["s5_noble_detail"], 12, used)
    sample += sample_from_pool("extra_assabet", pools["extra_assabet"], 44, used)

    rows = []
    for idx, cand in enumerate(sample, start=1):
        pass_row = pass_index[(cand.library_id, cand.attraction_slug)]
        lib = libraries[cand.library_id]
        prober = prober_for(cand.library_id, lib["network"])
        env_key, prober_label = prober
        barcode = env[env_key]
        dates = available_dates(pass_row)
        result = {
            "index": idx,
            "pool": cand.pool,
            "library_id": cand.library_id,
            "library_name": lib["name"],
            "network": lib["network"],
            "attraction_slug": pass_row["attraction_slug"],
            "attraction_rawslug": pass_row["attraction_rawslug"],
            "source_url": pass_row["source_url"],
            "pass_form": pass_row["pass_form"],
            "expected_verdict": expected_verdict(pass_row),
            "structured_requires_own_card": bool(pass_row.get("requires_own_card")),
            "structured_residency": json.dumps(pass_row.get("residency_restriction"), ensure_ascii=False),
            "prober_card": prober_label,
            "probe_verdict": None,
            "probe_url": None,
            "probe_date": None,
            "status": "no_conclusive_date",
            "issue": "",
        }
        base = f"https://{seeds[cand.library_id]['domain']}"
        for ym, day in dates:
            url = _date_path(base, cand.attraction_slug, ym, day)
            result["probe_url"] = url
            result["probe_date"] = f"{ym}/{day}"
            try:
                probe = probe_card(url, barcode)
            except Exception as exc:
                result["status"] = f"error:{type(exc).__name__}"
                result["issue"] = str(exc)[:240]
                time.sleep(1.0)
                continue
            result["probe_verdict"] = probe["verdict"]
            if probe["verdict"] in {"accepted", "rejected_resident"}:
                result["status"] = "conclusive"
                break
            if probe["verdict"] == "booked_unexpectedly":
                result["status"] = "safety_stop"
                result["issue"] = "Probe appeared to finalize unexpectedly; manual review required."
                rows.append(result)
                break
            time.sleep(0.8)

        expected = result["expected_verdict"]
        actual = result["probe_verdict"]
        if result["status"] == "conclusive" and expected and actual and expected != actual:
            result["issue"] = f"Structured data expects {expected}, but live card validation returned {actual}."
        elif result["status"] != "conclusive" and not result["issue"]:
            result["issue"] = "Could not reach a conclusive card-validation result on a future available date."
        rows.append(result)
        if result["status"] == "safety_stop":
            break
        time.sleep(1.0)

    json_path = out_root / "assabet_audit_results.json"
    csv_path = out_root / "assabet_audit_results.csv"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {json_path} and {csv_path}")


if __name__ == "__main__":
    main()
