# Plan 1 — Data Augmentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把前端 v0.1 必需的 3 类新数据补齐:景点+图书馆 lat/lon、景点 original price、景点 hero image。产物落到 `data/structured/geo.json`、`data/raw/attraction_prices/`、`data/raw/library_addresses/`、`data/static/images/`。

**Architecture:** 增加 1 个 `common/geocode.py` 工具 + 3 个 scraper(`sources/libraries/addresses.py`、`sources/attractions/prices.py`、`sources/attractions/images.py`)+ 4 个 CLI 入口脚本。所有 scraper 走现有 `common/http.fetch` 模式(stdlib urllib + 24h cache,失败可升级 `render_js=True` 用 Playwright)。AI 提取走 Claude Haiku 4.5,key 走 `ANTHROPIC_API_KEY` env。

**Tech Stack:** Python 3.11+ / stdlib urllib / Playwright(可选,JS 页面)/ Anthropic SDK(Claude Haiku 4.5)/ OSM Nominatim(geocoding,免费,1 req/sec 限流)/ pytest

---

## 0. 前置准备(零任务,只读)

**输入文件**(已就绪):
- `data/raw/assabet/index/*.json`(52 馆,每条 pass 有 `slug` / `museum_name` / `address` / `website`)
- `data/raw/libcal/index/*.json`(5 馆)
- `data/raw/museumkey/index/*.json`(2 馆)
- `config/library_seeds.json`(59 馆 metadata,带 `domain` 但无 street address)
- `config/platform_pass_ids/{bpl,libcal,museumkey}.json`(平台 pass-id → canonical benefit_id)

**输出**(本 plan 产出):
- `data/structured/_tmp_attractions_index.json` — 临时景点索引(plan-2 会用它,然后被 `attractions.json` 取代;`_tmp_` 前缀按 [[feedback_temp_files]] 不入 git)
- `data/structured/geo.json` — `{ "attractions": {<slug>: {lat, lon}}, "libraries": {<lib_id>: {lat, lon}} }`
- `data/raw/library_addresses/<lib_id>.json` — 每馆 `{street, city, state, zip, status, raw_text}`
- `data/raw/attraction_prices/<slug>.json` — 每景点 `{adult, child, senior, student, notes, status, raw_text}`
- `data/raw/attraction_images/<slug>.json` — 每景点 `{og_image_url, local_path, status}`
- `data/static/images/<slug>.<ext>` — hero 图本地缓存(gitignore,体积大)
- `data/static/placeholders/<category>.svg` — fallback 占位图(入 git,小)

**新增依赖**(`pyproject.toml`):
```toml
[project.optional-dependencies]
browser = ["playwright>=1.40"]
ai = ["anthropic>=0.40"]
dev = ["pytest>=7"]
```

**.gitignore 追加**:
```
data/static/images/
data/.cache/
data/structured/_tmp_*
```

---

## File Structure

```
src/malibbene/
├── common/
│   └── geocode.py                    # NEW — Nominatim wrapper + cache + rate limit
├── sources/
│   ├── attractions/
│   │   ├── prices.py                 # NEW — Original price scraper (AI extract)
│   │   └── images.py                 # NEW — og:image scraper + downloader
│   └── libraries/                    # NEW dir
│       ├── __init__.py
│       └── addresses.py              # NEW — Library street address scraper (AI extract)
└── ai/                               # NEW dir
    ├── __init__.py
    └── extract.py                    # NEW — Claude Haiku extraction helper

scripts/
├── build_attractions_index.py        # NEW — 扫 raw/*/index/ → _tmp_attractions_index.json
├── scrape_library_addresses.py       # NEW
├── scrape_attraction_prices.py       # NEW
├── scrape_attraction_images.py       # NEW
└── geocode_all.py                    # NEW — 读上面产物,跑 Nominatim,写 geo.json

tests/
├── test_geocode.py                   # NEW
├── test_ai_extract.py                # NEW (with mock)
├── test_build_attractions_index.py   # NEW
├── test_library_addresses.py         # NEW (parser-level)
├── test_attraction_prices.py         # NEW (parser-level)
└── test_attraction_images.py         # NEW (parser-level)
```

---

## Task 1 — Bootstrap: build temporary attractions index

**Why:** 后续所有 scraper(prices / images / geocoding)需要"108 个唯一景点"清单作为输入。plan-2 才正式产出 `attractions.json`,plan-1 先用 `_tmp_` 前缀建一份索引,plan-2 落地后会被取代。

**Files:**
- Create: `scripts/build_attractions_index.py`
- Create: `tests/test_build_attractions_index.py`
- Test fixture: `tests/fixtures/attractions_index/sample_assabet.json`(后面 step 创建)
- Output: `data/structured/_tmp_attractions_index.json`

- [ ] **Step 1.1: Write the failing test**

Create `tests/test_build_attractions_index.py`:

