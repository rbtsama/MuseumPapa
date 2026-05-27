"""Full source_url liveness sweep (no cards, public GETs only).

Walks every UNIQUE source_url referenced by data/structured/passes.json and
records its HTTP status via the cached, TTL'd fetcher used by the build
validator (data/.cache/source_url_status.json, 72h TTL). The cache makes the
run RESUMABLE: a full 1002-URL sweep can exceed one window, but re-running
picks up where it left off and only re-checks entries older than the TTL.

Output: outputs/dead_source_urls.json — the COMPLETE list of dead links
(status >= 400), each mapped back to every (library_id, attraction_slug) that
references it (unlike the build report, which only keeps the first 8 samples).

This is the credential-free half of the audit: it never touches a library card,
so it can run as broadly as needed without tripping booking-site rate limits.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from malibbene.build.validate import build_source_url_fetcher  # noqa: E402

OUT = ROOT / "audit" / "strict_audit_20260527" / "outputs"


def main() -> None:
    passes = json.loads((ROOT / "data/structured/passes.json").read_text(encoding="utf-8"))["passes"]
    refs: dict[str, list[dict]] = defaultdict(list)
    for p in passes:
        url = p.get("source_url")
        if url:
            refs[url].append({"library_id": p.get("library_id"),
                              "attraction_slug": p.get("attraction_slug")})

    fetcher = build_source_url_fetcher()
    urls = sorted(refs)
    statuses: dict[str, int | None] = {}
    t0 = time.time()
    for i, url in enumerate(urls, 1):
        statuses[url] = fetcher(url)
        if i % 50 == 0 or i == len(urls):
            print(f"  [{i}/{len(urls)}] {time.time()-t0:.0f}s elapsed", flush=True)

    dead = []
    for url in urls:
        st = statuses[url]
        if st is not None and st >= 400:
            for ref in refs[url]:
                dead.append({**ref, "status": st, "source_url": url})

    unreachable = sorted(u for u in urls if statuses[u] is None)
    by_status: dict[str, int] = defaultdict(int)
    for url in urls:
        by_status[str(statuses[url])] += 1

    result = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "unique_urls": len(urls),
        "dead_count": len(dead),
        "status_histogram": dict(sorted(by_status.items())),
        "unreachable_urls": unreachable,  # status None = network/DNS error, not necessarily dead
        "dead": sorted(dead, key=lambda d: (d["source_url"], d["library_id"])),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dead_source_urls.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "dead"}, indent=2, ensure_ascii=False))
    print(f"Wrote {len(dead)} dead-link rows to {OUT/'dead_source_urls.json'}")


if __name__ == "__main__":
    main()
