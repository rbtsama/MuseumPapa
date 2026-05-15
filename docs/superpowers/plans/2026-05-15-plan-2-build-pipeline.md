# Plan 2 — Build Pipeline Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to execute task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 把 plan-1 + 历史 scraper 留下的 `data/raw/*` 合并、规范化、拼装,产出前端可直接消费的 3 份结构化 JSON:`libraries.json`、`attractions.json`、`passes.json`,以及它们的中间锚点 `library_catalog.json`。

**Architecture:** 一个新模块 `src/malibbene/build/` 包含 4 个纯函数 builder(catalog → libraries → attractions → passes);一个 CLI `scripts/build.py` 串起来,每步落盘并打印 status_summary;最后 merge `config/manual_overrides.json` 作为最终修正层。

**Tech Stack:** Python 3.11+ / stdlib / pytest / `malibbene.common.normalize` (已有,from backup port)

---

## 0. 输入 / 输出契约

**Input 文件**(全部已就绪):

| 路径 | 内容 | 来源 |
|---|---|---|
| `data/raw/{assabet,libcal,museumkey}/index/*.json` | 每馆 pass 目录 | 历史 scraper |
| `data/raw/{assabet,libcal}/availability/*.json` | 每馆 30-day 库存日历 | 历史 scraper |
| `data/raw/library_addresses/*.json` | 每馆街道地址 | plan-1 Task 4 |
| `data/raw/attraction_prices/*.json` | 每景点 adult/child/senior 等 | plan-1 Task 7 |
| `data/raw/attraction_images/*.json` | 每景点 og:image URL + local_path | plan-1 Task 8 |
| `data/structured/geo.json` | 全 (lib × attraction) 经纬度 | plan-1 Task 5 |
| `config/library_seeds.json` | 59 馆 metadata seed | 已有 |
| `config/platform_pass_ids/*.json` | 三平台 pass-id 映射 | 已有 |
| `config/manual_overrides.json` | 手工 override 层 | 已有(目前 `libraries:{}, attractions:{}, passes:{}`) |

**Output 文件**(本 plan 产出,全部入 git):

| 路径 | 形状 | 用途 |
|---|---|---|
| `data/structured/library_catalog.json` | nested by lib_id → passes by slug | 规范化快照 + diff 锚点 |
| `data/structured/libraries.json` | `[{id, name, town, network, platform, card_page, address, geo, eligibility, ...}]` × 59 | 前端图书馆元数据 |
| `data/structured/attractions.json` | `[{slug, name, website, categories, address, geo, original_price, hero_image, ...}]` × ~104 | 前端景点元数据 |
| `data/structured/passes.json` | `[{library_id, attraction_slug, pass_type, discount, source_url, availability}]` × ~1000 | 前端 (馆×景) 优惠矩阵 |

---

## File Structure

```
src/malibbene/
└── build/                            # NEW package
    ├── __init__.py
    ├── catalog.py                    # build_library_catalog()
    ├── libraries.py                  # build_libraries()
    ├── attractions.py                # build_attractions()
    └── passes.py                     # build_passes()

scripts/
└── build.py                          # NEW orchestrator CLI

tests/
├── test_build_catalog.py             # NEW
├── test_build_libraries.py           # NEW
├── test_build_attractions.py         # NEW
└── test_build_passes.py              # NEW
```

每个 builder 文件独立 testable,纯函数(读 dict in,返回 dict out),不直接 IO(IO 在 `scripts/build.py` 里集中处理)。

---

## Task 1 — Build library_catalog.json

**Why:** 取代 plan-1 留下的 `_tmp_attractions_index.json`。merged + normalized catalog 是后续 3 份产物的共同上游。

**Files:**
- Create: `src/malibbene/build/__init__.py`
- Create: `src/malibbene/build/catalog.py`
- Create: `tests/test_build_catalog.py`

### Step 1.1: Write the failing test

Create `tests/test_build_catalog.py`:

