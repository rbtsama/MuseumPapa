# Plan 1 — Data Augmentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把前端 v0.1 必需的 3 类新数据补齐:景点 + 图书馆 lat/lon、景点 original price、景点 hero image。产物落到 `data/structured/geo.json`、`data/raw/library_addresses/`、`data/raw/attraction_prices/`、`data/static/images/`。

**Architecture:** 增加 1 个 `common/geocode.py` 工具 + 3 个 scraper(`sources/libraries/addresses.py` fetch-only、`sources/attractions/prices.py` fetch-only、`sources/attractions/images.py`)+ 5 个 CLI 入口脚本。所有 scraper 走现有 `common/http.fetch` 模式(stdlib urllib + 24h cache,失败可升级 `render_js=True` 用 Playwright)。**LLM 提取通过 subagent dispatch 完成**(不调 Anthropic API、不放 API key、对齐用户铁律 [[feedback_no_api_call]]):Python fetcher 只负责把页面 HTML 落盘到 `_pages/`,extraction subagent 读 HTML → 产出结构化 JSON。

**Tech Stack:** Python 3.11+ / stdlib urllib / Playwright(可选,JS 页面)/ Subagent dispatch(extraction)/ OSM Nominatim(geocoding,免费,1 req/sec 限流)/ pytest

---

## 0. 前置准备(零任务,只读)

**输入文件**(已就绪):
- `data/raw/{assabet,libcal,museumkey}/index/*.json`
- `config/library_seeds.json`(59 馆,带 `domain` 但无 street address)
- `config/platform_pass_ids/{bpl,libcal,museumkey}.json`

**输出**(本 plan 产出):
- `data/structured/_tmp_attractions_index.json` — 临时景点索引(`_tmp_` 前缀按 [[feedback_temp_files]] 不入 git)
- `data/structured/geo.json` — `{ "attractions": {<slug>: {lat, lon}}, "libraries": {<lib_id>: {lat, lon}} }`
- `data/raw/library_addresses/_pages/<lib_id>.html` — 主站抓到的原始 HTML(供 extraction subagent 读)
- `data/raw/library_addresses/<lib_id>.json` — extraction subagent 产出 `{street, city, state, zip, status}`
- `data/raw/attraction_prices/_pages/<slug>.html` — 景点 admission 页 HTML
- `data/raw/attraction_prices/<slug>.json` — `{adult, child, senior, student, family, free_under_age, notes, status}`
- `data/raw/attraction_images/<slug>.json` — `{og_image_url, local_path, status}`
- `data/static/images/<slug>.<ext>` — hero 图本地缓存(gitignore,体积大)
- `data/static/placeholders/<category>.svg` — fallback 占位图(入 git,小)

**新增依赖**(`pyproject.toml`):无新增运行时依赖(继续 stdlib);Playwright 是已有的 optional。

**.gitignore 追加**:
```
data/static/images/
data/.cache/
data/structured/_tmp_*
data/raw/library_addresses/_pages/
data/raw/attraction_prices/_pages/
```

---

## File Structure

```
src/malibbene/
├── common/
│   └── geocode.py                    # NEW — Nominatim wrapper + cache + haversine
└── sources/
    ├── attractions/
    │   ├── prices.py                 # NEW — fetcher only (fetches admission pages, saves HTML)
    │   └── images.py                 # NEW — og:image scraper + downloader (regex, no LLM)
    └── libraries/                    # NEW dir
        ├── __init__.py
        └── addresses.py              # NEW — fetcher only (fetches library main site, saves HTML)

scripts/
├── build_attractions_index.py        # NEW — 扫 raw/*/index/ → _tmp_attractions_index.json
├── fetch_library_pages.py            # NEW — fetcher CLI for library addresses
├── fetch_attraction_price_pages.py   # NEW — fetcher CLI for attraction admission pages
├── scrape_attraction_images.py       # NEW — og:image scraper + downloader
└── geocode_all.py                    # NEW — 读上面产物,跑 Nominatim,写 geo.json

tests/
├── test_geocode.py                   # NEW
├── test_build_attractions_index.py   # NEW
├── test_library_addresses_fetcher.py # NEW
├── test_attraction_prices_fetcher.py # NEW
└── test_attraction_images.py         # NEW
```

**Extraction subagent dispatch**(不是文件,是执行流程):
- 在 Task 4 Step 4.6 / Task 6 Step 6.6,主 controller 派发一个 extraction subagent,指令为"读 `_pages/*.html`,按 schema 提取 → 写 `<id>.json`"。
- 不需要额外代码或依赖,Claude(subagent)读 HTML 后直接 Write 工具落盘。

---

## Task 1 — Bootstrap: build temporary attractions index

**Files:**
- Create: `scripts/build_attractions_index.py`
- Create: `tests/test_build_attractions_index.py`

- [ ] **Step 1.1: Write the failing test**

Create `tests/test_build_attractions_index.py`:

```python
"""Test extracting unique attractions across all platforms."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


@pytest.fixture
def fake_raw_root(tmp_path):
    assabet = tmp_path / "raw" / "assabet" / "index"
    assabet.mkdir(parents=True)
    (assabet / "wakefield.json").write_text(json.dumps({
        "passes": [
            {"slug": "mos", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/visit",
             "categories": ["Science", "Family"], "status": "ok"},
            {"slug": "neaq", "museum_name": "New England Aquarium",
             "address": "1 Central Wharf, Boston, MA 02110",
             "website": "https://www.neaq.org/", "categories": ["Ocean"], "status": "ok"},
        ],
    }), encoding="utf-8")
    (assabet / "reading.json").write_text(json.dumps({
        "passes": [
            {"slug": "mos", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/visit",
             "categories": ["Science"], "status": "ok"},
        ],
    }), encoding="utf-8")
    return tmp_path


def test_build_attractions_index_dedupes_across_libraries(fake_raw_root):
    from scripts.build_attractions_index import build_index

    idx = build_index(fake_raw_root / "raw")

    assert set(idx.keys()) == {"mos", "neaq"}
    assert idx["mos"]["museum_name"] == "Museum of Science"
    assert idx["mos"]["website"] == "https://www.mos.org/visit"
    assert set(idx["mos"]["sources"]) == {"wakefield", "reading"}
    assert idx["neaq"]["sources"] == ["wakefield"]


def test_build_attractions_index_handles_libcal_via_platform_map(fake_raw_root):
    libcal = fake_raw_root / "raw" / "libcal" / "index"
    libcal.mkdir(parents=True)
    (libcal / "bpl.json").write_text(json.dumps({
        "passes": [
            {"libcal_pass_id": "12345", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/visit", "status": "ok"},
        ],
    }), encoding="utf-8")
    cfg = fake_raw_root / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "libcal.json").write_text(json.dumps({"bpl": {"12345": "mos"}}), encoding="utf-8")

    from scripts.build_attractions_index import build_index

    idx = build_index(fake_raw_root / "raw", config_root=fake_raw_root / "config")
    assert "mos" in idx
    assert "bpl" in idx["mos"]["sources"]


def test_build_attractions_index_skips_failed_passes(fake_raw_root):
    assabet = fake_raw_root / "raw" / "assabet" / "index"
    (assabet / "bad.json").write_text(json.dumps({
        "passes": [
            {"slug": "ghost", "museum_name": "Ghost", "status": "failed:parse_error"},
        ],
    }), encoding="utf-8")

    from scripts.build_attractions_index import build_index
    idx = build_index(fake_raw_root / "raw")
    assert "ghost" not in idx
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `pytest tests/test_build_attractions_index.py -v`
Expected: FAIL with `ModuleNotFoundError: scripts.build_attractions_index`

- [ ] **Step 1.3: Write minimal implementation**

Create `scripts/build_attractions_index.py`:

```python
"""Build a temporary canonical attractions index from raw/*/index/*.json.

Output: data/structured/_tmp_attractions_index.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_platform_map(config_root: Path, platform: str) -> dict[str, dict[str, str]]:
    p = config_root / "platform_pass_ids" / f"{platform}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _canonical_slug(pass_obj: dict, lib_id: str, platform: str, pmap: dict) -> str | None:
    if platform == "assabet":
        return pass_obj.get("slug")
    if platform == "libcal":
        sid = pass_obj.get("libcal_pass_id") or pass_obj.get("pass_id")
        return pmap.get(lib_id, {}).get(str(sid))
    if platform == "museumkey":
        sid = pass_obj.get("museum_id") or pass_obj.get("pass_id")
        return pmap.get(lib_id, {}).get(str(sid))
    return None


def build_index(raw_root: Path, config_root: Path | None = None) -> dict:
    if config_root is None:
        config_root = REPO / "config"

    out: dict[str, dict] = {}
    for platform in ("assabet", "libcal", "museumkey"):
        pmap = _load_platform_map(config_root, platform)
        platform_dir = raw_root / platform / "index"
        if not platform_dir.exists():
            continue
        for lib_file in sorted(platform_dir.glob("*.json")):
            lib_id = lib_file.stem
            data = json.loads(lib_file.read_text(encoding="utf-8"))
            for p in data.get("passes", []):
                if str(p.get("status", "")).startswith("failed"):
                    continue
                slug = _canonical_slug(p, lib_id, platform, pmap)
                if not slug:
                    continue
                entry = out.setdefault(slug, {
                    "slug": slug,
                    "museum_name": p.get("museum_name", ""),
                    "address": p.get("address", ""),
                    "website": p.get("website", ""),
                    "categories": list(p.get("categories", [])),
                    "sources": [],
                })
                if lib_id not in entry["sources"]:
                    entry["sources"].append(lib_id)
                for fld in ("museum_name", "address", "website"):
                    if not entry[fld] and p.get(fld):
                        entry[fld] = p[fld]
                for c in p.get("categories", []):
                    if c not in entry["categories"]:
                        entry["categories"].append(c)
    return out


def main() -> int:
    raw_root = REPO / "data" / "raw"
    idx = build_index(raw_root)
    out_path = REPO / "data" / "structured" / "_tmp_attractions_index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(idx)} attractions to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `pytest tests/test_build_attractions_index.py -v`
Expected: 3 passed

- [ ] **Step 1.5: Run for real on real raw data**

Run: `python scripts/build_attractions_index.py`
Expected output: `Wrote ~100-110 attractions to .../data/structured/_tmp_attractions_index.json`

- [ ] **Step 1.6: Spot check the output**

Run:
```bash
python -c "import json; d=json.load(open('data/structured/_tmp_attractions_index.json',encoding='utf-8')); print(len(d), 'attractions'); k=next(iter(d)); print('sample:', d[k])"
```
Expected: prints count and one full entry with `slug`, `museum_name`, `address`, `website`, `sources` ≥1.

- [ ] **Step 1.7: Update .gitignore**

Edit `.gitignore` to add:
```
data/static/images/
data/structured/_tmp_*
data/raw/library_addresses/_pages/
data/raw/attraction_prices/_pages/
```
(`data/.cache/` should already be there from existing project.)

- [ ] **Step 1.8: Commit**

```bash
git add scripts/build_attractions_index.py tests/test_build_attractions_index.py .gitignore
git commit -m "feat(data): build temporary canonical attractions index across platforms"
```

---

## Task 2 — Geocoding utility (Nominatim wrapper)

**Files:**
- Create: `src/malibbene/common/geocode.py`
- Create: `tests/test_geocode.py`

- [ ] **Step 2.1: Write the failing test**

Create `tests/test_geocode.py`:

```python
"""Test Nominatim geocoding wrapper: cache + rate limit + fallback."""
import json
from unittest.mock import patch


def test_geocode_cache_hit(tmp_path):
    from malibbene.common import geocode

    cache_path = tmp_path / "geocache.json"
    cache_path.write_text(json.dumps({
        "1 Science Park, Boston, MA 02114": {"lat": 42.3676, "lon": -71.0712, "ok": True}
    }), encoding="utf-8")

    result = geocode.geocode("1 Science Park, Boston, MA 02114", cache_path=cache_path)
    assert result == {"lat": 42.3676, "lon": -71.0712, "ok": True}


def test_geocode_hits_nominatim_on_cache_miss(tmp_path):
    from malibbene.common import geocode

    cache_path = tmp_path / "geocache.json"
    fake_response = json.dumps([{"lat": "42.3676", "lon": "-71.0712"}]).encode()

    with patch("malibbene.common.geocode._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_response
        result = geocode.geocode("Wakefield, MA", cache_path=cache_path)

    assert result["ok"] is True
    assert abs(result["lat"] - 42.3676) < 1e-4
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert "Wakefield, MA" in cached


def test_geocode_records_failure(tmp_path):
    from malibbene.common import geocode

    cache_path = tmp_path / "geocache.json"
    with patch("malibbene.common.geocode._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"[]"
        result = geocode.geocode("nonexistent place xyz", cache_path=cache_path)

    assert result["ok"] is False
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached["nonexistent place xyz"]["ok"] is False


def test_geocode_haversine_distance():
    from malibbene.common.geocode import haversine_miles
    # Boston to Wakefield, MA ~12mi straight line
    d = haversine_miles(42.3601, -71.0589, 42.5065, -71.0759)
    assert 9 < d < 13
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `pytest tests/test_geocode.py -v`
Expected: FAIL with `ModuleNotFoundError: malibbene.common.geocode`

- [ ] **Step 2.3: Write minimal implementation**

Create `src/malibbene/common/geocode.py`:

```python
"""Nominatim (OSM) geocoding wrapper: cache + rate limit + haversine.

