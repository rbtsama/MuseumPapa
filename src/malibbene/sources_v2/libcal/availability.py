"""LibCal availability — calls /pass/availability/institution JSON endpoint."""
from __future__ import annotations

import json
from pathlib import Path

from malibbene.common.http import fetch


def build_availability_url(libcal_subdomain: str, pass_id: str, date: str) -> str:
    return (
        f"https://{libcal_subdomain}.libcal.com/pass/availability/institution"
        f"?museum={pass_id}&date={date}"
    )


def parse_availability_json(data: dict) -> list[dict]:
    out: list[dict] = []
    for status in ("available", "booked", "unavailable"):
        for entry in data.get(status, []) or []:
            out.append({"date": entry["date"], "status": status})
    return out


def scrape_availability(
    library_id: str,
    libcal_subdomain: str,
    pass_id: str,
    attraction_slug: str,
    start_date: str,
    raw_root: Path,
) -> dict:
    url = build_availability_url(libcal_subdomain, pass_id, start_date)
    body = fetch(url)
    data = json.loads(body)
    days = parse_availability_json(data)
    out = raw_root / "libcal" / "availability" / library_id / f"{attraction_slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "library_id": library_id,
                "pass_id": pass_id,
                "attraction_slug": attraction_slug,
                "days": days,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"n_days": len(days)}