```python
"""Test build_library_catalog: merge raw/<platform>/index + normalize."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_raw_root(tmp_path):
    assabet = tmp_path / "raw" / "assabet" / "index"
    assabet.mkdir(parents=True)
    (assabet / "wakefield.json").write_text(json.dumps({
        "scraped_at": "2026-05-13T16:07:09+00:00",
        "meta": {"status_summary": {"ok": 2, "empty": 0, "failed": {}, "total": 2, "ok_ratio": 1.0}},
        "passes": [
            {"slug": "mos", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/",
             "categories": ["Science"], "pass_type": "digital",
             "pass_type_raw": "Digital coupon",
             "benefits_text": "Free admission for up to 4 people.",
             "status": "ok"},
            {"slug": "neaq", "museum_name": "New England Aquarium",
             "address": "1 Central Wharf, Boston, MA 02110",
             "website": "https://www.neaq.org/", "categories": ["Ocean"],
             "pass_type": "physical-coupon",
             "pass_type_raw": "Coupon (pick up at library)",
             "benefits_text": "Pass admits up to 4 people for half price.",
             "status": "ok"},
        ],
    }), encoding="utf-8")
    return tmp_path / "raw"


def test_build_library_catalog_includes_normalized_label(fake_raw_root):
    from malibbene.build.catalog import build_library_catalog

    cat = build_library_catalog(fake_raw_root)

    assert "wakefield" in cat["libraries"]
    wake = cat["libraries"]["wakefield"]
    assert wake["platform"] == "assabet"
    assert "mos" in wake["passes"]
    mos = wake["passes"]["mos"]
    assert mos["pass_type"] == "digital"
    # normalize_benefit should fire and add benefit_label + benefit_class
    assert mos["benefit_class"] == "free"
    assert mos["benefit_label"].lower() == "free"
    neaq = wake["passes"]["neaq"]
    assert neaq["benefit_class"] == "half"


def test_build_library_catalog_attaches_availability(tmp_path):
    """Availability calendar from raw/<platform>/availability/*.json should attach to passes."""
    from malibbene.build.catalog import build_library_catalog

    assabet_idx = tmp_path / "raw" / "assabet" / "index"
    assabet_idx.mkdir(parents=True)
    (assabet_idx / "wakefield.json").write_text(json.dumps({
        "passes": [{"slug": "mos", "museum_name": "MOS", "pass_type": "digital",
                    "benefits_text": "Free.", "status": "ok"}]
    }), encoding="utf-8")
    assabet_avail = tmp_path / "raw" / "assabet" / "availability"
    assabet_avail.mkdir(parents=True)
    (assabet_avail / "wakefield.json").write_text(json.dumps({
        "passes": {"mos": {"status": "ok",
                            "calendar": {"2026-05-13": "available", "2026-05-14": "booked"}}}
    }), encoding="utf-8")

    cat = build_library_catalog(tmp_path / "raw")
    mos = cat["libraries"]["wakefield"]["passes"]["mos"]
    assert mos["calendar"]["2026-05-13"] == "available"
    assert mos["calendar"]["2026-05-14"] == "booked"


def test_build_library_catalog_handles_libcal_via_platform_map(tmp_path):
    """LibCal BPL passes need pass_id → canonical slug via bpl.json (inverted)."""
    from malibbene.build.catalog import build_library_catalog

    libcal = tmp_path / "raw" / "libcal" / "index"
    libcal.mkdir(parents=True)
    (libcal / "bpl.json").write_text(json.dumps({
        "passes": [{"pass_id": "abc123", "slug": "mos-libcal-side",
                    "museum_name": "MOS", "benefits_text": "Free.", "status": "ok",
                    "pass_type": "digital"}]
    }), encoding="utf-8")
    cfg = tmp_path / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "bpl.json").write_text(json.dumps({"passes": {"mos": "abc123"}}), encoding="utf-8")
    (cfg / "libcal.json").write_text(json.dumps({"libraries": {}}), encoding="utf-8")
    (cfg / "museumkey.json").write_text(json.dumps({"libraries": {}, "name_to_benefit": {}}), encoding="utf-8")

    cat = build_library_catalog(tmp_path / "raw", config_root=tmp_path / "config")
    assert "mos" in cat["libraries"]["bpl"]["passes"]


def test_build_library_catalog_writes_meta_summary(fake_raw_root):
    from malibbene.build.catalog import build_library_catalog

    cat = build_library_catalog(fake_raw_root)
    assert "_meta" in cat
    assert cat["_meta"]["n_libraries"] >= 1
    assert cat["_meta"]["n_passes_total"] >= 2
```

### Step 1.2: Run test to verify it fails

Run: `python -m pytest tests/test_build_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: malibbene.build`

### Step 1.3: Write minimal implementation

Create `src/malibbene/build/__init__.py`:

```python
"""Build pipeline: raw/* → structured/{library_catalog, libraries, attractions, passes}.json."""
```

Create `src/malibbene/build/catalog.py`:

```python
"""Merge raw catalog + availability across platforms; normalize benefit labels.

Output is the canonical intermediate `library_catalog.json` — nested by lib_id,
with each pass keyed by canonical benefit slug. Calendar data attached when
available. `manual_overrides.json` is NOT applied here (later step).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from malibbene.common.normalize import normalize_benefit

REPO = Path(__file__).resolve().parents[3]


def _load_platform_maps(config_root: Path) -> dict:
    """Same logic as scripts/build_attractions_index.py — return normalized lookups."""
    bpl_raw = json.loads((config_root / "platform_pass_ids" / "bpl.json").read_text(encoding="utf-8"))
    libcal_raw = json.loads((config_root / "platform_pass_ids" / "libcal.json").read_text(encoding="utf-8"))
    mk_raw = json.loads((config_root / "platform_pass_ids" / "museumkey.json").read_text(encoding="utf-8"))

    # bpl: invert {canonical: pass_id} → {pass_id: canonical}
    bpl_inv = {v: k for k, v in bpl_raw.get("passes", {}).items()}

    # libcal: flatten {libraries.<lib>.passes: {libcal_slug: canonical}} → {lib: {slug: canonical}}
    libcal_lookup = {}
    for lib_id, info in libcal_raw.get("libraries", {}).items():
        libcal_lookup[lib_id] = info.get("passes", {})

    # museumkey: {name_to_benefit, canonical_set}
    mk_n2b = mk_raw.get("name_to_benefit", {})
    return {
        "bpl_inverted": bpl_inv,
        "libcal_by_lib": libcal_lookup,
        "museumkey": {"name_to_benefit": mk_n2b, "canonical_set": set(mk_n2b.values())},
    }


def _canonical_slug(pass_obj: dict, lib_id: str, platform: str, maps: dict) -> str | None:
    if platform == "assabet":
        return pass_obj.get("slug")
    if platform == "libcal":
        if lib_id == "bpl":
            return maps["bpl_inverted"].get(pass_obj.get("pass_id"))
        return maps["libcal_by_lib"].get(lib_id, {}).get(pass_obj.get("slug"))
    if platform == "museumkey":
        slug = pass_obj.get("slug")
        if slug and slug in maps["museumkey"]["canonical_set"]:
            return slug
        return maps["museumkey"]["name_to_benefit"].get(
            (pass_obj.get("museum_name") or "").lower()
        )
    return None


def build_library_catalog(raw_root: Path, *, config_root: Path | None = None) -> dict:
    if config_root is None:
        config_root = REPO / "config"
    maps = _load_platform_maps(config_root)

    libs: dict[str, dict] = {}
    n_unmapped = {"assabet": 0, "libcal": 0, "museumkey": 0}
    n_passes_total = 0

    for platform in ("assabet", "libcal", "museumkey"):
        idx_dir = raw_root / platform / "index"
        avail_dir = raw_root / platform / "availability"
        if not idx_dir.exists():
            continue
        for idx_file in sorted(idx_dir.glob("*.json")):
            lib_id = idx_file.stem
            idx_data = json.loads(idx_file.read_text(encoding="utf-8"))
            avail_data = None
            avail_file = avail_dir / f"{lib_id}.json" if avail_dir.exists() else None
            if avail_file and avail_file.exists():
                avail_data = json.loads(avail_file.read_text(encoding="utf-8"))

            lib_entry = libs.setdefault(lib_id, {
                "platform": platform,
                "scraped_at": idx_data.get("scraped_at"),
                "passes": {},
            })

            for raw_pass in idx_data.get("passes", []):
                if str(raw_pass.get("status", "")).startswith("failed"):
                    continue
                slug = _canonical_slug(raw_pass, lib_id, platform, maps)
                if not slug:
                    n_unmapped[platform] += 1
                    continue
                label, label_class = normalize_benefit(raw_pass.get("benefits_text", "") or "")
                pass_entry = {
                    "museum_name": raw_pass.get("museum_name", ""),
                    "address": raw_pass.get("address", ""),
                    "website": raw_pass.get("website", ""),
                    "categories": list(raw_pass.get("categories", [])),
                    "pass_type": raw_pass.get("pass_type", "unknown"),
                    "pass_type_raw": raw_pass.get("pass_type_raw", ""),
                    "benefits_text": raw_pass.get("benefits_text", ""),
                    "benefit_label": label,
                    "benefit_class": label_class,
                    "source_url": raw_pass.get("url", ""),
                }
                # Attach calendar if availability data exists for this pass
                if avail_data:
                    cal_entry = avail_data.get("passes", {}).get(slug) or avail_data.get("passes", {}).get(raw_pass.get("slug", ""))
                    if cal_entry and cal_entry.get("status") == "ok":
                        pass_entry["calendar"] = cal_entry.get("calendar", {})
                lib_entry["passes"][slug] = pass_entry
                n_passes_total += 1

    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_libraries": len(libs),
            "n_passes_total": n_passes_total,
            "n_unmapped_passes_per_platform": n_unmapped,
        },
        "libraries": libs,
    }
```