Nominatim usage policy: max 1 req/sec, required User-Agent identifying app.
See https://operations.osmfoundation.org/policies/nominatim/
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CACHE = REPO / "data" / ".cache" / "geocode.json"
UA = "MuseumPass-MA-Geocoder/0.1 (https://github.com/rbtsama)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_LAST_REQUEST_AT = 0.0


def _urlopen(req, timeout=30):
    return urllib.request.urlopen(req, timeout=timeout)


def _rate_limit():
    global _LAST_REQUEST_AT
    elapsed = time.time() - _LAST_REQUEST_AT
    if elapsed < 1.05:
        time.sleep(1.05 - elapsed)
    _LAST_REQUEST_AT = time.time()


def _load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text(encoding="utf-8"))


def _save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def geocode(query: str, *, cache_path: Path = DEFAULT_CACHE) -> dict:
    """Return {lat, lon, ok} for a free-form address.

    On failure: returns {ok: False, error: <reason>}. Failure also cached so
    we don't re-query unsolvable addresses.
    """
    cache = _load_cache(cache_path)
    if query in cache:
        return cache[query]

    _rate_limit()
    qs = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    req = urllib.request.Request(f"{NOMINATIM_URL}?{qs}", headers={"User-Agent": UA})
    try:
        with _urlopen(req, timeout=30) as resp:
            body = resp.read()
        results = json.loads(body)
        if not results:
            entry = {"ok": False, "error": "no_results"}
        else:
            entry = {"ok": True, "lat": float(results[0]["lat"]), "lon": float(results[0]["lon"])}
    except Exception as e:
        entry = {"ok": False, "error": str(e)}

    cache[query] = entry
    _save_cache(cache_path, cache)
    return entry


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in miles."""
    R_MILES = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R_MILES * math.asin(math.sqrt(a))
```

- [ ] **Step 2.4: Run test to verify it passes**

Run: `pytest tests/test_geocode.py -v`
Expected: 4 passed

- [ ] **Step 2.5: Sanity check with one real query**

Run: `python -c "from malibbene.common.geocode import geocode; print(geocode('1 Science Park, Boston, MA'))"`
Expected: `{'ok': True, 'lat': 42.36..., 'lon': -71.07...}`

- [ ] **Step 2.6: Commit**

```bash
git add src/malibbene/common/geocode.py tests/test_geocode.py
git commit -m "feat(geocode): Nominatim wrapper with cache, rate limit, haversine"
```

---

## Task 3 — Library address fetcher (Python-only, no LLM)

**Why:** `config/library_seeds.json` 只有 domain,无 street address。先 fetch 每馆主站常见路径,落 HTML;extraction 由 Task 4 的 subagent dispatch 完成。

**Files:**
- Create: `src/malibbene/sources/libraries/__init__.py`
- Create: `src/malibbene/sources/libraries/addresses.py`
- Create: `scripts/fetch_library_pages.py`
- Create: `tests/test_library_addresses_fetcher.py`

- [ ] **Step 3.1: Write the failing test**

Create `tests/test_library_addresses_fetcher.py`:

```python
"""Test the library page fetcher (HTML saving, not extraction)."""
from unittest.mock import patch


def test_fetch_one_saves_html_to_disk(tmp_path):
    from malibbene.sources.libraries.addresses import fetch_one

    fake_html = "<html><body>Visit us at 60 Main Street, Wakefield, MA 01880.</body></html>"
    with patch("malibbene.sources.libraries.addresses.fetch", return_value=fake_html):
        result = fetch_one("wakefield", "https://wakefieldlibrary.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["lib_id"] == "wakefield"
    # HTML saved
    p = tmp_path / "wakefield.html"
    assert p.exists()
    assert "60 Main Street" in p.read_text(encoding="utf-8")


def test_fetch_one_tries_multiple_paths(tmp_path):
    """If /visit 404s, fall back to /hours, /contact."""
    from malibbene.sources.libraries.addresses import fetch_one

    calls = []
    def fake_fetch(url, **kw):
        calls.append(url)
        if "/visit" in url or "/hours" in url:
            raise Exception("404")
        return "<html>address content</html>"

    with patch("malibbene.sources.libraries.addresses.fetch", side_effect=fake_fetch):
        result = fetch_one("wakefield", "https://wakefieldlibrary.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    # tried at least 3 paths before success
    assert len(calls) >= 3


def test_fetch_one_marks_failed_when_all_paths_fail(tmp_path):
    from malibbene.sources.libraries.addresses import fetch_one

    with patch("malibbene.sources.libraries.addresses.fetch", side_effect=Exception("network")):
        result = fetch_one("wakefield", "https://wakefieldlibrary.org/", out_dir=tmp_path)

    assert result["status"].startswith("failed")
    assert not (tmp_path / "wakefield.html").exists()
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `pytest tests/test_library_addresses_fetcher.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3.3: Write implementation**

Create `src/malibbene/sources/libraries/__init__.py`:

```python
"""Library-side data scrapers (addresses, policies)."""
```

Create `src/malibbene/sources/libraries/addresses.py`:

```python
"""Library main-site page fetcher.