```python
"""Test extracting unique attractions across all platforms."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_raw_root(tmp_path):
    """Build a minimal data/raw/ structure with 2 assabet libs sharing 1 pass."""
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
            # mos shows up in both libraries — must dedupe
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
    # sources are the libraries that link to this attraction
    assert set(idx["mos"]["sources"]) == {"wakefield", "reading"}
    assert idx["neaq"]["sources"] == ["wakefield"]


def test_build_attractions_index_handles_libcal_via_platform_map(fake_raw_root):
    """LibCal/MuseumKey use platform-specific pass IDs; index should normalize to benefit_id."""
    libcal = fake_raw_root / "raw" / "libcal" / "index"
    libcal.mkdir(parents=True)
    (libcal / "bpl.json").write_text(json.dumps({
        "passes": [
            # BPL libcal pass id 12345 maps to canonical "mos"
            {"libcal_pass_id": "12345", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/visit", "status": "ok"},
        ],
    }), encoding="utf-8")
    # mock platform_pass_ids
    cfg = fake_raw_root / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "libcal.json").write_text(json.dumps({"bpl": {"12345": "mos"}}), encoding="utf-8")

    from scripts.build_attractions_index import build_index

    idx = build_index(fake_raw_root / "raw", config_root=fake_raw_root / "config")
    assert "mos" in idx
    assert "bpl" in idx["mos"]["sources"]
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `rtk pytest tests/test_build_attractions_index.py -v`
Expected: FAIL with `ModuleNotFoundError: scripts.build_attractions_index`

- [ ] **Step 1.3: Write minimal implementation**

Create `scripts/build_attractions_index.py`:

```python
"""Build a temporary canonical attractions index from raw/{assabet,libcal,museumkey}/index/*.json.

Output: data/structured/_tmp_attractions_index.json (plan-2 will supersede with attractions.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_platform_map(config_root: Path, platform: str) -> dict[str, dict[str, str]]:
    """Return { lib_id: { source_pass_id: canonical_benefit_id } }."""
    p = config_root / "platform_pass_ids" / f"{platform}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _canonical_slug(pass_obj: dict, lib_id: str, platform: str, pmap: dict) -> str | None:
    """Extract canonical benefit_id from a raw pass record."""
    if platform == "assabet":
        return pass_obj.get("slug")  # Assabet slug is already canonical
    if platform == "libcal":
        sid = pass_obj.get("libcal_pass_id") or pass_obj.get("pass_id")
        return pmap.get(lib_id, {}).get(str(sid))
    if platform == "museumkey":
        sid = pass_obj.get("museum_id") or pass_obj.get("pass_id")
        return pmap.get(lib_id, {}).get(str(sid))
    return None


def build_index(raw_root: Path, config_root: Path | None = None) -> dict:
    """Walk raw/<platform>/index/*.json, dedupe by canonical slug, return dict."""
    if config_root is None:
        config_root = REPO / "config"

    out: dict[str, dict] = {}
    for platform in ("assabet", "libcal", "museumkey"):
        pmap = _load_platform_map(config_root, platform)
        platform_dir = raw_root / platform / "index"
        if not platform_dir.exists():
            continue
        for lib_file in platform_dir.glob("*.json"):
            lib_id = lib_file.stem
            data = json.loads(lib_file.read_text(encoding="utf-8"))
            for p in data.get("passes", []):
                if p.get("status", "").startswith("failed"):
                    continue
                slug = _canonical_slug(p, lib_id, platform, pmap)
                if not slug:
                    continue
                entry = out.setdefault(slug, {
                    "slug": slug,
                    "museum_name": p.get("museum_name", ""),
                    "address": p.get("address", ""),
                    "website": p.get("website", ""),
                    "categories": p.get("categories", []),
                    "sources": [],
                })
                if lib_id not in entry["sources"]:
                    entry["sources"].append(lib_id)
                # First non-empty field wins (assabet has best metadata usually)
                for fld in ("museum_name", "address", "website"):
                    if not entry[fld] and p.get(fld):
                        entry[fld] = p[fld]
                # Merge categories union
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

- [ ] **Step 1.4: Run test to verify it passes**

Run: `rtk pytest tests/test_build_attractions_index.py -v`
Expected: 2 passed

- [ ] **Step 1.5: Run for real on real raw data**

Run: `python scripts/build_attractions_index.py`
Expected output: `Wrote 108 attractions to .../data/structured/_tmp_attractions_index.json` (数字约 ~100-110)

- [ ] **Step 1.6: Spot check the output**

Run: `python -c "import json; d=json.load(open('data/structured/_tmp_attractions_index.json',encoding='utf-8')); print(len(d), 'attractions'); print('mos:', d.get('museum-of-science'))"`
Expected: prints count and `mos` entry with address, website, ≥3 sources

- [ ] **Step 1.7: Commit**

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
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


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
    # Persisted to cache
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert "Wakefield, MA" in cached


def test_geocode_records_failure(tmp_path):
    from malibbene.common import geocode

    cache_path = tmp_path / "geocache.json"

    with patch("malibbene.common.geocode._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"[]"
        result = geocode.geocode("nonexistent place xyz", cache_path=cache_path)

    assert result["ok"] is False
    # Failure also cached (so we don't re-query)
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached["nonexistent place xyz"]["ok"] is False


def test_geocode_haversine_distance():
    from malibbene.common.geocode import haversine_miles

    # Boston to Wakefield, MA ~12mi straight line
    d = haversine_miles(42.3601, -71.0589, 42.5065, -71.0759)
    assert 9 < d < 13
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `rtk pytest tests/test_geocode.py -v`
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
UA = "Mozilla/5.0 (MuseumPass-MA-Geocoder; contact: rbtsama@github)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_LAST_REQUEST_AT = 0.0


def _urlopen(req, timeout=30):
    # Indirection so tests can patch.
    return urllib.request.urlopen(req, timeout=timeout)


def _rate_limit():
    """Enforce 1 req/sec to Nominatim."""
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

    On failure (no results / network error): returns {ok: False, error: <reason>}.
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

Run: `rtk pytest tests/test_geocode.py -v`
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

## Task 3 — AI extraction helper (Claude Haiku)

**Why:** Tasks 4 (library addresses) 和 6 (original prices) 都靠 Claude Haiku 从自由文字里抽结构化 JSON。共享一个 helper 避免重复。

**Files:**
- Create: `src/malibbene/ai/__init__.py`(空)
- Create: `src/malibbene/ai/extract.py`
- Create: `tests/test_ai_extract.py`

- [ ] **Step 3.1: Update pyproject.toml to add `ai` extra**

Edit `pyproject.toml`:

```toml
[project.optional-dependencies]
browser = ["playwright>=1.40"]
ai = ["anthropic>=0.40"]
dev = ["pytest>=7"]
```

Run: `pip install -e .[ai,dev]`
Expected: `anthropic` installed.

- [ ] **Step 3.2: Write the failing test**

Create `tests/test_ai_extract.py`:

```python
"""Test the AI extraction helper using mocked Anthropic client."""
import json
from unittest.mock import patch, MagicMock


def test_extract_returns_parsed_json():
    """Helper should parse Claude's JSON reply into a dict."""
    from malibbene.ai import extract

    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"adult": 30, "child": 25, "notes": "Free under 3"}')]

    with patch("malibbene.ai.extract._client") as mock_client:
        mock_client.messages.create.return_value = fake_msg
        result = extract.extract_json(
            system="extract prices",
            user="HTML body here",
            schema_hint={"adult": "int", "child": "int", "notes": "str"},
        )

    assert result == {"adult": 30, "child": 25, "notes": "Free under 3"}


def test_extract_recovers_from_json_with_prose_prefix():
    """Claude sometimes prepends 'Here is the JSON:' — strip and parse."""
    from malibbene.ai import extract

    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='Here is the JSON:\n```json\n{"adult": 30}\n```')]

    with patch("malibbene.ai.extract._client") as mock_client:
        mock_client.messages.create.return_value = fake_msg
        result = extract.extract_json(system="x", user="x", schema_hint={"adult": "int"})

    assert result == {"adult": 30}


def test_extract_returns_none_on_unparseable():
    from malibbene.ai import extract

    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="I don't know")]

    with patch("malibbene.ai.extract._client") as mock_client:
        mock_client.messages.create.return_value = fake_msg
        result = extract.extract_json(system="x", user="x", schema_hint={"adult": "int"})

    assert result is None
```

- [ ] **Step 3.3: Run test to verify it fails**

Run: `rtk pytest tests/test_ai_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: malibbene.ai`

- [ ] **Step 3.4: Write minimal implementation**

Create `src/malibbene/ai/__init__.py`:

```python
"""AI extraction helpers (Claude Haiku 4.5)."""
```

Create `src/malibbene/ai/extract.py`:

```python
"""Claude Haiku 4.5 JSON extraction helper.

Uses prompt caching: the system prompt is cached so repeated calls are cheap.
Requires ANTHROPIC_API_KEY in env.
"""
from __future__ import annotations

import json
import os
import re

MODEL = "claude-haiku-4-5-20251001"


def _get_client():
    """Lazy import so tests can run without anthropic installed."""
    import anthropic

    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


_client = None  # populated lazily; patchable for tests


def _ensure_client():
    global _client
    if _client is None:
        _client = _get_client()
    return _client


def _strip_to_json(text: str) -> str | None:
    """Strip surrounding prose/markdown fences and return the JSON substring."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        return m.group(1)
    return None


def extract_json(*, system: str, user: str, schema_hint: dict, max_tokens: int = 800) -> dict | None:
    """Ask Claude Haiku to extract structured JSON from a free-form user input.

    Args:
        system: Task instruction (cached across calls).
        user: The HTML/text to extract from.
        schema_hint: A dict like {"field": "type"} to nudge Claude's output shape.
        max_tokens: Reply cap.

    Returns:
        Parsed dict, or None if reply is unparseable.
    """
    client = _ensure_client()
    schema_str = json.dumps(schema_hint, ensure_ascii=False)
    full_system = (
        f"{system}\n\n"
        f"Reply with ONLY a JSON object matching this schema (use null for unknown fields):\n{schema_str}"
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": full_system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text
    payload = _strip_to_json(raw)
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None
```

- [ ] **Step 3.5: Run test to verify it passes**

Run: `rtk pytest tests/test_ai_extract.py -v`
Expected: 3 passed

- [ ] **Step 3.6: Smoke test against real API (skip if no key)**

Run:
```bash
python -c "
import os
if not os.environ.get('ANTHROPIC_API_KEY'):
    print('SKIP: no ANTHROPIC_API_KEY'); exit()
from malibbene.ai.extract import extract_json
r = extract_json(
    system='Extract person info from text.',
    user='Alice is 30 years old.',
    schema_hint={'name': 'str', 'age': 'int'},
)
print(r)
"
```
Expected: `{'name': 'Alice', 'age': 30}` (or similar) — if no key, prints SKIP.

- [ ] **Step 3.7: Commit**

```bash
git add src/malibbene/ai/ tests/test_ai_extract.py pyproject.toml
git commit -m "feat(ai): Claude Haiku 4.5 JSON extraction helper with prompt cache"
```

---

## Task 4 — Library address scraper

**Why:** `config/library_seeds.json` 只有 domain,无 street address。无地址 geocode 不准。

**Approach:** 每馆主站尝试常见路径 (`/visit`, `/hours`, `/contact`, `/about`) → fetch → 用 Claude Haiku 提 `{street, city, state, zip}`。

**Files:**
- Create: `src/malibbene/sources/libraries/__init__.py`
- Create: `src/malibbene/sources/libraries/addresses.py`
- Create: `scripts/scrape_library_addresses.py`
- Create: `tests/test_library_addresses.py`

- [ ] **Step 4.1: Write the failing test**

Create `tests/test_library_addresses.py`:

```python
"""Unit tests for library address scraping pipeline (mocked HTTP + AI)."""
from unittest.mock import patch


def test_extract_address_from_html_via_ai():
    from malibbene.sources.libraries.addresses import extract_address

    html = "<html><body>Visit us at 60 Main Street, Wakefield, MA 01880. Phone: 781-555-0100</body></html>"

    fake_result = {"street": "60 Main Street", "city": "Wakefield", "state": "MA", "zip": "01880"}
    with patch("malibbene.sources.libraries.addresses.extract_json", return_value=fake_result):
        result = extract_address(html, lib_name="Wakefield Public Library")

    assert result == fake_result


def test_extract_address_returns_status_failed_when_ai_returns_none():
    from malibbene.sources.libraries.addresses import scrape_one

    with patch("malibbene.sources.libraries.addresses.fetch", return_value="<html>foo</html>"), \
         patch("malibbene.sources.libraries.addresses.extract_json", return_value=None):
        result = scrape_one(lib_id="wakefield", lib_name="Wakefield Public Library",
                            base_url="https://wakefieldlibrary.org/")

    assert result["status"].startswith("failed")
    assert "street" not in result or result.get("street") is None
```

- [ ] **Step 4.2: Run test to verify it fails**

Run: `rtk pytest tests/test_library_addresses.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4.3: Write minimal implementation**

Create `src/malibbene/sources/libraries/__init__.py`:

```python
"""Library-side data scrapers (addresses, policies)."""
```

Create `src/malibbene/sources/libraries/addresses.py`:

```python
"""Scrape library street addresses from each library's main site.

Strategy: try common URL paths (/visit, /hours, /contact, /about), feed the
HTML body text to Claude Haiku, extract { street, city, state, zip }.
"""
from __future__ import annotations

import re

from malibbene.ai.extract import extract_json
from malibbene.common.http import fetch

CANDIDATE_PATHS = ["/visit", "/hours", "/contact", "/about", "/locations", "/"]

SYSTEM_PROMPT = (
    "You extract the street address of a public library from a web page. "
    "If the page contains multiple branches, return the MAIN branch (the one most "
    "likely intended by 'visit this library'). If unclear, return null fields."
)


def _html_to_text(html: str) -> str:
    """Crude HTML → text for LLM input (no extra deps)."""
    txt = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()[:8000]  # cap to keep token cost predictable


def extract_address(html: str, *, lib_name: str) -> dict | None:
    """Run AI extraction on already-fetched HTML."""
    text = _html_to_text(html)
    return extract_json(
        system=SYSTEM_PROMPT,
        user=f"Library name: {lib_name}\n\nPage text:\n{text}",
        schema_hint={"street": "str", "city": "str", "state": "str (2-letter)", "zip": "str (5-digit)"},
    )


def scrape_one(lib_id: str, lib_name: str, base_url: str) -> dict:
    """Try each candidate path on the library's main site until extraction succeeds."""
    base = base_url.rstrip("/")
    last_error = "no_path_yielded_address"
    for path in CANDIDATE_PATHS:
        url = base + path
        try:
            html = fetch(url)
        except Exception as e:
            last_error = f"fetch_failed:{e}"
            continue
        result = extract_address(html, lib_name=lib_name)
        if result and result.get("street"):
            return {
                "lib_id": lib_id,
                "source_url": url,
                "status": "ok",
                **result,
            }
    return {"lib_id": lib_id, "status": f"failed:{last_error}"}
```

Create `scripts/scrape_library_addresses.py`:

```python
"""Scrape street addresses for all 59 libraries; write data/raw/library_addresses/<lib_id>.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.libraries.addresses import scrape_one


def derive_base_url(seed: dict) -> str | None:
    """Prefer card_page (the main library site), fall back to deriving from domain."""
    if seed.get("card_page"):
        from urllib.parse import urlparse

        p = urlparse(seed["card_page"])
        return f"{p.scheme}://{p.netloc}/"
    # platform domain (e.g. xxx.assabetinteractive.com) is NOT the library's main site
    # — skip in that case
    return None


def main() -> int:
    seeds = json.loads((REPO / "config" / "library_seeds.json").read_text(encoding="utf-8"))
    out_dir = REPO / "data" / "raw" / "library_addresses"
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    total = 0
    for seed in seeds["libraries"]:
        total += 1
        base = derive_base_url(seed)
        if not base:
            result = {"lib_id": seed["id"], "status": "failed:no_base_url"}
        else:
            print(f"[{total}/{len(seeds['libraries'])}] {seed['id']} ← {base}")
            result = scrape_one(seed["id"], seed["name"], base)
        (out_dir / f"{seed['id']}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if result["status"] == "ok":
            ok += 1

    print(f"Done. ok={ok}/{total} = {ok/total:.1%}")
    return 0 if ok / total >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4.4: Run test to verify it passes**

Run: `rtk pytest tests/test_library_addresses.py -v`
Expected: 2 passed

- [ ] **Step 4.5: Run on real data, verify ok_ratio ≥ 80%**

Run: `python scripts/scrape_library_addresses.py`
Expected: prints `Done. ok=X/59 = N%` with N ≥ 80. If <80%, inspect 5 failing `data/raw/library_addresses/*.json` files and tune `CANDIDATE_PATHS` or `SYSTEM_PROMPT` before commit.

- [ ] **Step 4.6: Commit**

```bash
git add src/malibbene/sources/libraries/ scripts/scrape_library_addresses.py tests/test_library_addresses.py data/raw/library_addresses/
git commit -m "feat(libraries): scrape street addresses for 59 libraries via Claude Haiku"
```

---

## Task 5 — Geocode attractions + libraries (write geo.json)

**Files:**
- Create: `scripts/geocode_all.py`
- (Re-uses `malibbene.common.geocode`)

- [ ] **Step 5.1: Write the failing test (smoke)**

Add to `tests/test_geocode.py` (append at end):

```python
def test_geocode_all_writes_geojson(tmp_path, monkeypatch):
    """End-to-end: read attractions index + library addresses, write geo.json."""
    import json

    # Fake attractions index
    structured = tmp_path / "data" / "structured"
    structured.mkdir(parents=True)
    (structured / "_tmp_attractions_index.json").write_text(json.dumps({
        "mos": {"address": "1 Science Park, Boston, MA 02114"},
    }), encoding="utf-8")

    # Fake library addresses raw
    libaddr = tmp_path / "data" / "raw" / "library_addresses"
    libaddr.mkdir(parents=True)
    (libaddr / "wakefield.json").write_text(json.dumps({
        "lib_id": "wakefield", "status": "ok",
        "street": "60 Main Street", "city": "Wakefield", "state": "MA", "zip": "01880",
    }), encoding="utf-8")

    # Patch geocode() to return a known value
    from malibbene.common import geocode as gmod

    def fake_geocode(query, **kw):
        return {"ok": True, "lat": 42.0 + len(query) * 0.001, "lon": -71.0}

    monkeypatch.setattr(gmod, "geocode", fake_geocode)
    monkeypatch.setattr("scripts.geocode_all.REPO", tmp_path)

    from scripts.geocode_all import main
    main()

    out = json.loads((tmp_path / "data" / "structured" / "geo.json").read_text(encoding="utf-8"))
    assert "mos" in out["attractions"]
    assert "wakefield" in out["libraries"]
    assert out["attractions"]["mos"]["ok"] is True
```

- [ ] **Step 5.2: Run test to verify it fails**

Run: `rtk pytest tests/test_geocode.py::test_geocode_all_writes_geojson -v`
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
    addr = entry.get("address", "").strip()
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

    # Attractions
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

    # Libraries
    n_ok = 0
    n_total = 0
    if libaddr_dir.exists():
        for f in libaddr_dir.glob("*.json"):
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

Run: `rtk pytest tests/test_geocode.py -v`
Expected: all tests pass (5 total now)

- [ ] **Step 5.5: Run for real**

Run: `python scripts/geocode_all.py`
Expected: prints `Attractions: X/108 geocoded` (X ≥ 90), `Libraries: Y/59 geocoded` (Y ≥ ok_count from Task 4).
Run time: ~3 minutes (1 sec/request × ~170 unique addresses; cache hits skip).

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
    print(f'MOS ↔ Wakefield Library: {d:.1f} mi')
"
```
Expected: ~10-12 mi.

- [ ] **Step 5.7: Commit**

```bash
git add scripts/geocode_all.py tests/test_geocode.py data/structured/geo.json
git commit -m "feat(geocode): batch geocode attractions + libraries to geo.json"
```

---

## Task 6 — Attraction original price scraper

**Why:** UI 卡片需要划线价。每景点官网 admission/tickets 页结构都不同 → AI 提取。

**Files:**
- Create: `src/malibbene/sources/attractions/prices.py`
- Create: `scripts/scrape_attraction_prices.py`
- Create: `tests/test_attraction_prices.py`

- [ ] **Step 6.1: Write the failing test**

Create `tests/test_attraction_prices.py`:

```python
from unittest.mock import patch


def test_extract_prices_via_ai():
    from malibbene.sources.attractions.prices import extract_prices

    html = "<p>Adult $30, Child (3-11) $25, Senior $27. Members free.</p>"
    fake = {"adult": 30, "child": 25, "senior": 27, "student": None,
            "family": None, "free_under_age": None, "notes": "Members free"}
    with patch("malibbene.sources.attractions.prices.extract_json", return_value=fake):
        r = extract_prices(html, attraction_name="Museum of Science")

    assert r["adult"] == 30
    assert r["child"] == 25


def test_scrape_one_tries_multiple_paths():
    """If /admission 404s, fall back to /tickets, then /visit."""
    from malibbene.sources.attractions.prices import scrape_one

    fetch_calls = []
    def fake_fetch(url, **kw):
        fetch_calls.append(url)
        if "/admission" in url or "/tickets" in url:
            raise Exception("404")
        return "<p>Adult $30</p>"

    fake_extract = {"adult": 30, "child": None, "senior": None, "student": None,
                    "family": None, "free_under_age": None, "notes": None}
    with patch("malibbene.sources.attractions.prices.fetch", side_effect=fake_fetch), \
         patch("malibbene.sources.attractions.prices.extract_json", return_value=fake_extract):
        r = scrape_one("mos", "Museum of Science", "https://www.mos.org/")

    assert r["status"] == "ok"
    assert r["adult"] == 30
    # Should have tried multiple URLs
    assert len(fetch_calls) >= 3


def test_scrape_one_marks_failed_when_no_price_found():
    from malibbene.sources.attractions.prices import scrape_one

    with patch("malibbene.sources.attractions.prices.fetch", return_value="<p>no prices</p>"), \
         patch("malibbene.sources.attractions.prices.extract_json", return_value=None):
        r = scrape_one("mos", "Museum of Science", "https://www.mos.org/")

    assert r["status"].startswith("failed")
```

- [ ] **Step 6.2: Run test to verify it fails**

Run: `rtk pytest tests/test_attraction_prices.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 6.3: Write implementation**

Create `src/malibbene/sources/attractions/prices.py`:

```python
"""Scrape original (regular) admission prices from attraction websites.

Strategy: try common URL paths (/admission, /tickets, /visit, /plan-your-visit, /hours),
feed page text to Claude Haiku, extract { adult, child, senior, student, family, notes }.

Falls back to Playwright if static fetch returns empty/short body — some sites
require JS rendering for their admission widgets.
"""
from __future__ import annotations

import re

from malibbene.ai.extract import extract_json
from malibbene.common.http import fetch

CANDIDATE_PATHS = [
    "/admission", "/tickets", "/visit/admission", "/visit/tickets",
    "/plan-your-visit", "/visit", "/hours-admission", "/hours", "/",
]

SYSTEM_PROMPT = (
    "You extract regular admission prices from a museum/attraction web page. "
    "Return the GENERAL ADMISSION price tier (not special exhibitions, IMAX, or events). "
    "If the attraction is genuinely free (e.g., a state park, free museum), set adult=0. "
    "Use null for fields that are not visible on the page. "
    "Prices should be dollar amounts as numbers (e.g., 30 not '$30')."
)

_PRICE_SCHEMA = {
    "adult": "number or null",
    "child": "number or null",
    "senior": "number or null",
    "student": "number or null",
    "family": "number or null",
    "free_under_age": "number or null (e.g., 3 if 'free under 3')",
    "notes": "string or null (e.g., 'Members free')",
}


def _html_to_text(html: str) -> str:
    txt = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()[:10000]


def extract_prices(html: str, *, attraction_name: str) -> dict | None:
    text = _html_to_text(html)
    return extract_json(
        system=SYSTEM_PROMPT,
        user=f"Attraction: {attraction_name}\n\nPage text:\n{text}",
        schema_hint=_PRICE_SCHEMA,
        max_tokens=600,
    )


def scrape_one(slug: str, name: str, base_url: str) -> dict:
    base = base_url.rstrip("/")
    last_error = "no_path_yielded_price"

    for path in CANDIDATE_PATHS:
        url = base + path
        # Try static first
        try:
            html = fetch(url)
        except Exception as e:
            last_error = f"fetch_failed:{e}"
            continue

        if len(html) < 500:
            # likely JS-rendered placeholder; try with Playwright
            try:
                html = fetch(url, render_js=True, force=True)
            except Exception as e:
                last_error = f"render_js_failed:{e}"
                continue

        result = extract_prices(html, attraction_name=name)
        if result and any(result.get(k) is not None for k in ("adult", "child", "senior")):
            return {"slug": slug, "source_url": url, "status": "ok", **result}

    return {"slug": slug, "status": f"failed:{last_error}"}
```

Create `scripts/scrape_attraction_prices.py`:

```python
"""Scrape original prices for all attractions; write data/raw/attraction_prices/<slug>.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.attractions.prices import scrape_one


def main() -> int:
    idx_path = REPO / "data" / "structured" / "_tmp_attractions_index.json"
    if not idx_path.exists():
        print("ERROR: run scripts/build_attractions_index.py first")
        return 1
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    out_dir = REPO / "data" / "raw" / "attraction_prices"
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    total = 0
    for slug, entry in idx.items():
        total += 1
        out_path = out_dir / f"{slug}.json"
        if out_path.exists():
            # Resume support — skip already-scraped
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            if existing.get("status") == "ok":
                ok += 1
                continue
        website = entry.get("website") or ""
        if not website.startswith("http"):
            result = {"slug": slug, "status": "failed:no_website"}
        else:
            print(f"[{total}/{len(idx)}] {slug} ← {website}")
            result = scrape_one(slug, entry.get("museum_name", slug), website)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        if result["status"] == "ok":
            ok += 1

    print(f"Done. ok={ok}/{total} = {ok/total:.1%}")
    return 0 if ok / total >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6.4: Run test to verify it passes**

Run: `rtk pytest tests/test_attraction_prices.py -v`
Expected: 3 passed

- [ ] **Step 6.5: Run on real data (long-running, ~30 min)**

Run: `python scripts/scrape_attraction_prices.py`
Expected: `Done. ok=X/108 = N%` with N ≥ 80.

If below 80%:
- Inspect 5 failing `data/raw/attraction_prices/*.json` files
- Common issues: site requires consent banner (try render_js), price hidden behind link (add to `CANDIDATE_PATHS`), attraction genuinely free with no admission page (acceptable: `adult: 0`, `notes: "Free admission"`)
- Tune CANDIDATE_PATHS or SYSTEM_PROMPT, re-run (resume support skips already-OK rows)

- [ ] **Step 6.6: Commit**

```bash
git add src/malibbene/sources/attractions/prices.py scripts/scrape_attraction_prices.py tests/test_attraction_prices.py data/raw/attraction_prices/
git commit -m "feat(attractions): scrape original prices via Claude Haiku from admission pages"
```

---

## Task 7 — Attraction hero image scraper (og:image)

**Why:** UI 卡片需要代表图。每景点官网 head 通常有 `<meta property="og:image">` 给社交分享卡用,作者明示可用。fallback 用 category 占位图。

**Files:**
- Create: `src/malibbene/sources/attractions/images.py`
- Create: `scripts/scrape_attraction_images.py`
- Create: `tests/test_attraction_images.py`

- [ ] **Step 7.1: Write the failing test**

Create `tests/test_attraction_images.py`:

```python
from unittest.mock import patch


def test_extract_og_image_url_from_head():
    from malibbene.sources.attractions.images import extract_og_image

    html = """
    <html><head>
      <meta property="og:image" content="https://example.com/hero.jpg">
      <meta property="og:title" content="MOS">
    </head></html>
    """
    assert extract_og_image(html) == "https://example.com/hero.jpg"


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
```

- [ ] **Step 7.2: Run test to verify it fails**

Run: `rtk pytest tests/test_attraction_images.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 7.3: Write implementation**

Create `src/malibbene/sources/attractions/images.py`:

```python
"""Scrape og:image from attraction websites and cache the file locally."""
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
OG_RE_REV = re.compile(  # some sites order attrs the other way
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
    """Fetch website, extract og:image URL, download to out_dir/<slug>.<ext>."""
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
        "local_path": str(local.relative_to(out_dir.parents[2])),  # relative to repo root
        "bytes": len(body),
    }
```

Create `scripts/scrape_attraction_images.py`:

```python
"""Download hero (og:image) for each attraction; write metadata + binary file."""
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

- [ ] **Step 7.4: Run test to verify it passes**

Run: `rtk pytest tests/test_attraction_images.py -v`
Expected: 4 passed

- [ ] **Step 7.5: Run on real data**

Run: `python scripts/scrape_attraction_images.py`
Expected: `Done. ok=X/108 = N%` with N ≥ 80.

- [ ] **Step 7.6: Spot check 3 downloaded images**

Manually open `data/static/images/museum-of-science.*`, `.../new-england-aquarium.*`, `.../boston-childrens-museum.*` — confirm valid images load.

- [ ] **Step 7.7: Commit**

```bash
git add src/malibbene/sources/attractions/images.py scripts/scrape_attraction_images.py tests/test_attraction_images.py data/raw/attraction_images/
git commit -m "feat(attractions): scrape og:image hero photos with local cache"
```

> Note: `data/static/images/*` 不 commit(在 .gitignore);本地文件保留供前端读。

---

## Task 8 — Category placeholder SVGs

**Why:** 当 og:image 抓不到(~10-20% 景点)或加载失败,前端要有 fallback 占位图。

**Approach:** 给前 8 个 category 各做一张 200×200 SVG,纯色块 + category icon。category 取自数据里高频 tag。

**Files:**
- Create: `data/static/placeholders/family.svg`、`children.svg`、`history.svg`、`nature.svg`、`art.svg`、`science.svg`、`ocean.svg`、`recreation.svg`、`default.svg`

- [ ] **Step 8.1: Define category → color mapping**

Decide colors using the spec's palette (`docs/superpowers/specs/2026-05-15-product-design.md` §2.1):

| Category | Background | Foreground |
|---|---|---|
| Family | `#EAF1EE` (g-pale) | `#1B5740` (g) |
| Children | `#F4EFE8` (au-pale) | `#8C6018` (au) |
| History | `#ECEAE4` (paper) | `#4A4845` (ink-3) |
| Nature | `#C4DDCF` (g-light) | `#1B5740` (g) |
| Art | `#F4EAE9` (rd-pale) | `#8C2A1E` (rd) |
| Science | `#EAF1EE` (g-pale) | `#2A7055` (g-2) |
| Ocean | `#FAFAF7` (white) | `#2A7055` (g-2) |
| Recreation | `#FDF1E2` (or-pale) | `#D97706` (or) |
| default | `#ECEAE4` (paper) | `#4A4845` (ink-3) |

- [ ] **Step 8.2: Write each SVG**

Create `data/static/placeholders/default.svg` (others follow same template, vary colors and label):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <rect width="200" height="200" fill="#ECEAE4"/>
  <text x="100" y="105" text-anchor="middle" font-family="Libre Baskerville, Georgia, serif"
        font-size="14" font-style="italic" fill="#4A4845">attraction</text>
</svg>
```

Create `data/static/placeholders/family.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <rect width="200" height="200" fill="#EAF1EE"/>
  <text x="100" y="105" text-anchor="middle" font-family="Libre Baskerville, Georgia, serif"
        font-size="14" font-style="italic" fill="#1B5740">family</text>
</svg>
```

(Repeat for `children` / `history` / `nature` / `art` / `science` / `ocean` / `recreation` — change bg, fg, label per Step 8.1 table.)

- [ ] **Step 8.3: Verify all 9 SVGs render**

Run: `python -c "from pathlib import Path; ps = list(Path('data/static/placeholders').glob('*.svg')); print(len(ps), 'placeholders'); [print(p.name) for p in ps]"`
Expected: 9 placeholders listed.

- [ ] **Step 8.4: Commit**

```bash
git add data/static/placeholders/
git commit -m "feat(static): add 9 category placeholder SVGs as og:image fallback"
```

---

## Task 9 — Update CLAUDE.md & BRD reflect new data layer

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/BRD.md`

- [ ] **Step 9.1: Append to CLAUDE.md "Repository Layout" section**

Add after the existing `data/snapshots/...` line:

```
├── data/static/
│   ├── images/<slug>.<ext>          # hero 图本地缓存(gitignored)
│   └── placeholders/<category>.svg  # category fallback 占位图(入 git)
```

And add a new row to the file-naming table:
- `data/static/images/<slug>.<ext>` — hero image cached files
- `data/static/placeholders/<category>.svg` — fallback placeholder SVGs

- [ ] **Step 9.2: Append to CLAUDE.md "Key Technical Decisions"**

```
- **Geocoding**: OSM Nominatim (free, 1 req/sec) via `malibbene.common.geocode.geocode(query)`;
  results cached in `data/.cache/geocode.json`. Library locations use town centroid; attractions use street address.
- **AI extraction**: Claude Haiku 4.5 via `malibbene.ai.extract.extract_json(system, user, schema_hint)`.
  Requires `ANTHROPIC_API_KEY` env. Used for library addresses + attraction original prices.
- **Hero images**: og:image meta tag scraped from each attraction website; cached binary at
  `data/static/images/<slug>.<ext>` (gitignored). Fallback: `data/static/placeholders/<category>.svg`.
```

- [ ] **Step 9.3: Append to BRD §6.1 / §7.1 the now-completed gaps**

In `docs/BRD.md` find:
- §7.1 row "距离用户家的开车时间" — update status `⚠️ 粗略` → `✅ 已有(Nominatim 直线距离)`
- §8.2 缺口表 — add row: "景点原价 / 图书馆街道地址 / 景点 hero 图 → 已补齐(plan-1)"

- [ ] **Step 9.4: Commit**

```bash
git add CLAUDE.md docs/BRD.md
git commit -m "docs: reflect plan-1 outputs (geocoding, AI extraction, hero images)"
```

---

## Verification Summary

After running all 9 tasks, the repo should contain:

| Artifact | Path | Count |
|---|---|---|
| Temporary attractions index | `data/structured/_tmp_attractions_index.json` | ~108 entries |
| Geocoding cache | `data/.cache/geocode.json` | ~170 entries |
| Geocoded coords | `data/structured/geo.json` | attractions + libraries |
| Library addresses | `data/raw/library_addresses/*.json` | 59 files, ≥48 with status=ok |
| Attraction prices | `data/raw/attraction_prices/*.json` | ~108 files, ≥86 with status=ok |
| Attraction image meta | `data/raw/attraction_images/*.json` | ~108 files, ≥86 with status=ok |
| Hero image binaries | `data/static/images/*.{jpg,png,webp}` | ~86 files (gitignored) |
| Category placeholders | `data/static/placeholders/*.svg` | 9 files |
| New modules | `src/malibbene/{common/geocode.py, ai/extract.py, sources/libraries/addresses.py, sources/attractions/{prices,images}.py}` | 5 files |
| New scripts | `scripts/{build_attractions_index, scrape_library_addresses, scrape_attraction_prices, scrape_attraction_images, geocode_all}.py` | 5 files |
| New tests | `tests/test_{build_attractions_index, geocode, ai_extract, library_addresses, attraction_prices, attraction_images}.py` | 6 files |

**Quality gate before declaring plan-1 done:**
- All pytest tests pass (`rtk pytest tests/ -v`)
- Each scraper's `ok_ratio ≥ 80%` ([[feedback_test_after_step]])
- All commits pushed (~9 commits)

After this, plan-2 (build pipeline → `libraries.json` / `attractions.json` / `passes.json`) can begin.