### Step 1.4: Run tests to pass

Run: `python -m pytest tests/test_build_catalog.py -v`
Expected: 4 passed

### Step 1.5: Commit (no real run yet — build.py orchestrator wraps later in Task 6)

```bash
git add src/malibbene/build/__init__.py src/malibbene/build/catalog.py tests/test_build_catalog.py
git commit -m "feat(build): merge raw catalogs + normalize_benefit into library_catalog"
```

---

## Task 2 — Build libraries.json

**Files:**
- Create: `src/malibbene/build/libraries.py`
- Create: `tests/test_build_libraries.py`

### Step 2.1: Write the failing test

Create `tests/test_build_libraries.py`:

```python
"""Test build_libraries: merge seeds + addresses + geo into final libraries.json."""
import json
import pytest


def test_build_libraries_merges_address_and_geo():
    from malibbene.build.libraries import build_libraries

    seeds = {
        "libraries": [
            {"id": "wakefield", "name": "Lucius Beebe Memorial Library",
             "town": "Wakefield", "network": "NOBLE", "platform": "assabet",
             "card_page": "https://www.wakefieldlibrary.org/get-a-card/",
             "non_resident_policy_initial": "open_ma_resident",
             "supports_availability": True}
        ]
    }
    addresses = {
        "wakefield": {"lib_id": "wakefield", "status": "ok",
                       "street": "60 Main Street", "city": "Wakefield",
                       "state": "MA", "zip": "01880"}
    }
    geo = {"libraries": {"wakefield": {"ok": True, "lat": 42.5065, "lon": -71.0759}}}

    libs = build_libraries(seeds, addresses, geo)

    assert len(libs["libraries"]) == 1
    w = libs["libraries"][0]
    assert w["id"] == "wakefield"
    assert w["town"] == "Wakefield"
    assert w["address"]["street"] == "60 Main Street"
    assert w["address"]["zip"] == "01880"
    assert w["geo"]["lat"] == 42.5065
    assert w["eligibility"] == "open_ma_resident"


def test_build_libraries_handles_missing_address_and_geo():
    """Libraries without address/geo data should still appear, with null fields."""
    from malibbene.build.libraries import build_libraries

    seeds = {
        "libraries": [
            {"id": "tewksbury", "name": "Tewksbury Public Library", "town": "Tewksbury",
             "platform": "assabet", "network": "MVLC",
             "card_page": "https://www.tewksburypl.org/",
             "non_resident_policy_initial": "open_ma_resident",
             "supports_availability": True}
        ]
    }
    libs = build_libraries(seeds, addresses={}, geo={"libraries": {}})

    t = libs["libraries"][0]
    assert t["address"] is None
    assert t["geo"] is None
    assert t["id"] == "tewksbury"


def test_build_libraries_includes_meta_summary():
    from malibbene.build.libraries import build_libraries
    seeds = {"libraries": []}
    out = build_libraries(seeds, addresses={}, geo={"libraries": {}})
    assert "_meta" in out
    assert out["_meta"]["n_libraries"] == 0
    assert "built_at" in out["_meta"]
```

### Step 2.2: Run test to fail, then implement

Run: `python -m pytest tests/test_build_libraries.py -v` → ModuleNotFoundError

Create `src/malibbene/build/libraries.py`:

```python
"""Build final libraries.json from seeds + address/geo data."""
from __future__ import annotations

import datetime as dt


def _address_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    return {
        "street": rec.get("street"),
        "city": rec.get("city"),
        "state": rec.get("state"),
        "zip": rec.get("zip"),
    }


def _geo_block(rec: dict | None) -> dict | None:
    if not rec or not rec.get("ok"):
        return None
    return {"lat": rec["lat"], "lon": rec["lon"]}


def build_libraries(seeds: dict, addresses: dict, geo: dict) -> dict:
    """Return {libraries: [...], _meta: {...}}.

    Args:
        seeds: parsed config/library_seeds.json
        addresses: dict mapping lib_id → parsed data/raw/library_addresses/<lib_id>.json
        geo: parsed data/structured/geo.json
    """
    lib_geo = geo.get("libraries", {})
    out = []
    for s in seeds.get("libraries", []):
        lib_id = s["id"]
        out.append({
            "id": lib_id,
            "name": s.get("name", ""),
            "town": s.get("town", ""),
            "network": s.get("network", ""),
            "platform": s.get("platform", ""),
            "card_page": s.get("card_page", ""),
            "eligibility": s.get("non_resident_policy_initial", "unknown"),
            "supports_availability": s.get("supports_availability", False),
            "address": _address_block(addresses.get(lib_id)),
            "geo": _geo_block(lib_geo.get(lib_id)),
        })
    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_libraries": len(out),
            "n_with_address": sum(1 for x in out if x["address"]),
            "n_with_geo": sum(1 for x in out if x["geo"]),
        },
        "libraries": out,
    }
```