Strategy: try common URL paths (/visit, /hours, /contact, /about, /), save the
first non-error response as raw HTML. Extraction (street/city/state/zip) is
done downstream by a subagent reading the saved HTML.
"""
from __future__ import annotations

from pathlib import Path

from malibbene.common.http import fetch

CANDIDATE_PATHS = ["/visit", "/hours", "/contact", "/about", "/locations", "/"]


def fetch_one(lib_id: str, base_url: str, *, out_dir: Path) -> dict:
    """Fetch a library's main site; save first OK response to out_dir/<lib_id>.html.

    Returns a status dict (does NOT extract address — that's a later step).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    base = base_url.rstrip("/")
    last_error = "no_path_returned_200"
    for path in CANDIDATE_PATHS:
        url = base + path
        try:
            html = fetch(url)
        except Exception as e:
            last_error = f"fetch_failed:{e}"
            continue
        if len(html) < 200:
            last_error = "html_too_short"
            continue
        out_path = out_dir / f"{lib_id}.html"
        out_path.write_text(html, encoding="utf-8")
        return {"lib_id": lib_id, "status": "ok", "source_url": url, "bytes": len(html)}
    return {"lib_id": lib_id, "status": f"failed:{last_error}"}
```

Create `scripts/fetch_library_pages.py`:

```python
"""Fetch the main-site HTML page for each of 59 libraries; write data/raw/library_addresses/_pages/<lib_id>.html."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.libraries.addresses import fetch_one


def derive_base_url(seed: dict) -> str | None:
    """Prefer card_page (the library's own site); skip if only platform domain available."""
    if seed.get("card_page"):
        p = urlparse(seed["card_page"])
        return f"{p.scheme}://{p.netloc}/"
    return None


def main() -> int:
    seeds = json.loads((REPO / "config" / "library_seeds.json").read_text(encoding="utf-8"))
    pages_dir = REPO / "data" / "raw" / "library_addresses" / "_pages"
    fetch_log_path = REPO / "data" / "raw" / "library_addresses" / "_fetch_log.json"
    pages_dir.mkdir(parents=True, exist_ok=True)

    log = {}
    ok = 0
    total = 0
    for seed in seeds["libraries"]:
        total += 1
        base = derive_base_url(seed)
        if not base:
            result = {"lib_id": seed["id"], "status": "failed:no_base_url"}
        else:
            print(f"[{total}/{len(seeds['libraries'])}] {seed['id']} ← {base}")
            result = fetch_one(seed["id"], base, out_dir=pages_dir)
        log[seed["id"]] = result
        if result["status"] == "ok":
            ok += 1

    fetch_log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Done. ok={ok}/{total} = {ok/total:.1%}")
    return 0 if ok / total >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3.4: Run tests to verify they pass**

Run: `pytest tests/test_library_addresses_fetcher.py -v`
Expected: 3 passed

- [ ] **Step 3.5: Run on real data, verify ok_ratio ≥ 80%**

Run: `python scripts/fetch_library_pages.py`
Expected: `Done. ok=X/59 = N%` with N ≥ 80. Check `data/raw/library_addresses/_fetch_log.json` for any failures.

**If ok_ratio < 80%:** STOP and report. Don't paper over — inspect the failing libraries' actual sites and adjust `CANDIDATE_PATHS` or escalate to the controller.

- [ ] **Step 3.6: Commit**

```bash
git add src/malibbene/sources/libraries/ scripts/fetch_library_pages.py tests/test_library_addresses_fetcher.py data/raw/library_addresses/_fetch_log.json
git commit -m "feat(libraries): fetcher saves HTML for 59 library main sites"
```

---

## Task 4 — Library address extraction (dispatch subagent)

**Why:** Task 3 拿到了 59 个馆的 HTML,本任务把地址结构化抽出来。**通过 subagent dispatch 完成,不调 API**。

**Files:**
- Output: `data/raw/library_addresses/<lib_id>.json` × 59
- Output schema (per file): `{lib_id, status, street, city, state, zip, source_url}`

- [ ] **Step 4.1: Verify input is ready**

Run:
```bash
python -c "
from pathlib import Path
pages = list(Path('data/raw/library_addresses/_pages').glob('*.html'))
print(f'{len(pages)} HTML pages ready for extraction')
"
```
Expected: 50+ pages.

- [ ] **Step 4.2: Dispatch extraction subagent**

Controller (the agent running this plan) dispatches a `general-purpose` subagent with the following prompt:

```
You are an extraction agent. Read the HTML pages in
`F:\pj\NorthShore Kids Events\data\raw\library_addresses\_pages\*.html`
and extract each library's mailing address.

For each `<lib_id>.html` in that directory:

1. Read the file (use Read tool).
2. Identify the library's MAIN BRANCH street address from the HTML
   text. Ignore branch listings — pick the main branch if multiple are listed.
3. Output a JSON object with this exact shape:
   {
     "lib_id": "<same as filename without .html>",
     "status": "ok" or "failed:<reason>",
     "street": "<e.g., 60 Main Street>" or null,
     "city": "<e.g., Wakefield>" or null,
     "state": "MA",
     "zip": "<5-digit>" or null,
     "source_url": "<from data/raw/library_addresses/_fetch_log.json[lib_id].source_url>"
   }
4. Write each result to `data/raw/library_addresses/<lib_id>.json`
   using the Write tool.

Process libraries in batches of 10 to manage your context window. Within
each batch, read 10 HTMLs, produce 10 JSONs, write them all.

If a page has no extractable address (rare), set status="failed:no_address_found"
and leave street/city/zip as null.

When done, run:
  python -c "
import json, glob
files = glob.glob('data/raw/library_addresses/*.json')
files = [f for f in files if not f.endswith('_fetch_log.json')]
ok = sum(1 for f in files if json.load(open(f, encoding='utf-8')).get('status') == 'ok')
print(f'extracted: {ok}/{len(files)} ok_ratio={ok/len(files):.1%}')
"

Report:
- How many libraries you processed
- ok_ratio (must be ≥ 80% — if not, report which libraries failed and why)
- Any pages that had unclear/missing addresses
```

- [ ] **Step 4.3: Verify extraction quality**

Spot check 3 JSONs manually:
```bash
python -c "
import json
for lid in ['wakefield', 'reading', 'bpl']:
    p = f'data/raw/library_addresses/{lid}.json'
    try:
        print(lid, json.load(open(p, encoding='utf-8')))
    except FileNotFoundError:
        print(lid, 'MISSING')
"
```
Expected: 3 records with `status=ok`, plausible street/city/zip.

Also verify ok_ratio: subagent should have reported ≥80%. If <80%, dispatch a retry subagent with specific failing lib_ids.

- [ ] **Step 4.4: Commit**

```bash
git add data/raw/library_addresses/*.json
git commit -m "data: extract library street addresses from fetched HTML (subagent)"
```

(Don't commit `_pages/` — gitignored.)

---

## Task 5 — Geocode attractions + libraries (write geo.json)

**Files:**
- Create: `scripts/geocode_all.py`

- [ ] **Step 5.1: Write the failing test (append to test_geocode.py)**

Append to `tests/test_geocode.py`:

```python
def test_geocode_all_writes_geojson(tmp_path, monkeypatch):
    """End-to-end: read attractions index + library addresses, write geo.json."""
    import json
    import sys
    from pathlib import Path

    structured = tmp_path / "data" / "structured"
    structured.mkdir(parents=True)
    (structured / "_tmp_attractions_index.json").write_text(json.dumps({
        "mos": {"address": "1 Science Park, Boston, MA 02114"},
    }), encoding="utf-8")

    libaddr = tmp_path / "data" / "raw" / "library_addresses"
    libaddr.mkdir(parents=True)
    (libaddr / "wakefield.json").write_text(json.dumps({
        "lib_id": "wakefield", "status": "ok",
        "street": "60 Main Street", "city": "Wakefield", "state": "MA", "zip": "01880",
    }), encoding="utf-8")

    REPO = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(REPO))

    from malibbene.common import geocode as gmod

    def fake_geocode(query, **kw):
        return {"ok": True, "lat": 42.0 + len(query) * 0.001, "lon": -71.0}

    monkeypatch.setattr(gmod, "geocode", fake_geocode)
    import scripts.geocode_all as ga
    monkeypatch.setattr(ga, "REPO", tmp_path)
    ga.main()

    out = json.loads((tmp_path / "data" / "structured" / "geo.json").read_text(encoding="utf-8"))
    assert "mos" in out["attractions"]
    assert "wakefield" in out["libraries"]
    assert out["attractions"]["mos"]["ok"] is True
```

- [ ] **Step 5.2: Run test to verify it fails**

Run: `pytest tests/test_geocode.py::test_geocode_all_writes_geojson -v`
Expected: FAIL `ModuleNotFoundError: scripts.geocode_all`

- [ ] **Step 5.3: Write implementation**

Create `scripts/geocode_all.py`:

```python
"""Geocode all attractions + libraries; write data/structured/geo.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.common import geocode as gmod


def _attraction_query(entry: dict) -> str | None:
    addr = (entry.get("address") or "").strip()
    return addr or None


def _library_query(addr_record: dict) -> str | None:
    if addr_record.get("status") != "ok":
        return None
    parts = [addr_record.get("street"), addr_record.get("city"),
             addr_record.get("state"), addr_record.get("zip")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def main() -> int:
    structured = REPO / "data" / "structured"
    idx_path = structured / "_tmp_attractions_index.json"
    if not idx_path.exists():
        print("ERROR: run scripts/build_attractions_index.py first")
        return 1

    attractions_idx = json.loads(idx_path.read_text(encoding="utf-8"))
    libaddr_dir = REPO / "data" / "raw" / "library_addresses"

    out = {"attractions": {}, "libraries": {}}

    n_ok = 0
    for slug, entry in attractions_idx.items():
        q = _attraction_query(entry)
        if not q:
            out["attractions"][slug] = {"ok": False, "error": "no_address"}
            continue
        r = gmod.geocode(q)
        out["attractions"][slug] = r
        if r.get("ok"):
            n_ok += 1
    print(f"Attractions: {n_ok}/{len(attractions_idx)} geocoded")

    n_ok = 0
    n_total = 0
    if libaddr_dir.exists():
        for f in sorted(libaddr_dir.glob("*.json")):
            if f.name.startswith("_"):
                continue  # skip _fetch_log.json
            n_total += 1
            rec = json.loads(f.read_text(encoding="utf-8"))
            q = _library_query(rec)
            if not q:
                out["libraries"][f.stem] = {"ok": False, "error": "no_address"}
                continue
            r = gmod.geocode(q)
            out["libraries"][f.stem] = r
            if r.get("ok"):
                n_ok += 1
    print(f"Libraries: {n_ok}/{n_total} geocoded")

    (structured / "geo.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {structured / 'geo.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5.4: Run test to verify it passes**

Run: `pytest tests/test_geocode.py -v`
Expected: 5 passed

- [ ] **Step 5.5: Run for real**

Run: `python scripts/geocode_all.py`
Expected: prints `Attractions: X/108 geocoded` (X ≥ 90), `Libraries: Y/59 geocoded` (Y ≥ Task 4 ok count).
Runtime: ~3 minutes (1 sec/request × ~170 unique addresses; cache hits skip).

- [ ] **Step 5.6: Spot check distance calculation**

```bash
python -c "
import json
from malibbene.common.geocode import haversine_miles
g = json.load(open('data/structured/geo.json',encoding='utf-8'))
mos = g['attractions'].get('museum-of-science')
wk = g['libraries'].get('wakefield')
print('MOS:', mos)
print('Wakefield:', wk)
if mos and wk and mos.get('ok') and wk.get('ok'):
    d = haversine_miles(mos['lat'], mos['lon'], wk['lat'], wk['lon'])
    print(f'MOS <-> Wakefield Library: {d:.1f} mi')
"
```
Expected: ~10-12 mi.

- [ ] **Step 5.7: Commit**

```bash
git add scripts/geocode_all.py tests/test_geocode.py data/structured/geo.json
git commit -m "feat(geocode): batch geocode attractions + libraries to geo.json"
```

---

## Task 6 — Attraction admission page fetcher (Python-only)

**Files:**
- Create: `src/malibbene/sources/attractions/prices.py`
- Create: `scripts/fetch_attraction_price_pages.py`
- Create: `tests/test_attraction_prices_fetcher.py`

- [ ] **Step 6.1: Write the failing test**

Create `tests/test_attraction_prices_fetcher.py`:

```python
from unittest.mock import patch


def test_fetch_one_saves_admission_html(tmp_path):
    from malibbene.sources.attractions.prices import fetch_one

    html = "<p>Adult $30, Child (3-11) $25. Members free.</p>" + "x" * 1000  # >200 chars
    with patch("malibbene.sources.attractions.prices.fetch", return_value=html):
        result = fetch_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    p = tmp_path / "mos.html"
    assert p.exists()
    assert "Adult $30" in p.read_text(encoding="utf-8")


def test_fetch_one_tries_multiple_paths(tmp_path):
    from malibbene.sources.attractions.prices import fetch_one

    calls = []
    def fake_fetch(url, **kw):
        calls.append(url)
        if "/admission" in url or "/tickets" in url:
            raise Exception("404")
        return "<p>Adult $30</p>" + "x" * 1000

    with patch("malibbene.sources.attractions.prices.fetch", side_effect=fake_fetch):
        result = fetch_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    assert len(calls) >= 3


def test_fetch_one_marks_failed_when_all_paths_fail(tmp_path):
    from malibbene.sources.attractions.prices import fetch_one

    with patch("malibbene.sources.attractions.prices.fetch", side_effect=Exception("502")):
        result = fetch_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"].startswith("failed")
```

- [ ] **Step 6.2: Run test to verify it fails**

Run: `pytest tests/test_attraction_prices_fetcher.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 6.3: Write implementation**

Create `src/malibbene/sources/attractions/prices.py`:

```python
"""Attraction admission page fetcher.

Tries common URL paths (/admission, /tickets, /visit, ...), saves first non-trivial
response as HTML. Extraction (adult/child/senior prices) is done downstream by a
subagent reading the saved HTML.

Falls back to Playwright if static fetch returns a near-empty body.
"""
from __future__ import annotations

from pathlib import Path

from malibbene.common.http import fetch

CANDIDATE_PATHS = [
    "/admission", "/tickets", "/visit/admission", "/visit/tickets",
    "/plan-your-visit", "/visit", "/hours-admission", "/hours", "/",
]


def fetch_one(slug: str, base_url: str, *, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = base_url.rstrip("/")
    last_error = "no_path_returned_useful_body"
    for path in CANDIDATE_PATHS:
        url = base + path
        try:
            html = fetch(url)
        except Exception as e:
            last_error = f"fetch_failed:{e}"
            continue
        if len(html) < 500:
            # Try JS-rendered fallback
            try:
                html = fetch(url, render_js=True, force=True)
            except Exception as e:
                last_error = f"render_js_failed:{e}"
                continue
            if len(html) < 500:
                last_error = "html_too_short_even_with_js"
                continue
        out_path = out_dir / f"{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        return {"slug": slug, "status": "ok", "source_url": url, "bytes": len(html)}
    return {"slug": slug, "status": f"failed:{last_error}"}
```

Create `scripts/fetch_attraction_price_pages.py`:

```python
"""Fetch admission/tickets page HTML for all attractions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.attractions.prices import fetch_one


def main() -> int:
    idx_path = REPO / "data" / "structured" / "_tmp_attractions_index.json"
    if not idx_path.exists():
        print("ERROR: run scripts/build_attractions_index.py first")
        return 1
    idx = json.loads(idx_path.read_text(encoding="utf-8"))

    pages_dir = REPO / "data" / "raw" / "attraction_prices" / "_pages"
    log_path = REPO / "data" / "raw" / "attraction_prices" / "_fetch_log.json"
    pages_dir.mkdir(parents=True, exist_ok=True)

    log = {}
    ok = 0
    total = 0
    for slug, entry in idx.items():
        total += 1
        # Resume: skip if already fetched
        if (pages_dir / f"{slug}.html").exists():
            log[slug] = {"slug": slug, "status": "ok_resumed"}
            ok += 1
            continue
        website = entry.get("website") or ""
        if not website.startswith("http"):
            result = {"slug": slug, "status": "failed:no_website"}
        else:
            print(f"[{total}/{len(idx)}] {slug} ← {website}")
            result = fetch_one(slug, website, out_dir=pages_dir)
        log[slug] = result
        if result["status"] == "ok":
            ok += 1

    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Done. ok={ok}/{total} = {ok/total:.1%}")
    return 0 if ok / total >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6.4: Run tests to verify they pass**

Run: `pytest tests/test_attraction_prices_fetcher.py -v`
Expected: 3 passed

- [ ] **Step 6.5: Run on real data**

Run: `python scripts/fetch_attraction_price_pages.py`
Expected: `Done. ok=X/108 = N%` with N ≥ 80. Runtime: ~10-30 min (Playwright slows it).

If <80%, STOP and report.

- [ ] **Step 6.6: Commit**

```bash
git add src/malibbene/sources/attractions/prices.py scripts/fetch_attraction_price_pages.py tests/test_attraction_prices_fetcher.py data/raw/attraction_prices/_fetch_log.json
git commit -m "feat(attractions): fetcher saves admission page HTML for all attractions"
```

---

## Task 7 — Attraction price extraction (dispatch subagent)

**Why:** Task 6 saved HTML; this task extracts structured prices via subagent dispatch (no API).

- [ ] **Step 7.1: Verify input is ready**

```bash
python -c "
from pathlib import Path
pages = list(Path('data/raw/attraction_prices/_pages').glob('*.html'))
print(f'{len(pages)} admission HTML pages ready')
"
```
Expected: 80+ pages.

- [ ] **Step 7.2: Dispatch extraction subagent**

Controller dispatches a `general-purpose` subagent:

```
You are an extraction agent. Read admission/tickets HTML pages and extract
the regular admission prices for each attraction.

For each `<slug>.html` in `F:\pj\NorthShore Kids Events\data\raw\attraction_prices\_pages\`:

1. Read the file.
2. Extract the GENERAL ADMISSION price tier (NOT special exhibits, IMAX, or
   private events). For each price field, use null if not on the page.
3. If the attraction is genuinely free (state parks, free museums), set adult=0.
4. Output JSON with this schema:
   {
     "slug": "<filename without .html>",
     "status": "ok" or "failed:<reason>",
     "adult": <number or null>,
     "child": <number or null>,
     "senior": <number or null>,
     "student": <number or null>,
     "family": <number or null>,
     "free_under_age": <number or null, e.g., 3 if "free under 3">,
     "notes": "<short string or null, e.g., 'Members free'>",
     "source_url": "<from data/raw/attraction_prices/_fetch_log.json[slug].source_url>"
   }
5. Write each to `data/raw/attraction_prices/<slug>.json` using Write tool.

Process in batches of 10. Total ~80-108 files.

If a page genuinely has no price info (unclear admission policy), set
status="failed:no_price_visible" and leave all numeric fields null.

When done, run:
  python -c "
import json, glob
files = [f for f in glob.glob('data/raw/attraction_prices/*.json') if '_fetch_log' not in f]
ok = sum(1 for f in files if json.load(open(f, encoding='utf-8')).get('status') == 'ok')
print(f'extracted: {ok}/{len(files)} ok_ratio={ok/len(files):.1%}')
"

Report: count processed, ok_ratio (must be ≥80%), any tricky/ambiguous pages.
```

- [ ] **Step 7.3: Verify extraction quality**

Spot check:
```bash
python -c "
import json
for s in ['museum-of-science', 'new-england-aquarium', 'boston-childrens-museum']:
    try:
        print(s, json.load(open(f'data/raw/attraction_prices/{s}.json', encoding='utf-8')))
    except FileNotFoundError:
        print(s, 'MISSING')
"
```
Expected: 3 records with plausible adult/child prices.

- [ ] **Step 7.4: Commit**

```bash
git add data/raw/attraction_prices/*.json
git commit -m "data: extract attraction original prices from fetched HTML (subagent)"
```

---

## Task 8 — Attraction hero image scraper (og:image, regex only)

**Why:** UI 卡片需要代表图。Pure regex extraction;no LLM needed.

**Files:**
- Create: `src/malibbene/sources/attractions/images.py`
- Create: `scripts/scrape_attraction_images.py`
- Create: `tests/test_attraction_images.py`

- [ ] **Step 8.1: Write the failing test**

Create `tests/test_attraction_images.py`:

```python
from unittest.mock import patch


def test_extract_og_image_from_head():
    from malibbene.sources.attractions.images import extract_og_image
    html = '<html><head><meta property="og:image" content="https://x/h.jpg"></head></html>'
    assert extract_og_image(html) == "https://x/h.jpg"


def test_extract_og_image_attribute_reverse_order():
    from malibbene.sources.attractions.images import extract_og_image
    html = '<meta content="https://x/h.jpg" property="og:image">'
    assert extract_og_image(html) == "https://x/h.jpg"


def test_extract_og_image_resolves_relative():
    from malibbene.sources.attractions.images import extract_og_image
    html = '<meta property="og:image" content="/img/hero.jpg">'
    assert extract_og_image(html, base_url="https://www.mos.org/visit") == "https://www.mos.org/img/hero.jpg"


def test_extract_og_image_returns_none_when_missing():
    from malibbene.sources.attractions.images import extract_og_image
    assert extract_og_image("<html><head><title>x</title></head></html>") is None


def test_scrape_one_downloads_image(tmp_path):
    from malibbene.sources.attractions import images

    with patch.object(images, "fetch", return_value='<meta property="og:image" content="https://x/h.jpg">'), \
         patch.object(images, "_download_binary", return_value=b"\x89PNG\r\n..."):
        result = images.scrape_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["og_image_url"] == "https://x/h.jpg"
    assert (tmp_path / "mos.jpg").exists()


def test_scrape_one_marks_failed_when_no_og(tmp_path):
    from malibbene.sources.attractions import images

    with patch.object(images, "fetch", return_value="<html><body>no og</body></html>"):
        result = images.scrape_one("mos", "https://www.mos.org/", out_dir=tmp_path)

    assert result["status"].startswith("failed")
```

- [ ] **Step 8.2: Run test to verify it fails**

Run: `pytest tests/test_attraction_images.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 8.3: Write implementation**

Create `src/malibbene/sources/attractions/images.py`:

```python
"""Scrape og:image from attraction websites and cache binaries locally."""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

from malibbene.common.http import fetch, UA

OG_RE = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_RE_REV = re.compile(
    r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
    re.IGNORECASE,
)


def extract_og_image(html: str, *, base_url: str | None = None) -> str | None:
    m = OG_RE.search(html) or OG_RE_REV.search(html)
    if not m:
        return None
    url = m.group(1).strip()
    if url.startswith("http"):
        return url
    if base_url:
        return urllib.parse.urljoin(base_url, url)
    return None


def _download_binary(url: str, *, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _ext_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def scrape_one(slug: str, website: str, *, out_dir: Path) -> dict:
    if not website.startswith("http"):
        return {"slug": slug, "status": "failed:no_website"}
    try:
        html = fetch(website)
    except Exception as e:
        return {"slug": slug, "status": f"failed:fetch:{e}"}
    img_url = extract_og_image(html, base_url=website)
    if not img_url:
        return {"slug": slug, "status": "failed:no_og_image"}
    try:
        body = _download_binary(img_url)
    except Exception as e:
        return {"slug": slug, "status": f"failed:download:{e}", "og_image_url": img_url}
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = _ext_from_url(img_url)
    local = out_dir / f"{slug}{ext}"
    local.write_bytes(body)
    return {
        "slug": slug,
        "status": "ok",
        "og_image_url": img_url,
        "local_path": str(local.relative_to(out_dir.parents[2])),
        "bytes": len(body),
    }
```

Create `scripts/scrape_attraction_images.py`:

```python
"""Download hero (og:image) for each attraction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.attractions.images import scrape_one


def main() -> int:
    idx_path = REPO / "data" / "structured" / "_tmp_attractions_index.json"
    if not idx_path.exists():
        print("ERROR: run scripts/build_attractions_index.py first")
        return 1
    idx = json.loads(idx_path.read_text(encoding="utf-8"))

    meta_dir = REPO / "data" / "raw" / "attraction_images"
    img_dir = REPO / "data" / "static" / "images"
    meta_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    total = 0
    for slug, entry in idx.items():
        total += 1
        meta_path = meta_dir / f"{slug}.json"
        if meta_path.exists():
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            if existing.get("status") == "ok":
                ok += 1
                continue
        website = entry.get("website") or ""
        print(f"[{total}/{len(idx)}] {slug} ← {website}")
        result = scrape_one(slug, website, out_dir=img_dir)
        meta_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        if result["status"] == "ok":
            ok += 1

    print(f"Done. ok={ok}/{total} = {ok/total:.1%}")
    return 0 if ok / total >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8.4: Run tests to verify they pass**

Run: `pytest tests/test_attraction_images.py -v`
Expected: 6 passed

- [ ] **Step 8.5: Run on real data**

Run: `python scripts/scrape_attraction_images.py`
Expected: `Done. ok=X/108 = N%` with N ≥ 80.

- [ ] **Step 8.6: Spot check 3 images load**

Manually open `data/static/images/museum-of-science.*`, `.../new-england-aquarium.*`, `.../boston-childrens-museum.*`.

- [ ] **Step 8.7: Commit**

```bash
git add src/malibbene/sources/attractions/images.py scripts/scrape_attraction_images.py tests/test_attraction_images.py data/raw/attraction_images/
git commit -m "feat(attractions): scrape og:image hero photos with local cache"
```

(Binaries in `data/static/images/` not committed — gitignored.)

---

## Task 9 — Category placeholder SVGs

**Files:**
- Create 9 SVG files in `data/static/placeholders/`

- [ ] **Step 9.1: Create 9 placeholder SVGs**

For each `(category, bg, fg, label)` row below, create `data/static/placeholders/<category>.svg`:

| Category | bg | fg | label |
|---|---|---|---|
| family | `#EAF1EE` | `#1B5740` | family |
| children | `#F4EFE8` | `#8C6018` | children |
| history | `#ECEAE4` | `#4A4845` | history |
| nature | `#C4DDCF` | `#1B5740` | nature |
| art | `#F4EAE9` | `#8C2A1E` | art |
| science | `#EAF1EE` | `#2A7055` | science |
| ocean | `#FAFAF7` | `#2A7055` | ocean |
| recreation | `#FDF1E2` | `#D97706` | recreation |
| default | `#ECEAE4` | `#4A4845` | attraction |

Template:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <rect width="200" height="200" fill="{BG}"/>
  <text x="100" y="105" text-anchor="middle" font-family="Libre Baskerville, Georgia, serif"
        font-size="14" font-style="italic" fill="{FG}">{LABEL}</text>
</svg>
```

- [ ] **Step 9.2: Verify all 9 SVGs exist**

```bash
python -c "from pathlib import Path; ps = sorted(Path('data/static/placeholders').glob('*.svg')); print(len(ps)); [print(p.name) for p in ps]"
```
Expected: 9 files printed.

- [ ] **Step 9.3: Commit**

```bash
git add data/static/placeholders/
git commit -m "feat(static): add 9 category placeholder SVGs as og:image fallback"
```

---

## Task 10 — Update CLAUDE.md & BRD reflect new data layer

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/BRD.md`

- [ ] **Step 10.1: Append to CLAUDE.md "Repository Layout"**

Add under `data/`:
```
├── data/static/
│   ├── images/<slug>.<ext>          # hero 图本地缓存 (gitignored)
│   └── placeholders/<category>.svg  # category fallback SVG (入 git)
```

- [ ] **Step 10.2: Append to CLAUDE.md "Key Technical Decisions"**

```
- **Geocoding**: OSM Nominatim (free, 1 req/sec) via `malibbene.common.geocode.geocode(query)`;
  results cached in `data/.cache/geocode.json`. Library locations use street address (extracted
  from each library's main site via subagent). Attractions use street address from raw pass data.
- **LLM 提取**(铁律:不调 Anthropic API):页面 HTML 由 Python scraper fetch 落盘到 `_pages/`,
  extraction 通过 subagent dispatch 完成,subagent 用 Read 工具读 HTML、Write 工具落 JSON。
- **Hero images**: og:image meta scraped from each attraction; cached binary at
  `data/static/images/<slug>.<ext>` (gitignored). Fallback: `data/static/placeholders/<category>.svg`.
```

- [ ] **Step 10.3: Update BRD §7.1 / §8.2**

In `docs/BRD.md`:
- §7.1 row "距离用户家的开车时间": `⚠️ 粗略` → `✅ 已有(Nominatim 直线距离)`
- §8.2 缺口表 append row: `景点原价 / 图书馆街道地址 / 景点 hero 图 → 已补齐 (plan-1)`

- [ ] **Step 10.4: Commit**

```bash
git add CLAUDE.md docs/BRD.md
git commit -m "docs: reflect plan-1 outputs (geocoding, subagent extraction, hero images)"
```

---

## Verification Summary

After all 10 tasks, the repo should contain:

| Artifact | Path | Count |
|---|---|---|
| Temporary attractions index | `data/structured/_tmp_attractions_index.json` | ~108 entries |
| Geocoding cache | `data/.cache/geocode.json` | ~170 entries |
| Geocoded coords | `data/structured/geo.json` | attractions + libraries |
| Library HTMLs (gitignored) | `data/raw/library_addresses/_pages/*.html` | ~50+ files |
| Library extracted addresses | `data/raw/library_addresses/<lib_id>.json` | ~48+ files (≥80% ok) |
| Attraction admission HTMLs (gitignored) | `data/raw/attraction_prices/_pages/*.html` | ~85+ files |
| Attraction extracted prices | `data/raw/attraction_prices/<slug>.json` | ~85+ files (≥80% ok) |
| Attraction image meta | `data/raw/attraction_images/*.json` | ~108 files (≥80% ok) |
| Hero image binaries (gitignored) | `data/static/images/*.{jpg,png,webp}` | ~85+ files |
| Category placeholders | `data/static/placeholders/*.svg` | 9 files |
| New Python modules | `src/malibbene/{common/geocode.py, sources/libraries/addresses.py, sources/attractions/{prices,images}.py}` | 4 files |
| New scripts | `scripts/{build_attractions_index, fetch_library_pages, fetch_attraction_price_pages, scrape_attraction_images, geocode_all}.py` | 5 files |
| New tests | `tests/test_{build_attractions_index, geocode, library_addresses_fetcher, attraction_prices_fetcher, attraction_images}.py` | 5 files |

**Quality gates before declaring plan-1 done:**
- All pytest tests pass: `pytest tests/ -v`
- Each scraper / extraction stage `ok_ratio ≥ 80%` ([[feedback_test_after_step]])
- All ~10 commits in `git log`
- 不调 Anthropic API,所有 LLM 提取通过 subagent dispatch 完成

After this, plan-2 (build pipeline → `libraries.json` / `attractions.json` / `passes.json`) can begin.
