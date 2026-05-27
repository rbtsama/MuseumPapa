from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "audit" / "strict_audit_20260527" / "outputs"

SAMPLE = [
    "american-repertory-theater",
    "boch-center",
    "boston-childrens-museum",
    "boston-harbor-islands",
    "hale-education",
    "harvard-museums-of-science-and-culture",
    "ica-boston",
    "mfa",
    "museum-of-science",
    "new-england-aquarium",
]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def summary_match(expected: str, body: str) -> bool:
    expected = normalize_space(expected).lower()
    body = normalize_space(body).lower()
    if expected == "disc":
        return "discount" in body or "off" in body
    if expected == "free":
        return "free" in body
    return expected in body


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    passes = json.loads((ROOT / "data" / "structured" / "passes.json").read_text(encoding="utf-8"))["passes"]
    passes = [row for row in passes if row["library_id"] == "bpl" and row["attraction_slug"] in SAMPLE]
    passes.sort(key=lambda row: SAMPLE.index(row["attraction_slug"]))

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 2000})
        for row in passes:
            resp = page.goto(row["source_url"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            body = page.locator("body").inner_text()
            availability_html = ""
            try:
                page.locator("#s-lc-pass-availability-content").wait_for(timeout=8000)
                availability_html = page.locator("#s-lc-pass-availability-content").inner_html()
            except Exception:
                availability_html = page.content()
            login_url = None
            m = re.search(r'href="([^"]+/book\?[^"]+)"', availability_html)
            if m:
                href = m.group(1)
                login_url = href if href.startswith("http") else row["source_url"].split("/passes/")[0] + href
            login_gate = None
            if login_url:
                page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1000)
                login_gate = page.locator("body").inner_text()[:1000]
            results.append(
                {
                    "library_id": row["library_id"],
                    "attraction_slug": row["attraction_slug"],
                    "source_url": row["source_url"],
                    "http_status": resp.status if resp else None,
                    "page_title": page.title(),
                    "structured_summary": (row.get("coupon") or {}).get("summary"),
                    "structured_pass_form": row["pass_form"],
                    "public_summary_match": summary_match((row.get("coupon") or {}).get("summary") or "", body),
                    "public_mentions_digital": "digital" in body.lower() or "downloadable" in body.lower(),
                    "login_gate_reached": bool(login_gate and "library card number and pin" in login_gate.lower()),
                    "body_excerpt": normalize_space(body[:500]),
                    "issue": "",
                }
            )
        browser.close()

    for rec in results:
        issues = []
        if not rec["public_summary_match"]:
            issues.append("Public page offer text does not clearly match structured summary.")
        if rec["structured_pass_form"] == "digital_email" and not rec["public_mentions_digital"]:
            issues.append("Structured pass_form says digital_email, but public page did not clearly mention digital/downloadable.")
        if rec["structured_pass_form"] != "digital_email" and rec["public_mentions_digital"]:
            issues.append("Structured pass_form is not digital_email, but public page clearly says Digital/downloadable.")
        if rec["http_status"] == 404 or "404" in (rec["page_title"] or ""):
            issues.append("source_url resolves to a 404 page.")
        if not rec["login_gate_reached"]:
            issues.append("Could not confirm the booking flow reached the card+PIN login gate.")
        rec["issue"] = " ".join(issues)

    json_path = OUT / "bpl_public_results.json"
    csv_path = OUT / "bpl_public_results.csv"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {len(results)} rows to {json_path} and {csv_path}")


if __name__ == "__main__":
    main()