### Step 2.3: Tests pass, commit

`python -m pytest tests/test_build_libraries.py -v` → 3 passed

```bash
git add src/malibbene/build/libraries.py tests/test_build_libraries.py
git commit -m "feat(build): assemble libraries.json from seeds + addresses + geo"
```

---

## Task 3 — Build attractions.json

**Files:**
- Create: `src/malibbene/build/attractions.py`
- Create: `tests/test_build_attractions.py`

### Step 3.1: Write the failing test

Create `tests/test_build_attractions.py`:

```python
"""Test build_attractions: collect all attractions from catalog + enrich."""
import pytest


def test_build_attractions_merges_price_image_geo():
    from malibbene.build.attractions import build_attractions

    catalog = {
        "libraries": {
            "wakefield": {
                "passes": {
                    "mos": {"museum_name": "Museum of Science",
                            "address": "1 Science Park, Boston, MA 02114",
                            "website": "https://www.mos.org/",
                            "categories": ["Science", "Family"]}
                }
            },
            "reading": {
                "passes": {
                    "mos": {"museum_name": "Museum of Science",
                            "address": "1 Science Park, Boston, MA 02114",
                            "website": "https://www.mos.org/",
                            "categories": ["Science"]}
                }
            }
        }
    }
    prices = {"mos": {"slug": "mos", "status": "ok",
                       "adult": 33, "child": 28, "senior": 29, "student": None,
                       "family": None, "free_under_age": None, "notes": None,
                       "source_url": "https://www.mos.org/visit"}}
    images = {"mos": {"slug": "mos", "status": "ok",
                       "og_image_url": "https://www.mos.org/og.jpg",
                       "local_path": "static/images/mos.jpg"}}
    geo = {"attractions": {"mos": {"ok": True, "lat": 42.367, "lon": -71.071}}}

    out = build_attractions(catalog, prices, images, geo)

    assert len(out["attractions"]) == 1
    a = out["attractions"][0]
    assert a["slug"] == "mos"
    assert a["museum_name"] == "Museum of Science"
    # categories union across libraries (Science, Family from wakefield; Science from reading)
    assert set(a["categories"]) == {"Science", "Family"}
    # sources from BOTH libraries
    assert set(a["sources"]) == {"wakefield", "reading"}
    # price merged
    assert a["original_price"]["adult"] == 33
    assert a["original_price"]["child"] == 28
    # image merged
    assert a["hero_image"]["og_image_url"] == "https://www.mos.org/og.jpg"
    # geo merged
    assert a["geo"]["lat"] == 42.367


def test_build_attractions_handles_missing_enrichments():
    """Attractions without price/image/geo should still appear with null fields."""
    from malibbene.build.attractions import build_attractions

    catalog = {
        "libraries": {
            "cohasset": {
                "passes": {
                    "obscure-museum": {"museum_name": "Obscure", "address": "", "website": "",
                                       "categories": ["History"]}
                }
            }
        }
    }
    out = build_attractions(catalog, prices={}, images={}, geo={"attractions": {}})

    a = out["attractions"][0]
    assert a["slug"] == "obscure-museum"
    assert a["original_price"] is None
    assert a["hero_image"] is None
    assert a["geo"] is None


def test_build_attractions_meta():
    from malibbene.build.attractions import build_attractions
    out = build_attractions({"libraries": {}}, {}, {}, {"attractions": {}})
    assert out["_meta"]["n_attractions"] == 0
    assert "built_at" in out["_meta"]
```

### Step 3.2: Implementation

Create `src/malibbene/build/attractions.py`:

