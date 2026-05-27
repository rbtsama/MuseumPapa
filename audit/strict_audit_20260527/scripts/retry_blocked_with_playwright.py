from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "audit" / "strict_audit_20260527" / "outputs"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

CASES = [
    {
        "library_id": "framingham",
        "attraction_rawslug": "new-england-botanic-garden-at-tower-hill",
        "url": "https://framinghamlibrary.assabetinteractive.com/museum-passes/by-date/2026-may/30/new-england-botanic-garden-at-tower-hill/",
        "barcode": "21155002861208",
        "card_label": "somerville",
    },
    {
        "library_id": "newton",
        "attraction_rawslug": "larz-anderson-auto-museum",
        "url": "https://newtonfreelibrary.assabetinteractive.com/museum-passes/by-date/2026-may/30/larz-anderson-auto-museum/",
        "barcode": "21155002861208",
        "card_label": "somerville",
    },
    {
        "library_id": "belmont",
        "attraction_rawslug": "isabella-stewart-gardner-museum",
        "url": "https://belmontpubliclibrary.assabetinteractive.com/museum-passes/by-date/2026-may/31/isabella-stewart-gardner-museum/",
        "barcode": "21155002861208",
        "card_label": "somerville",
    },
    {
        "library_id": "everett",
        "attraction_rawslug": "massachusetts-state-parks-department-of-conservation-and-recreation",
        "url": "https://everettpubliclibraries.assabetinteractive.com/museum-passes/by-date/2026-may/31/massachusetts-state-parks-department-of-conservation-and-recreation/",
        "barcode": "21392000916862",
        "card_label": "wakefield",
    },
    {
        "library_id": "everett",
        "attraction_rawslug": "massachusetts-state-parks-department-of-conservation-and-recreation",
        "url": "https://everettpubliclibraries.assabetinteractive.com/museum-passes/by-date/2026-may/31/massachusetts-state-parks-department-of-conservation-and-recreation/",
        "barcode": "21995000908588",
        "card_label": "reading",
    },
]


def classify(text: str) -> str:
    t = text.lower()
    if "does not appear to be valid" in t or "blocked from making this type of reservation" in t:
        return "rejected_resident"
    if "first name *" in t or "reserver information" in t or "available pass" in t:
        return "accepted"
    if "please check the following" in t and "library card" in t:
        return "format_error"
    return "unknown"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for case in CASES:
            context = browser.new_context(
                viewport={"width": 1366, "height": 2200},
                locale="en-US",
                user_agent=UA,
            )
            page = context.new_page()
            page.goto(case["url"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            inp = page.locator('input[name="reservationlibrarycard"]')
            if inp.count():
                inp.fill("")
                page.wait_for_timeout(400)
                inp.type(case["barcode"], delay=100)
                page.wait_for_timeout(1200)
                page.locator('input[name="save"], input[type="submit"], button[type="submit"]').first.click()
                page.wait_for_timeout(4000)
            text = page.locator("body").inner_text()
            rows.append(
                {
                    "library_id": case["library_id"],
                    "attraction_rawslug": case["attraction_rawslug"],
                    "card_label": case["card_label"],
                    "url": case["url"],
                    "final_url": page.url,
                    "verdict": classify(text),
                    "body_excerpt": " | ".join(text.splitlines())[:2000],
                }
            )
            context.close()
        browser.close()
    out_path = OUT / "playwright_retry_results.json"
    out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