```python
"""Build final attractions.json from catalog + price + image + geo enrichments."""
from __future__ import annotations

import datetime as dt


def _price_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    return {
        "adult": rec.get("adult"),
        "child": rec.get("child"),
        "senior": rec.get("senior"),
        "student": rec.get("student"),
        "family": rec.get("family"),
        "free_under_age": rec.get("free_under_age"),
        "notes": rec.get("notes"),
        "source_url": rec.get("source_url"),
    }


def _image_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    return {
        "og_image_url": rec.get("og_image_url"),
        "local_path": rec.get("local_path"),
    }


def _geo_block(rec: dict | None) -> dict | None:
    if not rec or not rec.get("ok"):
        return None
    return {"lat": rec["lat"], "lon": rec["lon"]}


def build_attractions(catalog: dict, prices: dict, images: dict, geo: dict) -> dict:
    """Return {attractions: [...], _meta: {...}}.

    Args:
        catalog: parsed library_catalog.json (Task 1 output)
        prices: dict slug → parsed data/raw/attraction_prices/<slug>.json
        images: dict slug → parsed data/raw/attraction_images/<slug>.json
        geo: parsed data/structured/geo.json
    """
    attr_geo = geo.get("attractions", {})
    accum: dict[str, dict] = {}
    for lib_id, lib_entry in catalog.get("libraries", {}).items():
        for slug, p in lib_entry.get("passes", {}).items():
            entry = accum.setdefault(slug, {
                "slug": slug,
                "museum_name": p.get("museum_name", ""),
                "address": p.get("address", ""),
                "website": p.get("website", ""),
                "categories": [],
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

    out = []
    for slug, base in accum.items():
        out.append({
            **base,
            "original_price": _price_block(prices.get(slug)),
            "hero_image": _image_block(images.get(slug)),
            "geo": _geo_block(attr_geo.get(slug)),
        })

    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_attractions": len(out),
            "n_with_price": sum(1 for x in out if x["original_price"]),
            "n_with_image": sum(1 for x in out if x["hero_image"]),
            "n_with_geo": sum(1 for x in out if x["geo"]),
        },
        "attractions": out,
    }
```

### Step 3.3: Tests + commit

`python -m pytest tests/test_build_attractions.py -v` → 3 passed

```bash
git add src/malibbene/build/attractions.py tests/test_build_attractions.py
git commit -m "feat(build): assemble attractions.json from catalog + prices + images + geo"
```

---

## Task 4 — Build passes.json

**Files:**
- Create: `src/malibbene/build/passes.py`
- Create: `tests/test_build_passes.py`

### Step 4.1: Write the failing test

Create `tests/test_build_passes.py`:

```python
"""Test build_passes: flatten (lib × attraction) matrix with discount + calendar."""


def test_build_passes_flattens_lib_x_attraction():
    from malibbene.build.passes import build_passes

    catalog = {
        "libraries": {
            "wakefield": {
                "passes": {
                    "mos": {"pass_type": "digital", "benefit_label": "Free",
                            "benefit_class": "free", "benefits_text": "Free for 4 people",
                            "source_url": "https://wakefieldlibrary.assabetinteractive.com/pass/mos",
                            "pass_type_raw": "Digital coupon",
                            "calendar": {"2026-05-13": "available", "2026-05-14": "booked"}}
                }
            },
            "reading": {
                "passes": {
                    "mos": {"pass_type": "physical-coupon", "benefit_label": "50% off",
                            "benefit_class": "half", "benefits_text": "Half price for 4",
                            "source_url": "https://readingpl.assabetinteractive.com/pass/mos",
                            "pass_type_raw": "Coupon (pick up at library)",
                            "calendar": {}}
                }
            }
        }
    }

    out = build_passes(catalog)

    assert len(out["passes"]) == 2
    by_lib = {p["library_id"]: p for p in out["passes"]}
    w = by_lib["wakefield"]
    assert w["attraction_slug"] == "mos"
    assert w["pass_type"] == "digital"
    assert w["discount"]["class"] == "free"
    assert w["discount"]["label"] == "Free"
    assert w["discount"]["raw"] == "Free for 4 people"
    assert w["availability"]["2026-05-13"] == "available"
    r = by_lib["reading"]
    assert r["pass_type"] == "physical-coupon"
    assert r["discount"]["class"] == "half"


def test_build_passes_handles_missing_calendar():
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {"x": {"passes": {"y": {"pass_type": "digital",
                                                      "benefit_label": "Free",
                                                      "benefit_class": "free",
                                                      "benefits_text": "",
                                                      "source_url": "",
                                                      "pass_type_raw": ""}}}}}
    out = build_passes(catalog)
    assert out["passes"][0]["availability"] is None


def test_build_passes_meta_counts():
    from malibbene.build.passes import build_passes
    out = build_passes({"libraries": {}})
    assert out["_meta"]["n_passes"] == 0
```

### Step 4.2: Implementation

Create `src/malibbene/build/passes.py`:

```python
"""Build final passes.json — flat list of (library × attraction) pass entries."""
from __future__ import annotations

import datetime as dt


def build_passes(catalog: dict) -> dict:
    """Return {passes: [...], _meta: {...}}.

    Each element of `passes` is a (library_id, attraction_slug) row carrying
    the discount, pass_type, source_url, and availability calendar.
    """
    out = []
    for lib_id, lib_entry in catalog.get("libraries", {}).items():
        for slug, p in lib_entry.get("passes", {}).items():
            cal = p.get("calendar")
            out.append({
                "library_id": lib_id,
                "attraction_slug": slug,
                "pass_type": p.get("pass_type", "unknown"),
                "pass_type_raw": p.get("pass_type_raw", ""),
                "discount": {
                    "class": p.get("benefit_class", "unknown"),
                    "label": p.get("benefit_label", ""),
                    "raw": p.get("benefits_text", ""),
                },
                "source_url": p.get("source_url", ""),
                "availability": cal if cal else None,
            })
    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_passes": len(out),
            "n_with_availability": sum(1 for x in out if x["availability"]),
        },
        "passes": out,
    }
```

### Step 4.3: Tests + commit

`python -m pytest tests/test_build_passes.py -v` → 3 passed

```bash
git add src/malibbene/build/passes.py tests/test_build_passes.py
git commit -m "feat(build): assemble passes.json from catalog (lib x attraction matrix)"
```

---

## Task 5 — Apply manual_overrides + orchestrator CLI

**Files:**
- Create: `scripts/build.py`

### Step 5.1: Add overrides logic in build.py

Create `scripts/build.py`:

```python
"""Orchestrate the full build: raw/* → structured/{library_catalog, libraries, attractions, passes}.json.

Manual overrides from config/manual_overrides.json are applied LAST so they always win.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.build.catalog import build_library_catalog
from malibbene.build.libraries import build_libraries
from malibbene.build.attractions import build_attractions
from malibbene.build.passes import build_passes


def _load_dir_jsons(d: Path, key: str = "slug") -> dict:
    """Load every *.json (except _* files) in d, return dict keyed by basename."""
    out = {}
    if not d.exists():
        return out
    for f in d.glob("*.json"):
        if f.name.startswith("_"):
            continue
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


def _apply_overrides(data: dict, key_field: str, list_key: str, overrides: dict) -> None:
    """Mutate data[list_key] entries in place using overrides keyed by entry[key_field]."""
    if not overrides:
        return
    by_key = {x[key_field]: x for x in data.get(list_key, [])}
    for k, patch in overrides.items():
        if k in by_key:
            by_key[k].update(patch)


def _apply_pass_overrides(passes_doc: dict, overrides: dict) -> None:
    """Pass overrides are nested: {lib_id: {slug: {...}}}."""
    if not overrides:
        return
    for p in passes_doc.get("passes", []):
        lib_patches = overrides.get(p["library_id"])
        if lib_patches:
            patch = lib_patches.get(p["attraction_slug"])
            if patch:
                p.update(patch)


def main() -> int:
    raw_root = REPO / "data" / "raw"
    structured = REPO / "data" / "structured"
    config_root = REPO / "config"
    structured.mkdir(parents=True, exist_ok=True)

    # 1. library_catalog.json (intermediate)
    print("Building library_catalog.json...")
    catalog = build_library_catalog(raw_root, config_root=config_root)
    (structured / "library_catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {catalog['_meta']['n_libraries']} libraries, {catalog['_meta']['n_passes_total']} passes")

    # Load enrichment data
    addresses = _load_dir_jsons(raw_root / "library_addresses")
    prices = _load_dir_jsons(raw_root / "attraction_prices")
    images = _load_dir_jsons(raw_root / "attraction_images")
    seeds = json.loads((config_root / "library_seeds.json").read_text(encoding="utf-8"))
    geo = json.loads((structured / "geo.json").read_text(encoding="utf-8"))
    overrides = json.loads((config_root / "manual_overrides.json").read_text(encoding="utf-8"))

    # 2. libraries.json
    print("Building libraries.json...")
    libs_doc = build_libraries(seeds, addresses, geo)
    _apply_overrides(libs_doc, "id", "libraries", overrides.get("libraries", {}))
    (structured / "libraries.json").write_text(
        json.dumps(libs_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {libs_doc['_meta']['n_libraries']} libraries "
          f"({libs_doc['_meta']['n_with_address']} addr, {libs_doc['_meta']['n_with_geo']} geo)")

    # 3. attractions.json
    print("Building attractions.json...")
    attr_doc = build_attractions(catalog, prices, images, geo)
    _apply_overrides(attr_doc, "slug", "attractions", overrides.get("attractions", {}))
    (structured / "attractions.json").write_text(
        json.dumps(attr_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {attr_doc['_meta']['n_attractions']} attractions "
          f"({attr_doc['_meta']['n_with_price']} price, {attr_doc['_meta']['n_with_image']} img, "
          f"{attr_doc['_meta']['n_with_geo']} geo)")

    # 4. passes.json
    print("Building passes.json...")
    passes_doc = build_passes(catalog)
    _apply_pass_overrides(passes_doc, overrides.get("passes", {}))
    (structured / "passes.json").write_text(
        json.dumps(passes_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {passes_doc['_meta']['n_passes']} passes "
          f"({passes_doc['_meta']['n_with_availability']} with calendar)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Step 5.2: Real run

Run: `python scripts/build.py`

Expected output:
```
Building library_catalog.json...
  ~50-59 libraries, ~1000+ passes
Building libraries.json...
  59 libraries (55 addr, 55 geo)
Building attractions.json...
  ~104 attractions (54 price, 47 img, 75 geo)
Building passes.json...
  ~1000 passes (~700+ with calendar)
```

If any tier looks wildly off (e.g., 0 attractions, or 0 libraries), STOP and inspect.

### Step 5.3: Spot check 3 files

```bash
python -c "
import json
for name in ['library_catalog', 'libraries', 'attractions', 'passes']:
    d = json.load(open(f'data/structured/{name}.json', encoding='utf-8'))
    print(f'{name}: {d[\"_meta\"]}')
"
```

Check each `_meta` block has reasonable counts.

### Step 5.4: Cleanup _tmp_attractions_index.json (superseded by attractions.json)

Remove the temporary file:
```bash
rm data/structured/_tmp_attractions_index.json
```
(It's gitignored, so no commit needed for the removal itself.)

### Step 5.5: Commit

```bash
git add scripts/build.py data/structured/library_catalog.json data/structured/libraries.json data/structured/attractions.json data/structured/passes.json
git commit -m "feat(build): orchestrator CLI produces 4 structured JSONs + apply overrides"
```

---

## Task 6 — Verification & docs

### Step 6.1: Run full test suite

`python -m pytest tests/ -v` → all tests pass (previously 98, now +12 from this plan = ~110)

### Step 6.2: Sanity-check output files

```bash
python -c "
import json
libs = json.load(open('data/structured/libraries.json', encoding='utf-8'))
attrs = json.load(open('data/structured/attractions.json', encoding='utf-8'))
passes = json.load(open('data/structured/passes.json', encoding='utf-8'))

# Find Wakefield's MOS pass
w = next(l for l in libs['libraries'] if l['id'] == 'wakefield')
print('Wakefield:', w['name'], '|', w['address'])
mos = next((a for a in attrs['attractions'] if a['slug'] == 'museum-of-science'), None)
if mos:
    print('MOS:', mos['museum_name'], '| price', mos.get('original_price'), '| geo', mos.get('geo'))
wak_mos = [p for p in passes['passes'] if p['library_id'] == 'wakefield' and p['attraction_slug'] == 'museum-of-science']
print(f'Wakefield × MOS passes: {len(wak_mos)}')
if wak_mos:
    print('  discount:', wak_mos[0]['discount'])
    print('  pass_type:', wak_mos[0]['pass_type'])
"
```

Verify reasonable data appears.

### Step 6.3: Update CLAUDE.md

Find the section that lists `data/structured/` files and update:

```markdown
├── data/structured/
│   ├── library_catalog.json       # 中间规范化快照(plan-2 产出)
│   ├── libraries.json             # 59 馆 final metadata
│   ├── attractions.json           # ~104 景点 final metadata
│   ├── passes.json                # (馆 × 景点) 优惠矩阵
│   └── geo.json                   # 全 entity 经纬度(plan-1 产出)
```

### Step 6.4: Final commit

```bash
git add CLAUDE.md
git commit -m "docs: reflect plan-2 outputs in repo layout section"
```

---

## Verification Summary

After all 6 tasks:

| Artifact | Path | Expected |
|---|---|---|
| Test count | `tests/test_build_*.py` | 13 tests (4+3+3+3) |
| Library catalog (intermediate) | `data/structured/library_catalog.json` | ~50-59 libraries, ~1000+ pass entries with `benefit_label`/`benefit_class`/`calendar` |
| Final libraries | `data/structured/libraries.json` | 59 entries with address(~55) + geo(~55) |
| Final attractions | `data/structured/attractions.json` | ~104 entries with price(~54) + image(~47) + geo(~75) + sources list |
| Final passes | `data/structured/passes.json` | ~1000+ rows (lib × attraction) with discount tier + availability |
| All commits | git log | 6-7 commits since plan-1 |
| All tests pass | `pytest tests/` | ~110 total, 100% pass |

After this, frontend (plan-3 + plan-4) can directly consume the 3 final JSONs.
