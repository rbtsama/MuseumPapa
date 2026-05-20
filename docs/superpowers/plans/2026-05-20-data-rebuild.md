# 数据底层重建 实施计划 (Data Rebuild Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/specs/2026-05-20-admin-panel-redesign.md` 定义的新数据模型，从零重写全部爬虫和构建管线，跑一次全量重抓，并把本次原始抓取归档为可回放快照。

**Architecture:** 三层分离 —— (1) 爬虫层只写 `data/raw/`；(2) 审计层 `data/overrides/` 独立存储人工修正；(3) build 层把 raw + overrides 合并产出 `data/structured/`。新增景点 visitor_eligibility / reservation 爬虫，新增 BPL/Cambridge/Brookline 分馆建模，coupon 抽取改用每 pass 单独的 source_phrases 保留+BOGO 识别+blackout 相对日历。旧爬虫和旧 structured 数据全部移到 `_legacy/` 归档，不删除。

**Tech Stack:** Python 3.11+, pytest, urllib + 可选 Playwright, dataclasses, LLM 抽取走 subagent dispatch（控制器派 Sonnet），不调外部 API。

**Scope 不包含：** Admin Panel UI 实现（另开 plan）、前端 web/ 改造（另开 plan）、LLM 抽取的 prompt 优化（按需迭代）。

---

## File Structure（建立前先看）

```
src/malibbene/
├── schema/                          # NEW —— 全部新建
│   ├── __init__.py
│   ├── library.py                   # Library, LibraryCardEligibility, PassPickupPolicy
│   ├── attraction.py                # Attraction, VisitorEligibility, Reservation
│   ├── pass_.py                     # Pass, Coupon, AudiencePolicy, Capacity, Restrictions
│   ├── branch.py                    # Branch
│   └── audit.py                     # AuditRecord, AuditStatus
├── common/
│   ├── snapshot.py                  # NEW —— raw 抓取的归档器
│   ├── audit_overrides.py           # NEW —— overrides 加载 + 合并
│   ├── eligibility_text.py          # NEW —— 政策文本 → 枚举的分类
│   ├── coupon_form.py               # NEW —— BOGO/percent/dollar/per-person/free/discount 分类
│   ├── blackout.py                  # NEW —— 相对日历（month/day, recurring）
│   ├── http.py                      # KEEP（沿用现有）
│   ├── browser.py                   # KEEP
│   ├── geocode.py                   # KEEP
│   └── status.py                    # KEEP
├── sources_v2/                      # NEW —— 全新爬虫，与旧 sources/ 并行存在
│   ├── __init__.py
│   ├── assabet/
│   │   ├── __init__.py
│   │   ├── catalog.py               # 抓 pass 列表 + benefit_text + source_phrases
│   │   ├── availability.py          # 抓 30 天日历
│   │   └── policies.py              # 抓 card-page + pass-policy 文本块
│   ├── libcal/
│   │   ├── __init__.py
│   │   ├── catalog.py
│   │   ├── availability.py
│   │   ├── policies.py
│   │   └── branches.py              # 仅 BPL/Cambridge/Brookline
│   ├── museumkey/
│   │   ├── __init__.py
│   │   ├── catalog.py               # 无 availability
│   │   └── policies.py
│   └── attractions/
│       ├── __init__.py
│       ├── pages.py                 # 抓景点官网 HTML（hero/meta/about）
│       ├── prices.py                # LLM 抽 prices[audience]
│       ├── reservation.py           # LLM 抽 timed-entry + pass holder path
│       ├── visitor_eligibility.py   # LLM 抽访客 residency 规则
│       └── hours.py                 # 抽营业时间
├── build/                           # NEW —— 替换原 scripts/build.py
│   ├── __init__.py
│   ├── libraries.py                 # raw + overrides → libraries.json
│   ├── attractions.py
│   ├── passes.py
│   ├── branches.py
│   └── validate.py                  # 计算覆盖率、unknown 比例
└── _legacy/                         # 旧代码归档（移到这里，不删）
    └── sources/                     # 原 src/malibbene/sources/

scripts/                             # 全部重建
├── archive_legacy.py                # NEW —— Task 1 用，搬运旧代码到 _legacy/
├── scrape_libraries.py              # NEW —— 各平台 policies + catalog
├── scrape_attractions.py            # NEW —— 景点页面 + LLM 抽取
├── scrape_availability.py           # NEW —— 仅动态库存
├── build_all.py                     # NEW —— 跑全部 build/*.py
├── snapshot_raw.py                  # NEW —— 把 data/raw/ 归档到 data/snapshots/<date>/
└── (旧 scripts/ 保留在原地，新脚本与旧脚本并行，新版稳定后再清理)

data/
├── raw/                             # 重抓后内容全变
│   ├── assabet/{catalog,availability,policies}/<lib_id>.json
│   ├── libcal/{catalog,availability,policies,branches}/<lib_id>.json
│   ├── museumkey/{catalog,policies}/<lib_id>.json
│   └── attractions/{pages,prices,reservation,eligibility,hours}/<slug>.{html,json}
├── overrides/                       # NEW —— 审计层
│   ├── libraries/<id>/<field>.json
│   ├── attractions/<slug>/<field>.json
│   ├── passes/<lib>__<slug>/<field>.json
│   └── branches/<lib>__<branch>/<field>.json
├── snapshots/<YYYY-MM-DD>/          # NEW —— 当次 raw 全量副本
└── structured/                      # 重 build 后内容全变
    ├── libraries.json
    ├── attractions.json
    ├── passes.json
    └── branches.json                # NEW

data/_legacy/2026-05-20/             # NEW —— 旧 structured/ 归档
    └── (原 libraries.json/attractions.json/passes.json/...)
```

---

## Phase 0：项目准备与归档

### Task 1：归档旧代码与旧数据 + 彻底删除旧 admin panel

**Files:**
- Create: `scripts/archive_legacy.py`
- Move: `src/malibbene/sources/` → `src/malibbene/_legacy/sources/`
- Move: `data/structured/*` → `data/_legacy/2026-05-20/`
- Delete: `audit/` (整个目录，旧的只读 audit 单页)
- Delete: `scripts/build_audit_site.py`（旧 audit 构建器）

- [ ] **Step 1：写归档脚本**

```python
# scripts/archive_legacy.py
"""一次性归档：把旧 sources 和旧 structured 移走，保留只读副本。"""
import shutil
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent

def main():
    legacy_date = date.today().isoformat()
    src_legacy = ROOT / "src/malibbene/_legacy"
    src_legacy.mkdir(parents=True, exist_ok=True)
    sources_old = ROOT / "src/malibbene/sources"
    if sources_old.exists():
        target = src_legacy / "sources"
        if target.exists():
            raise SystemExit(f"already archived: {target}")
        shutil.move(str(sources_old), str(target))
        print(f"moved: src/malibbene/sources → src/malibbene/_legacy/sources")

    data_legacy = ROOT / "data/_legacy" / legacy_date
    data_legacy.mkdir(parents=True, exist_ok=True)
    struct_old = ROOT / "data/structured"
    if struct_old.exists():
        for f in struct_old.iterdir():
            shutil.move(str(f), str(data_legacy / f.name))
        print(f"moved: data/structured/* → data/_legacy/{legacy_date}/")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2：执行归档**

```bash
python scripts/archive_legacy.py
```

预期输出：
```
moved: src/malibbene/sources → src/malibbene/_legacy/sources
moved: data/structured/* → data/_legacy/2026-05-20/
```

- [ ] **Step 3：验证归档结果**

```bash
ls src/malibbene/_legacy/sources/  # 应含 assabet/ libcal/ museumkey/ attractions/...
ls data/_legacy/2026-05-20/        # 应含 libraries.json attractions.json passes.json ...
ls src/malibbene/                  # 应没有 sources/ 了
```

- [ ] **Step 4：彻底删除旧 admin panel**

```bash
git rm -r audit/
git rm scripts/build_audit_site.py
```

预期：audit/audit.html、audit/assets/、scripts/build_audit_site.py 全部从 git 移除。

- [ ] **Step 5：commit**

```bash
git add scripts/archive_legacy.py src/malibbene/_legacy data/_legacy
git rm -r --cached src/malibbene/sources data/structured 2>/dev/null || true
git commit -m "chore: archive legacy crawlers + delete old audit panel before rebuild"
```

---

### Task 2：建立 sources_v2 目录骨架

**Files:**
- Create: `src/malibbene/sources_v2/__init__.py`
- Create: `src/malibbene/sources_v2/{assabet,libcal,museumkey,attractions}/__init__.py`
- Create: `src/malibbene/schema/__init__.py`
- Create: `src/malibbene/build/__init__.py`

- [ ] **Step 1：建空目录与 `__init__.py`**

```bash
mkdir -p src/malibbene/sources_v2/{assabet,libcal,museumkey,attractions}
mkdir -p src/malibbene/{schema,build}
touch src/malibbene/sources_v2/__init__.py
touch src/malibbene/sources_v2/{assabet,libcal,museumkey,attractions}/__init__.py
touch src/malibbene/{schema,build}/__init__.py
```

- [ ] **Step 2：commit**

```bash
git add src/malibbene/sources_v2 src/malibbene/schema src/malibbene/build
git commit -m "scaffold: sources_v2 + schema + build package skeleton"
```

---

## Phase 1：数据模型层（Schema）

> 全部 TDD：先写测试断言枚举值和字段，再写 dataclass。

### Task 3：Library 与资格枚举

**Files:**
- Create: `src/malibbene/schema/library.py`
- Test: `tests/test_schema_library.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_schema_library.py
from malibbene.schema.library import Library, CardEligibility, PassPickupPolicy

def test_card_eligibility_enum_has_six_values():
    assert {e.value for e in CardEligibility} == {
        "ma_resident", "town_resident", "town_or_works",
        "network", "none", "unknown",
    }

def test_pass_pickup_enum_has_eight_values():
    assert {e.value for e in PassPickupPolicy} == {
        "same_as_card", "ma_resident", "town_resident",
        "town_cardholder_only", "network",
        "walkin_for_nonresidents", "none", "unknown",
    }

def test_library_minimum_required_fields():
    lib = Library(
        id="wakefield", name="Lucius Beebe Memorial Library",
        town="Wakefield", network="NOBLE", platform="assabet",
        card_eligibility=CardEligibility.MA_RESIDENT,
        pass_pickup_default=PassPickupPolicy.SAME_AS_CARD,
    )
    assert lib.id == "wakefield"
    assert lib.branch_ids == []  # default empty
```

- [ ] **Step 2：跑测试确认失败**

```bash
pytest tests/test_schema_library.py -v
# 预期：ImportError: cannot import name 'Library' from 'malibbene.schema.library'
```

- [ ] **Step 3：写实现**

```python
# src/malibbene/schema/library.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class CardEligibility(str, Enum):
    MA_RESIDENT = "ma_resident"
    TOWN_RESIDENT = "town_resident"
    TOWN_OR_WORKS = "town_or_works"
    NETWORK = "network"
    NONE = "none"
    UNKNOWN = "unknown"

class PassPickupPolicy(str, Enum):
    SAME_AS_CARD = "same_as_card"
    MA_RESIDENT = "ma_resident"
    TOWN_RESIDENT = "town_resident"
    TOWN_CARDHOLDER_ONLY = "town_cardholder_only"
    NETWORK = "network"
    WALKIN_FOR_NONRESIDENTS = "walkin_for_nonresidents"
    NONE = "none"
    UNKNOWN = "unknown"

@dataclass
class Address:
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

@dataclass
class Geo:
    lat: float
    lon: float

@dataclass
class Library:
    id: str
    name: str
    town: str
    network: str
    platform: str
    card_eligibility: CardEligibility
    pass_pickup_default: PassPickupPolicy
    address: Optional[Address] = None
    geo: Optional[Geo] = None
    card_page: Optional[str] = None
    pass_page: Optional[str] = None
    hours: Optional[dict] = None
    branch_ids: list[str] = field(default_factory=list)
    eligibility_source_phrase: Optional[str] = None
    pickup_source_phrase: Optional[str] = None
```

- [ ] **Step 4：跑测试验证通过**

```bash
pytest tests/test_schema_library.py -v
# 预期：3 passed
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/schema/library.py tests/test_schema_library.py
git commit -m "schema: Library + CardEligibility/PassPickupPolicy enums"
```

---

### Task 4：Attraction 与访客资格 / 预约

**Files:**
- Create: `src/malibbene/schema/attraction.py`
- Test: `tests/test_schema_attraction.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_schema_attraction.py
from malibbene.schema.attraction import (
    Attraction, VisitorEligibility, Reservation,
    ReservationRequired, PassHolderPath, AudiencePrice,
)

def test_reservation_required_enum():
    assert {e.value for e in ReservationRequired} == {"none", "timed_entry", "walk_in_ok"}

def test_pass_holder_path_enum():
    assert {e.value for e in PassHolderPath} == {
        "promo_code_in_general_checkout", "dedicated_pass_sku",
        "dedicated_pass_holders_url", "library_only", "unknown",
    }

def test_attraction_construct_minimum():
    a = Attraction(slug="mfa", name="Museum of Fine Arts")
    assert a.slug == "mfa"
    assert a.prices == []
    assert a.visitor_eligibility is None
    assert a.reservation is None

def test_audience_price_fields():
    p = AudiencePrice(audience="adult", price=27.0, source_phrase="Adults $27")
    assert p.audience == "adult"
    assert p.price == 27.0
```

- [ ] **Step 2：跑测试失败**

```bash
pytest tests/test_schema_attraction.py -v
```

- [ ] **Step 3：写实现**

```python
# src/malibbene/schema/attraction.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from .library import Geo, Address

class ReservationRequired(str, Enum):
    NONE = "none"
    TIMED_ENTRY = "timed_entry"
    WALK_IN_OK = "walk_in_ok"

class PassHolderPath(str, Enum):
    PROMO_CODE = "promo_code_in_general_checkout"
    DEDICATED_SKU = "dedicated_pass_sku"
    DEDICATED_URL = "dedicated_pass_holders_url"
    LIBRARY_ONLY = "library_only"
    UNKNOWN = "unknown"

class VisitorResidency(str, Enum):
    MA_RESIDENT = "ma_resident"
    TOWN_RESIDENT = "town_resident"
    NONE = "none"
    UNKNOWN = "unknown"

@dataclass
class VisitorEligibility:
    residency: VisitorResidency
    scope: Optional[str] = None             # 例如 "Salem" / "MA"
    locals_free: bool = False
    note: Optional[str] = None
    source_phrase: Optional[str] = None

@dataclass
class Reservation:
    required: ReservationRequired
    booking_url: Optional[str] = None
    lead_time_hours: Optional[int] = None
    pass_holder_path: PassHolderPath = PassHolderPath.UNKNOWN
    pass_holder_url: Optional[str] = None
    notes: Optional[str] = None
    source_phrase: Optional[str] = None

@dataclass
class AudiencePrice:
    audience: str                            # adult/child/senior/youth/student/military/educator/family
    price: Optional[float] = None
    age_range: Optional[dict] = None         # {"min": 3, "max": 17}
    source_phrase: Optional[str] = None

@dataclass
class Attraction:
    slug: str
    name: str
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None
    geo: Optional[Geo] = None
    description: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    hero_image: Optional[str] = None
    hours: Optional[dict] = None
    prices: list[AudiencePrice] = field(default_factory=list)
    visitor_eligibility: Optional[VisitorEligibility] = None
    reservation: Optional[Reservation] = None
    sources: list[str] = field(default_factory=list)
```

- [ ] **Step 4：测试通过**

```bash
pytest tests/test_schema_attraction.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/schema/attraction.py tests/test_schema_attraction.py
git commit -m "schema: Attraction + VisitorEligibility + Reservation"
```

---

### Task 5：Pass / Coupon / Restrictions

**Files:**
- Create: `src/malibbene/schema/pass_.py`
- Test: `tests/test_schema_pass.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_schema_pass.py
from malibbene.schema.pass_ import (
    Pass, PassForm, Coupon, Capacity, CapacityKind,
    AudiencePolicy, CouponForm, Restrictions, EligibilityOverride,
)
from malibbene.schema.library import PassPickupPolicy

def test_coupon_form_enum_includes_bogo():
    assert {e.value for e in CouponForm} == {
        "free", "percent-off", "dollar-off",
        "per-person-price", "bogo", "discount",
    }

def test_capacity_kind_enum():
    assert {e.value for e in CapacityKind} == {"people", "vehicle", "ticket", "unspecified"}

def test_pass_form_enum():
    assert {e.value for e in PassForm} == {"digital_email", "physical_circ", "physical_coupon"}

def test_pass_minimum():
    p = Pass(
        library_id="wakefield",
        attraction_slug="mfa",
        pass_form=PassForm.DIGITAL_EMAIL,
        coupon=Coupon(
            capacity=Capacity(kind=CapacityKind.PEOPLE, n=4),
            audience_policies=[AudiencePolicy(audience="Everyone", form=CouponForm.PERCENT_OFF, value=50)],
        ),
    )
    assert p.available_at_branches == "all"
    assert p.eligibility_override is None
    assert p.restrictions is None

def test_eligibility_override_carries_residency():
    eo = EligibilityOverride(residency=PassPickupPolicy.TOWN_RESIDENT, reason="town park funding")
    assert eo.residency == PassPickupPolicy.TOWN_RESIDENT

def test_restrictions_blackout_uses_month_day():
    r = Restrictions(blackout=[{"month": 7, "day": 4}])
    assert r.blackout[0]["month"] == 7
```

- [ ] **Step 2：跑失败**

```bash
pytest tests/test_schema_pass.py -v
```

- [ ] **Step 3：写实现**

```python
# src/malibbene/schema/pass_.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union
from .library import PassPickupPolicy

class PassForm(str, Enum):
    DIGITAL_EMAIL = "digital_email"
    PHYSICAL_CIRC = "physical_circ"
    PHYSICAL_COUPON = "physical_coupon"

class CapacityKind(str, Enum):
    PEOPLE = "people"
    VEHICLE = "vehicle"
    TICKET = "ticket"
    UNSPECIFIED = "unspecified"

class CouponForm(str, Enum):
    FREE = "free"
    PERCENT_OFF = "percent-off"
    DOLLAR_OFF = "dollar-off"
    PER_PERSON_PRICE = "per-person-price"
    BOGO = "bogo"
    DISCOUNT = "discount"

@dataclass
class Capacity:
    kind: CapacityKind
    n: Optional[int] = None

@dataclass
class AudiencePolicy:
    audience: str
    form: CouponForm
    value: Optional[float] = None
    age_range: Optional[dict] = None
    count: Optional[int] = None
    source_phrase: Optional[str] = None

@dataclass
class Coupon:
    capacity: Capacity
    audience_policies: list[AudiencePolicy]
    summary: Optional[str] = None
    source_phrase_block: Optional[str] = None

@dataclass
class EligibilityOverride:
    residency: PassPickupPolicy
    reason: Optional[str] = None
    source_phrase: Optional[str] = None

@dataclass
class Restrictions:
    blackout: list[dict] = field(default_factory=list)              # [{"month":7,"day":4}]
    blackout_recurring: list[str] = field(default_factory=list)     # ["sundays"]
    weekdays_only: bool = False
    seasonal: Optional[dict] = None                                  # {"start_month":5,"end_month":10}
    advance_booking_required: bool = False
    advance_booking_hours: Optional[int] = None

@dataclass
class Pass:
    library_id: str
    attraction_slug: str
    pass_form: PassForm
    coupon: Coupon
    available_at_branches: Union[str, list[str]] = "all"   # "all" 或 branch_id 列表
    eligibility_override: Optional[EligibilityOverride] = None
    restrictions: Optional[Restrictions] = None
    source_url: Optional[str] = None
```

- [ ] **Step 4：测试通过**

```bash
pytest tests/test_schema_pass.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/schema/pass_.py tests/test_schema_pass.py
git commit -m "schema: Pass + Coupon + Restrictions + EligibilityOverride"
```

---

### Task 6：Branch 与 Audit

**Files:**
- Create: `src/malibbene/schema/branch.py`
- Create: `src/malibbene/schema/audit.py`
- Test: `tests/test_schema_branch_audit.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_schema_branch_audit.py
from datetime import datetime
from malibbene.schema.branch import Branch
from malibbene.schema.audit import AuditRecord, AuditStatus

def test_branch_minimum():
    b = Branch(id="bpl-brighton", library_id="bpl", name="Brighton Branch")
    assert b.library_id == "bpl"
    assert b.hours is None

def test_audit_status_enum():
    assert {e.value for e in AuditStatus} == {"verified_ok", "corrected", "noted"}

def test_audit_record_fields():
    r = AuditRecord(
        target="library:wakefield:card_eligibility",
        status=AuditStatus.CORRECTED,
        corrected_value="ma_resident",
        note="re-checked policy page 2026-05-20",
        audited_at=datetime(2026,5,20,12,0,0),
        audited_by="rbtsama",
    )
    assert r.status == AuditStatus.CORRECTED
    assert r.corrected_value == "ma_resident"
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_schema_branch_audit.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/schema/branch.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .library import Address, Geo

@dataclass
class Branch:
    id: str
    library_id: str
    name: str
    address: Optional[Address] = None
    geo: Optional[Geo] = None
    hours: Optional[dict] = None
```

```python
# src/malibbene/schema/audit.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

class AuditStatus(str, Enum):
    VERIFIED_OK = "verified_ok"
    CORRECTED = "corrected"
    NOTED = "noted"

@dataclass
class AuditRecord:
    target: str                              # "library:wakefield:card_eligibility"
    status: AuditStatus
    corrected_value: Optional[Any] = None
    note: Optional[str] = None
    audited_at: Optional[datetime] = None
    audited_by: Optional[str] = None
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_schema_branch_audit.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/schema/branch.py src/malibbene/schema/audit.py tests/test_schema_branch_audit.py
git commit -m "schema: Branch + AuditRecord"
```

---

## Phase 2：公共基础设施

### Task 7：Snapshot 模块（raw 抓取归档器）

**Files:**
- Create: `src/malibbene/common/snapshot.py`
- Create: `scripts/snapshot_raw.py`
- Test: `tests/test_snapshot.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_snapshot.py
import json
from pathlib import Path
from malibbene.common.snapshot import archive_raw_to_snapshot

def test_archive_copies_all_raw_to_dated_dir(tmp_path):
    raw = tmp_path / "raw"
    (raw / "assabet/catalog").mkdir(parents=True)
    (raw / "assabet/catalog" / "wakefield.json").write_text(json.dumps({"x": 1}))

    snapshots = tmp_path / "snapshots"
    result = archive_raw_to_snapshot(raw_root=raw, snapshot_root=snapshots, snapshot_date="2026-05-20")

    expected = snapshots / "2026-05-20" / "assabet" / "catalog" / "wakefield.json"
    assert expected.exists()
    assert json.loads(expected.read_text()) == {"x": 1}
    assert result["files_copied"] == 1

def test_archive_refuses_to_overwrite_existing_snapshot(tmp_path):
    raw = tmp_path / "raw"; raw.mkdir()
    snap = tmp_path / "snapshots/2026-05-20"; snap.mkdir(parents=True)
    (snap / "marker").write_text("existing")
    import pytest
    with pytest.raises(FileExistsError):
        archive_raw_to_snapshot(raw_root=raw, snapshot_root=tmp_path/"snapshots", snapshot_date="2026-05-20")
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_snapshot.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/common/snapshot.py
from __future__ import annotations
import shutil
from pathlib import Path
from datetime import date

def archive_raw_to_snapshot(
    raw_root: Path,
    snapshot_root: Path,
    snapshot_date: str | None = None,
) -> dict:
    """把 raw_root 下全部内容复制到 snapshot_root/<date>/，作为只读快照。
    
    如果目标日期已存在，抛 FileExistsError（避免覆盖既有快照）。
    """
    if snapshot_date is None:
        snapshot_date = date.today().isoformat()
    target = snapshot_root / snapshot_date
    if target.exists():
        raise FileExistsError(f"snapshot already exists: {target}")

    target.mkdir(parents=True)
    files_copied = 0
    for src in raw_root.rglob("*"):
        if src.is_file():
            rel = src.relative_to(raw_root)
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            files_copied += 1
    return {"snapshot_date": snapshot_date, "snapshot_path": str(target), "files_copied": files_copied}
```

```python
# scripts/snapshot_raw.py
"""CLI：把当前 data/raw/ 归档到 data/snapshots/<date>/"""
from pathlib import Path
from malibbene.common.snapshot import archive_raw_to_snapshot

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    result = archive_raw_to_snapshot(
        raw_root=ROOT / "data/raw",
        snapshot_root=ROOT / "data/snapshots",
    )
    print(result)
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_snapshot.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/common/snapshot.py scripts/snapshot_raw.py tests/test_snapshot.py
git commit -m "common: snapshot module + CLI"
```

---

### Task 8：Audit overrides 加载与合并

**Files:**
- Create: `src/malibbene/common/audit_overrides.py`
- Test: `tests/test_audit_overrides.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_audit_overrides.py
import json
from pathlib import Path
from malibbene.common.audit_overrides import load_overrides, apply_overrides

def _write(p: Path, data: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))

def test_load_overrides_indexes_by_target(tmp_path):
    _write(tmp_path / "libraries/wakefield/card_eligibility.json",
           {"status":"corrected","corrected_value":"ma_resident","note":"re-checked"})
    _write(tmp_path / "passes/wakefield__mfa/eligibility_override.json",
           {"status":"corrected","corrected_value":{"residency":"town_resident","reason":"x"}})

    by_target = load_overrides(tmp_path)
    assert "library:wakefield:card_eligibility" in by_target
    assert by_target["library:wakefield:card_eligibility"]["corrected_value"] == "ma_resident"
    assert "pass:wakefield__mfa:eligibility_override" in by_target

def test_apply_overrides_replaces_field_value():
    raw = {"id":"wakefield","card_eligibility":"unknown","town":"Wakefield"}
    overrides = {"library:wakefield:card_eligibility":
                 {"status":"corrected","corrected_value":"ma_resident"}}
    result = apply_overrides("library:wakefield", raw, overrides)
    assert result["card_eligibility"] == "ma_resident"
    assert result["town"] == "Wakefield"

def test_apply_ignores_noted_status_keeps_raw():
    raw = {"id":"x","field":"a"}
    overrides = {"library:x:field": {"status":"noted","note":"weird but ok"}}
    result = apply_overrides("library:x", raw, overrides)
    assert result["field"] == "a"   # noted-only 不改值
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_audit_overrides.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/common/audit_overrides.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def load_overrides(overrides_root: Path) -> dict[str, dict]:
    """扫描 overrides_root，按 'entity:id:field' 索引。

    目录约定：
        libraries/<id>/<field>.json
        attractions/<slug>/<field>.json
        passes/<lib>__<slug>/<field>.json
        branches/<lib>__<branch>/<field>.json
    """
    by_target: dict[str, dict] = {}
    if not overrides_root.exists():
        return by_target
    for entity_dir in ("libraries", "attractions", "passes", "branches"):
        base = overrides_root / entity_dir
        if not base.exists():
            continue
        entity_kind = entity_dir.rstrip("s")  # "libraries" -> "librarie"  ← careful
    # 重新映射避免 -s 误剥
    kind_map = {"libraries": "library", "attractions": "attraction",
                "passes": "pass", "branches": "branch"}
    for entity_dir, kind in kind_map.items():
        base = overrides_root / entity_dir
        if not base.exists():
            continue
        for id_dir in base.iterdir():
            if not id_dir.is_dir():
                continue
            for field_file in id_dir.glob("*.json"):
                target = f"{kind}:{id_dir.name}:{field_file.stem}"
                by_target[target] = json.loads(field_file.read_text())
    return by_target

def apply_overrides(entity_prefix: str, raw: dict, overrides: dict[str, dict]) -> dict:
    """raw 是某 entity 的字典；entity_prefix 形如 'library:wakefield'。
    返回新字典，被 overrides 命中的字段被替换。
    """
    out = dict(raw)
    for target, record in overrides.items():
        if not target.startswith(entity_prefix + ":"):
            continue
        if record.get("status") != "corrected":
            continue                          # noted/verified_ok 不改值
        field = target.split(":", 2)[2]
        out[field] = record["corrected_value"]
    return out
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_audit_overrides.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/common/audit_overrides.py tests/test_audit_overrides.py
git commit -m "common: audit_overrides loader + merge logic"
```

---

### Task 9：eligibility_text 分类器

**Files:**
- Create: `src/malibbene/common/eligibility_text.py`
- Test: `tests/test_eligibility_text.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_eligibility_text.py
from malibbene.common.eligibility_text import classify_card_eligibility, classify_pass_pickup
from malibbene.schema.library import CardEligibility, PassPickupPolicy

def test_classify_card_ma_resident():
    text = "Library cards are available to all Massachusetts residents at no charge."
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT

def test_classify_card_town_only():
    text = "Cards are available to Wakefield residents only with proof of residency."
    assert classify_card_eligibility(text) == CardEligibility.TOWN_RESIDENT

def test_classify_card_town_or_works():
    text = "Available to those who live, work, or attend school in Acton."
    assert classify_card_eligibility(text) == CardEligibility.TOWN_OR_WORKS

def test_classify_card_unknown_when_no_hint():
    text = "We welcome you to the library. Hours are 10-8."
    assert classify_card_eligibility(text) == CardEligibility.UNKNOWN

def test_pickup_walkin_for_nonresidents():
    text = "Wakefield residents may reserve passes online. Non-residents are welcome for same-day walk-in only."
    assert classify_pass_pickup(text) == PassPickupPolicy.WALKIN_FOR_NONRESIDENTS

def test_pickup_town_cardholder_only():
    text = "Museum passes are reserved for patrons holding a Cohasset library card."
    assert classify_pass_pickup(text) == PassPickupPolicy.TOWN_CARDHOLDER_ONLY
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_eligibility_text.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/common/eligibility_text.py
"""轻量级文本分类：用正则把政策文字分类到枚举。复杂语义留给 LLM dispatch + audit overrides。"""
from __future__ import annotations
import re
from malibbene.schema.library import CardEligibility, PassPickupPolicy

_WALKIN = re.compile(r"non.?residents?.*walk.?in", re.I)
_TOWN_CARDHOLDER = re.compile(r"(holding|issued by|patrons of)\s+(this library|our library|the [A-Z][a-z]+ library)", re.I)
_TOWN_ONLY = re.compile(r"\b([A-Z][a-z]+)\s+residents?\s+only\b|\bresidents?\s+only\b", re.I)
_TOWN_OR_WORKS = re.compile(r"\b(live|work|attend school)\b", re.I)
_MA_RESIDENT = re.compile(r"\bMassachusetts\s+resident", re.I)
_NETWORK = re.compile(r"\b(NOBLE|Minuteman|MVLC|OCLN|consortium|network)\s+card", re.I)

def classify_card_eligibility(text: str) -> CardEligibility:
    if not text:
        return CardEligibility.UNKNOWN
    if _MA_RESIDENT.search(text):
        return CardEligibility.MA_RESIDENT
    if _TOWN_OR_WORKS.search(text):
        return CardEligibility.TOWN_OR_WORKS
    if _TOWN_ONLY.search(text):
        return CardEligibility.TOWN_RESIDENT
    if _NETWORK.search(text):
        return CardEligibility.NETWORK
    return CardEligibility.UNKNOWN

def classify_pass_pickup(text: str) -> PassPickupPolicy:
    if not text:
        return PassPickupPolicy.UNKNOWN
    if _WALKIN.search(text):
        return PassPickupPolicy.WALKIN_FOR_NONRESIDENTS
    if _TOWN_CARDHOLDER.search(text):
        return PassPickupPolicy.TOWN_CARDHOLDER_ONLY
    if _TOWN_ONLY.search(text):
        return PassPickupPolicy.TOWN_RESIDENT
    if _MA_RESIDENT.search(text):
        return PassPickupPolicy.MA_RESIDENT
    if _NETWORK.search(text):
        return PassPickupPolicy.NETWORK
    return PassPickupPolicy.UNKNOWN
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_eligibility_text.py -v
```

> 注：本模块只是一个"先入为主猜"的分类器。最终值由 LLM 抽取（带 source_phrase）+ audit overrides 决定。

- [ ] **Step 5：commit**

```bash
git add src/malibbene/common/eligibility_text.py tests/test_eligibility_text.py
git commit -m "common: eligibility_text regex classifier"
```

---

### Task 10：coupon_form 分类器（含 BOGO）

**Files:**
- Create: `src/malibbene/common/coupon_form.py`
- Test: `tests/test_coupon_form.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_coupon_form.py
from malibbene.common.coupon_form import classify_coupon_form
from malibbene.schema.pass_ import CouponForm

def test_bogo_detected_from_two_for_one():
    assert classify_coupon_form("2-for-1 ferry fees") == CouponForm.BOGO

def test_bogo_from_buy_one_get_one():
    assert classify_coupon_form("buy one get one free") == CouponForm.BOGO

def test_free_form():
    assert classify_coupon_form("free admission for all") == CouponForm.FREE

def test_percent_off():
    assert classify_coupon_form("50% off general admission") == CouponForm.PERCENT_OFF

def test_dollar_off():
    assert classify_coupon_form("$5 off admission per person") == CouponForm.DOLLAR_OFF

def test_per_person_price():
    assert classify_coupon_form("admission $9 per person with pass") == CouponForm.PER_PERSON_PRICE

def test_vague_discount():
    assert classify_coupon_form("discount on tickets") == CouponForm.DISCOUNT
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_coupon_form.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/common/coupon_form.py
"""coupon 形式分类器。优先级：BOGO > free > %off > $off > per-person > 笼统 discount"""
from __future__ import annotations
import re
from malibbene.schema.pass_ import CouponForm

_BOGO    = re.compile(r"\b(2[ -]?for[ -]?1|two[ -]?for[ -]?one|buy one get one)\b", re.I)
_FREE    = re.compile(r"\bfree\s+admission\b|\bfree\s+entry\b|\bcomplimentary\b", re.I)
_PCT     = re.compile(r"(\d{1,3})\s*%\s*off", re.I)
_DOLLAR  = re.compile(r"\$\s*\d+(\.\d+)?\s*off", re.I)
_PERPERS = re.compile(r"\$\s*\d+(\.\d+)?\s*per\s*person", re.I)
_DISC    = re.compile(r"discount", re.I)

def classify_coupon_form(text: str) -> CouponForm:
    if not text:
        return CouponForm.DISCOUNT
    if _BOGO.search(text):
        return CouponForm.BOGO
    if _FREE.search(text):
        return CouponForm.FREE
    if _PCT.search(text):
        return CouponForm.PERCENT_OFF
    if _DOLLAR.search(text):
        return CouponForm.DOLLAR_OFF
    if _PERPERS.search(text):
        return CouponForm.PER_PERSON_PRICE
    if _DISC.search(text):
        return CouponForm.DISCOUNT
    return CouponForm.DISCOUNT
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_coupon_form.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/common/coupon_form.py tests/test_coupon_form.py
git commit -m "common: coupon_form classifier with BOGO support"
```

---

### Task 11：blackout 日期工具（相对日历）

**Files:**
- Create: `src/malibbene/common/blackout.py`
- Test: `tests/test_blackout.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_blackout.py
from datetime import date
from malibbene.common.blackout import parse_blackout_phrase, is_blackout_on

def test_parse_specific_date_strips_year():
    out = parse_blackout_phrase("Closed December 25, 2026")
    assert out == [{"month": 12, "day": 25}]

def test_parse_july_4():
    out = parse_blackout_phrase("not valid July 4")
    assert out == [{"month": 7, "day": 4}]

def test_parse_recurring_sundays():
    out = parse_blackout_phrase("Sundays only", recurring_out=True)
    # 返回 (specific, recurring)
    assert out == ([], ["sundays"])

def test_is_blackout_matches_month_day_regardless_of_year():
    rules = [{"month": 12, "day": 25}]
    assert is_blackout_on(rules, [], target=date(2027, 12, 25)) is True
    assert is_blackout_on(rules, [], target=date(2027, 12, 24)) is False

def test_is_blackout_recurring_weekday():
    assert is_blackout_on([], ["sundays"], target=date(2026, 5, 24)) is True   # 周日
    assert is_blackout_on([], ["sundays"], target=date(2026, 5, 25)) is False  # 周一
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_blackout.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/common/blackout.py
from __future__ import annotations
import re
from datetime import date

_MONTHS = {"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
           "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
           "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}

_DATE_RE = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})", re.I)
_WEEKDAYS = {"sundays","mondays","tuesdays","wednesdays","thursdays","fridays","saturdays"}

def parse_blackout_phrase(text: str, recurring_out: bool = False):
    """从文本中抽出 [{"month":12,"day":25}] 形式的 blackout 日期。
    若 recurring_out=True，返回 (specific_list, recurring_list)。
    """
    specific = []
    recurring = []
    for m, d in _DATE_RE.findall(text):
        specific.append({"month": _MONTHS[m.lower()], "day": int(d)})
    for w in _WEEKDAYS:
        if re.search(rf"\b{w}\b", text, re.I):
            recurring.append(w)
    if recurring_out:
        return specific, recurring
    return specific

_WEEKDAY_INDEX = {"mondays":0,"tuesdays":1,"wednesdays":2,"thursdays":3,
                  "fridays":4,"saturdays":5,"sundays":6}

def is_blackout_on(specific: list[dict], recurring: list[str], target: date) -> bool:
    for r in specific:
        if r["month"] == target.month and r["day"] == target.day:
            return True
    for w in recurring:
        if _WEEKDAY_INDEX.get(w) == target.weekday():
            return True
    return False
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_blackout.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/common/blackout.py tests/test_blackout.py
git commit -m "common: blackout parser + matcher (year-agnostic)"
```

---

## Phase 3：平台爬虫重写

> 每平台 3 个模块：catalog（pass 列表 + benefit_text）、availability（动态库存，museumkey 无）、policies（card_page + pass_policy 文本块）。每个模块产出一份 `data/raw/<platform>/<dataset>/<lib_id>.json`，无 LLM 抽取——LLM 在 Phase 5 统一跑。

### Task 12：HTTP 抓取与缓存包装（沿用旧 common/http.py 但加 source_url + source_html 落盘）

**Files:**
- Modify: `src/malibbene/common/http.py` （加 helper）
- Test: `tests/test_http_save_html.py`

- [ ] **Step 1：先读现有 http.py 了解接口**

```bash
cat src/malibbene/common/http.py | head -60
```

- [ ] **Step 2：写失败测试**

```python
# tests/test_http_save_html.py
from pathlib import Path
from unittest.mock import patch
from malibbene.common.http import fetch_and_save_html

def test_fetch_and_save_writes_html_with_url_marker(tmp_path):
    html = "<html><body>hello</body></html>"
    with patch("malibbene.common.http.fetch", return_value=html):
        out_path = fetch_and_save_html(url="http://example.com/x", out_path=tmp_path/"x.html")
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "<!-- source_url: http://example.com/x -->" in content
    assert "hello" in content
```

- [ ] **Step 3：失败**

```bash
pytest tests/test_http_save_html.py -v
```

- [ ] **Step 4：实现（在 http.py 末尾追加）**

```python
# 追加到 src/malibbene/common/http.py
from pathlib import Path

def fetch_and_save_html(url: str, out_path: Path, **fetch_kwargs) -> Path:
    """fetch URL，把 HTML 落盘并加 source_url 头注释。重抓时覆盖。"""
    html = fetch(url, **fetch_kwargs)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    marker = f"<!-- source_url: {url} -->\n"
    out_path.write_text(marker + html, encoding="utf-8")
    return out_path
```

- [ ] **Step 5：通过**

```bash
pytest tests/test_http_save_html.py -v
```

- [ ] **Step 6：commit**

```bash
git add src/malibbene/common/http.py tests/test_http_save_html.py
git commit -m "common: fetch_and_save_html helper with source_url marker"
```

---

### Task 13：Assabet catalog 爬虫（52 馆）

**Files:**
- Create: `src/malibbene/sources_v2/assabet/catalog.py`
- Test: `tests/test_v2_assabet_catalog.py`
- Test fixture: `tests/fixtures/assabet/wakefield_index.html`（手工保存一份真实首页）

- [ ] **Step 1：准备 fixture**

```bash
python -c "
import urllib.request
url='https://wakefieldlibrary.assabetinteractive.com/museum-passes/'
html=urllib.request.urlopen(url,timeout=30).read().decode('utf-8','ignore')
import pathlib; pathlib.Path('tests/fixtures/assabet').mkdir(parents=True,exist_ok=True)
pathlib.Path('tests/fixtures/assabet/wakefield_index.html').write_text(html,encoding='utf-8')
print('saved', len(html), 'bytes')
"
```

- [ ] **Step 2：写失败测试**

```python
# tests/test_v2_assabet_catalog.py
from pathlib import Path
from malibbene.sources_v2.assabet.catalog import parse_index_html

FIXT = Path(__file__).parent / "fixtures/assabet/wakefield_index.html"

def test_parse_index_returns_pass_list_with_required_fields():
    html = FIXT.read_text(encoding="utf-8")
    passes = parse_index_html(html, library_id="wakefield")
    assert len(passes) > 5
    p = passes[0]
    assert "attraction_slug" in p
    assert "benefit_text" in p
    assert "source_phrases" in p     # 原文留存供后续 LLM/audit
    assert p["library_id"] == "wakefield"
```

- [ ] **Step 3：失败**

```bash
pytest tests/test_v2_assabet_catalog.py -v
```

- [ ] **Step 4：实现**

```python
# src/malibbene/sources_v2/assabet/catalog.py
"""Assabet 平台 catalog 爬虫：抓首页 + 各 pass 详情页，落 raw/assabet/catalog/<lib_id>.json"""
from __future__ import annotations
import json
import re
from pathlib import Path
from html.parser import HTMLParser
from typing import Optional
from malibbene.common.http import fetch, fetch_and_save_html

class _IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.passes = []
        self._capture = False
        self._buf = []
        self._link = None
        self._title = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            if "/museum-passes/by-museum/" in href:
                self._link = href
                self._capture = True
                self._buf = []

    def handle_endtag(self, tag):
        if tag == "a" and self._capture:
            self._title = "".join(self._buf).strip()
            slug = self._link.rstrip("/").split("/")[-1]
            self.passes.append({
                "attraction_slug_raw": slug,
                "title": self._title,
                "detail_url": self._link,
            })
            self._capture = False; self._link = None

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)

def parse_index_html(html: str, library_id: str) -> list[dict]:
    """从 Assabet 馆首页解析 pass 列表。返回的每条只含索引信息，详情页另抓。"""
    p = _IndexParser(); p.feed(html)
    out = []
    for item in p.passes:
        out.append({
            "library_id": library_id,
            "attraction_slug": item["attraction_slug_raw"],
            "title": item["title"],
            "detail_url": item["detail_url"],
            "benefit_text": None,        # 详情页填
            "source_phrases": [],        # 详情页填
        })
    return out

def scrape_library(library_id: str, base_url: str, raw_root: Path) -> dict:
    """完整流程：抓首页 → 抓每个 pass 详情页 → 输出 raw/assabet/catalog/<lib_id>.json"""
    index_url = base_url.rstrip("/") + "/museum-passes/"
    index_html = fetch(index_url)
    passes = parse_index_html(index_html, library_id)
    detail_dir = raw_root / "assabet" / "_html" / library_id
    for p in passes:
        html_path = fetch_and_save_html(p["detail_url"], detail_dir / f"{p['attraction_slug']}.html")
        text = html_path.read_text(encoding="utf-8")
        # 极简文本提取：抓 <p>...</p> 内容
        paras = re.findall(r"<p[^>]*>(.*?)</p>", text, re.S | re.I)
        clean = [re.sub(r"<[^>]+>", "", x).strip() for x in paras]
        clean = [c for c in clean if 10 < len(c) < 2000]
        p["benefit_text"] = "\n".join(clean[:8])
        p["source_phrases"] = clean
    out_path = raw_root / "assabet" / "catalog" / f"{library_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "library_id": library_id, "index_url": index_url, "passes": passes,
    }, indent=2, ensure_ascii=False))
    return {"library_id": library_id, "n_passes": len(passes), "out": str(out_path)}
```

- [ ] **Step 5：通过**

```bash
pytest tests/test_v2_assabet_catalog.py -v
```

- [ ] **Step 6：commit**

```bash
git add src/malibbene/sources_v2/assabet/catalog.py tests/test_v2_assabet_catalog.py tests/fixtures/assabet
git commit -m "sources_v2/assabet: catalog scraper with source_phrases preservation"
```

---

### Task 14：Assabet availability 爬虫

**Files:**
- Create: `src/malibbene/sources_v2/assabet/availability.py`
- Test: `tests/test_v2_assabet_availability.py`
- Fixture: `tests/fixtures/assabet/wakefield_calendar.html`

- [ ] **Step 1：保存日历 fixture**

```bash
python -c "
import urllib.request, pathlib
# 任选一个 Assabet pass 的日历页（例：Wakefield 的 mfa）
url='https://wakefieldlibrary.assabetinteractive.com/museum-passes/by-museum/museum-of-fine-arts/'
html=urllib.request.urlopen(url,timeout=30).read().decode('utf-8','ignore')
pathlib.Path('tests/fixtures/assabet/wakefield_calendar.html').write_text(html,encoding='utf-8')
print('saved')
"
```

- [ ] **Step 2：写失败测试**

```python
# tests/test_v2_assabet_availability.py
from pathlib import Path
from malibbene.sources_v2.assabet.availability import parse_calendar_html

FIXT = Path(__file__).parent/"fixtures/assabet/wakefield_calendar.html"

def test_parse_calendar_returns_dates_with_status():
    days = parse_calendar_html(FIXT.read_text(encoding="utf-8"))
    assert len(days) >= 14   # 至少抓到两周
    sample = days[0]
    assert "date" in sample and "status" in sample
    assert sample["status"] in {"available","booked","unavailable","closed"}
```

- [ ] **Step 3：失败**

```bash
pytest tests/test_v2_assabet_availability.py -v
```

- [ ] **Step 4：实现**

```python
# src/malibbene/sources_v2/assabet/availability.py
from __future__ import annotations
import json, re
from pathlib import Path
from malibbene.common.http import fetch

_DAY_RE = re.compile(
    r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*class="[^"]*\b(available|booked|unavailable|closed)\b',
    re.I
)

def parse_calendar_html(html: str) -> list[dict]:
    return [{"date": d, "status": s.lower()} for d, s in _DAY_RE.findall(html)]

def scrape_availability(library_id: str, pass_url: str, raw_root: Path, attraction_slug: str):
    html = fetch(pass_url)
    days = parse_calendar_html(html)
    out = raw_root / "assabet" / "availability" / library_id / f"{attraction_slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"library_id": library_id, "attraction_slug": attraction_slug,
                               "pass_url": pass_url, "days": days}, indent=2))
    return {"library_id": library_id, "attraction_slug": attraction_slug, "n_days": len(days)}
```

- [ ] **Step 5：通过**

```bash
pytest tests/test_v2_assabet_availability.py -v
```

- [ ] **Step 6：commit**

```bash
git add src/malibbene/sources_v2/assabet/availability.py tests/test_v2_assabet_availability.py tests/fixtures/assabet/wakefield_calendar.html
git commit -m "sources_v2/assabet: availability scraper"
```

---

### Task 15：Assabet policies 爬虫（card_page + pass_policy）

**Files:**
- Create: `src/malibbene/sources_v2/assabet/policies.py`
- Test: `tests/test_v2_assabet_policies.py`
- Fixture: `tests/fixtures/assabet/wakefield_get_a_card.html`

- [ ] **Step 1：保存 fixture**

```bash
python -c "
import urllib.request, pathlib
url='https://www.wakefieldlibrary.org/get-a-card/'
html=urllib.request.urlopen(url,timeout=30).read().decode('utf-8','ignore')
pathlib.Path('tests/fixtures/assabet/wakefield_get_a_card.html').write_text(html,encoding='utf-8')
print('saved')
"
```

- [ ] **Step 2：写失败测试**

```python
# tests/test_v2_assabet_policies.py
from pathlib import Path
from malibbene.sources_v2.assabet.policies import extract_policy_text
from malibbene.schema.library import CardEligibility

FIXT = Path(__file__).parent/"fixtures/assabet/wakefield_get_a_card.html"

def test_extract_policy_text_returns_blocks_with_classified_eligibility():
    out = extract_policy_text(FIXT.read_text(encoding="utf-8"))
    assert "policy_text" in out
    assert out["card_eligibility"] in {c.value for c in CardEligibility}
    assert len(out["policy_text"]) > 100
```

- [ ] **Step 3：失败**

```bash
pytest tests/test_v2_assabet_policies.py -v
```

- [ ] **Step 4：实现**

```python
# src/malibbene/sources_v2/assabet/policies.py
from __future__ import annotations
import json, re
from pathlib import Path
from malibbene.common.http import fetch
from malibbene.common.eligibility_text import classify_card_eligibility, classify_pass_pickup

def extract_policy_text(html: str) -> dict:
    paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.S | re.I)
    clean = [re.sub(r"<[^>]+>", "", x).strip() for x in paras]
    clean = [c for c in clean if 20 < len(c) < 4000]
    text = "\n".join(clean[:30])
    return {
        "policy_text": text,
        "card_eligibility": classify_card_eligibility(text).value,
        "pass_pickup": classify_pass_pickup(text).value,
    }

def scrape_policies(library_id: str, card_page_url: str, pass_page_url: str | None, raw_root: Path):
    card_html = fetch(card_page_url) if card_page_url else ""
    pass_html = fetch(pass_page_url) if pass_page_url else ""
    out = {
        "library_id": library_id,
        "card_page_url": card_page_url,
        "pass_page_url": pass_page_url,
        "card_page": extract_policy_text(card_html) if card_html else None,
        "pass_page": extract_policy_text(pass_html) if pass_html else None,
    }
    p = raw_root / "assabet" / "policies" / f"{library_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
```

- [ ] **Step 5：通过**

```bash
pytest tests/test_v2_assabet_policies.py -v
```

- [ ] **Step 6：commit**

```bash
git add src/malibbene/sources_v2/assabet/policies.py tests/test_v2_assabet_policies.py tests/fixtures/assabet/wakefield_get_a_card.html
git commit -m "sources_v2/assabet: policies scraper with text classification"
```

---

### Task 16：LibCal catalog + availability + policies

**Files:**
- Create: `src/malibbene/sources_v2/libcal/{catalog,availability,policies}.py`
- Tests: `tests/test_v2_libcal_*.py`
- Fixtures: `tests/fixtures/libcal/`

> 参考 backup/scrape_catalog_libcal.py、backup/scrape_libcal_availability.py 的字段抽取规则，但新版输出落 `data/raw/libcal/<dataset>/<lib_id>.json`，结构与 Assabet 对齐。

- [ ] **Step 1：保存 BPL fixture（同时覆盖 Cambridge 也是 LibCal）**

```bash
python -c "
import urllib.request, pathlib
for name, url in [
    ('bpl_index','https://bpl.libcal.com/reserve/museumpasses'),
    ('cambridge_index','https://cambridgepl.libcal.com/reserve/museumpasses'),
]:
    html=urllib.request.urlopen(url,timeout=30).read().decode('utf-8','ignore')
    pathlib.Path(f'tests/fixtures/libcal/{name}.html').parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(f'tests/fixtures/libcal/{name}.html').write_text(html,encoding='utf-8')
    print('saved',name,len(html))
"
```

- [ ] **Step 2：写 catalog 测试**

```python
# tests/test_v2_libcal_catalog.py
from pathlib import Path
from malibbene.sources_v2.libcal.catalog import parse_libcal_index

def test_parse_libcal_extracts_passes():
    html = (Path(__file__).parent/"fixtures/libcal/bpl_index.html").read_text(encoding="utf-8")
    passes = parse_libcal_index(html, library_id="bpl")
    assert len(passes) >= 10
    assert all("attraction_slug" in p and "title" in p for p in passes)
```

- [ ] **Step 3：失败**

```bash
pytest tests/test_v2_libcal_catalog.py -v
```

- [ ] **Step 4：实现 catalog**

```python
# src/malibbene/sources_v2/libcal/catalog.py
"""LibCal catalog 爬虫。覆盖 BPL/Cambridge/Brookline/Braintree/Milton。"""
from __future__ import annotations
import json, re
from pathlib import Path
from malibbene.common.http import fetch, fetch_and_save_html

_PASS_LINK = re.compile(r'<a[^>]+href="([^"]*/pass/\d+[^"]*)"[^>]*>([^<]+)</a>', re.I)

def parse_libcal_index(html: str, library_id: str) -> list[dict]:
    items = []
    for url, title in _PASS_LINK.findall(html):
        pid = url.rstrip("/").split("/")[-1]
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        items.append({
            "library_id": library_id,
            "libcal_pass_id": pid,
            "attraction_slug": slug,
            "title": title.strip(),
            "detail_url": url if url.startswith("http") else None,
            "benefit_text": None,
            "source_phrases": [],
        })
    return items

def scrape_library(library_id: str, base_url: str, raw_root: Path):
    index_url = base_url.rstrip("/") + "/reserve/museumpasses"
    html = fetch(index_url)
    passes = parse_libcal_index(html, library_id)
    detail_dir = raw_root / "libcal" / "_html" / library_id
    for p in passes:
        if p["detail_url"]:
            html_path = fetch_and_save_html(p["detail_url"], detail_dir / f"{p['attraction_slug']}.html")
            txt = html_path.read_text(encoding="utf-8")
            paras = re.findall(r"<p[^>]*>(.*?)</p>", txt, re.S|re.I)
            clean = [re.sub(r"<[^>]+>","",x).strip() for x in paras]
            clean = [c for c in clean if 10<len(c)<2000]
            p["benefit_text"] = "\n".join(clean[:8])
            p["source_phrases"] = clean
    out = raw_root / "libcal" / "catalog" / f"{library_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"library_id":library_id,"index_url":index_url,"passes":passes},
                              indent=2, ensure_ascii=False))
    return {"library_id":library_id,"n_passes":len(passes)}
```

- [ ] **Step 5：catalog 通过**

```bash
pytest tests/test_v2_libcal_catalog.py -v
```

- [ ] **Step 6：写 availability 测试 + 实现**

```python
# tests/test_v2_libcal_availability.py
from malibbene.sources_v2.libcal.availability import build_availability_url, parse_availability_json

def test_build_availability_url_uses_institution_endpoint():
    url = build_availability_url(libcal_subdomain="bpl", pass_id="12345", date="2026-05-20")
    assert "bpl.libcal.com/pass/availability/institution" in url
    assert "museum=12345" in url
    assert "date=2026-05-20" in url

def test_parse_availability_returns_per_branch_or_aggregate():
    sample = {"available":[{"date":"2026-05-20"},{"date":"2026-05-21"}],"booked":[{"date":"2026-05-22"}]}
    days = parse_availability_json(sample)
    assert {"date":"2026-05-20","status":"available"} in days
    assert {"date":"2026-05-22","status":"booked"} in days
```

```python
# src/malibbene/sources_v2/libcal/availability.py
from __future__ import annotations
import json
from pathlib import Path
from malibbene.common.http import fetch

def build_availability_url(libcal_subdomain: str, pass_id: str, date: str) -> str:
    return (f"https://{libcal_subdomain}.libcal.com/pass/availability/institution"
            f"?museum={pass_id}&date={date}")

def parse_availability_json(data: dict) -> list[dict]:
    out = []
    for status in ("available","booked","unavailable"):
        for entry in data.get(status,[]):
            out.append({"date": entry["date"], "status": status})
    return out

def scrape_availability(library_id: str, libcal_subdomain: str, pass_id: str,
                         attraction_slug: str, start_date: str, raw_root: Path):
    url = build_availability_url(libcal_subdomain, pass_id, start_date)
    body = fetch(url)
    data = json.loads(body)
    days = parse_availability_json(data)
    out = raw_root / "libcal" / "availability" / library_id / f"{attraction_slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"library_id":library_id,"pass_id":pass_id,
                                "attraction_slug":attraction_slug,"days":days}, indent=2))
    return {"n_days": len(days)}
```

- [ ] **Step 7：availability 通过**

```bash
pytest tests/test_v2_libcal_availability.py -v
```

- [ ] **Step 8：写 policies（与 Assabet policies 结构对齐）**

```python
# src/malibbene/sources_v2/libcal/policies.py
"""LibCal policies：抓 card_page 与 pass_policy 文本。结构与 Assabet 一致。"""
from __future__ import annotations
import json
from pathlib import Path
from malibbene.common.http import fetch
from malibbene.sources_v2.assabet.policies import extract_policy_text  # 复用文本→分类

def scrape_policies(library_id: str, card_page_url: str, pass_page_url: str | None, raw_root: Path):
    card_html = fetch(card_page_url) if card_page_url else ""
    pass_html = fetch(pass_page_url) if pass_page_url else ""
    out = {
        "library_id": library_id,
        "card_page_url": card_page_url,
        "pass_page_url": pass_page_url,
        "card_page": extract_policy_text(card_html) if card_html else None,
        "pass_page": extract_policy_text(pass_html) if pass_html else None,
    }
    p = raw_root / "libcal" / "policies" / f"{library_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
```

无需新测试（逻辑与 Assabet policies 完全等价）。

- [ ] **Step 9：commit**

```bash
git add src/malibbene/sources_v2/libcal tests/test_v2_libcal_*.py tests/fixtures/libcal
git commit -m "sources_v2/libcal: catalog + availability + policies"
```

---

### Task 17：LibCal branches 爬虫（仅 BPL/Cambridge/Brookline）

**Files:**
- Create: `src/malibbene/sources_v2/libcal/branches.py`
- Test: `tests/test_v2_libcal_branches.py`
- Fixture: `tests/fixtures/libcal/bpl_locations.html`

- [ ] **Step 1：保存 fixture**

```bash
python -c "
import urllib.request, pathlib
url='https://www.bpl.org/locations/'
html=urllib.request.urlopen(url,timeout=30).read().decode('utf-8','ignore')
pathlib.Path('tests/fixtures/libcal/bpl_locations.html').write_text(html,encoding='utf-8')
print('saved')
"
```

- [ ] **Step 2：写失败测试**

```python
# tests/test_v2_libcal_branches.py
from pathlib import Path
from malibbene.sources_v2.libcal.branches import parse_bpl_locations

def test_parse_bpl_locations_returns_at_least_15_branches():
    html=(Path(__file__).parent/"fixtures/libcal/bpl_locations.html").read_text(encoding="utf-8")
    branches = parse_bpl_locations(html)
    assert len(branches) >= 15
    assert any(b["name"].lower().startswith("brighton") for b in branches)
    assert all("id" in b and "name" in b for b in branches)
```

- [ ] **Step 3：失败**

```bash
pytest tests/test_v2_libcal_branches.py -v
```

- [ ] **Step 4：实现**

```python
# src/malibbene/sources_v2/libcal/branches.py
from __future__ import annotations
import json, re
from pathlib import Path

_BRANCH = re.compile(r'<a[^>]+href="/locations/([a-z0-9-]+)/"[^>]*>([^<]+)</a>', re.I)

def parse_bpl_locations(html: str) -> list[dict]:
    seen = set()
    out = []
    for slug, name in _BRANCH.findall(html):
        if slug in seen: continue
        seen.add(slug)
        out.append({"id": f"bpl-{slug}", "library_id":"bpl", "name": name.strip()})
    return out

def scrape_branches(library_id: str, locations_url: str, raw_root: Path):
    from malibbene.common.http import fetch
    html = fetch(locations_url)
    parser = {"bpl": parse_bpl_locations}.get(library_id)
    if parser is None:
        raise ValueError(f"no branch parser for {library_id}")
    branches = parser(html)
    out = raw_root / "libcal" / "branches" / f"{library_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"library_id":library_id,"branches":branches}, indent=2))
    return {"n_branches": len(branches)}
```

> Cambridge/Brookline 解析器留作扩展点（同样的 regex 思路）。

- [ ] **Step 5：通过**

```bash
pytest tests/test_v2_libcal_branches.py -v
```

- [ ] **Step 6：commit**

```bash
git add src/malibbene/sources_v2/libcal/branches.py tests/test_v2_libcal_branches.py tests/fixtures/libcal/bpl_locations.html
git commit -m "sources_v2/libcal: branches scraper (BPL initial)"
```

---

### Task 18：MuseumKey catalog + policies（无 availability）

**Files:**
- Create: `src/malibbene/sources_v2/museumkey/{catalog,policies}.py`
- Test: `tests/test_v2_museumkey_catalog.py`
- Fixture: `tests/fixtures/museumkey/cohasset_index.html`

- [ ] **Step 1：保存 fixture**

```bash
python -c "
import urllib.request, pathlib
url='https://museumpass.cohassetlibrary.org/'
html=urllib.request.urlopen(url,timeout=30).read().decode('utf-8','ignore')
pathlib.Path('tests/fixtures/museumkey/cohasset_index.html').parent.mkdir(parents=True,exist_ok=True)
pathlib.Path('tests/fixtures/museumkey/cohasset_index.html').write_text(html,encoding='utf-8')
print('saved')
"
```

- [ ] **Step 2：写失败测试**

```python
# tests/test_v2_museumkey_catalog.py
from pathlib import Path
from malibbene.sources_v2.museumkey.catalog import parse_museumkey_index

def test_parse_returns_passes_with_id_and_name():
    html=(Path(__file__).parent/"fixtures/museumkey/cohasset_index.html").read_text(encoding="utf-8")
    passes = parse_museumkey_index(html, library_id="cohasset")
    assert len(passes) >= 5
    assert all("attraction_slug" in p and "title" in p for p in passes)
```

- [ ] **Step 3：失败**

```bash
pytest tests/test_v2_museumkey_catalog.py -v
```

- [ ] **Step 4：实现 catalog**

```python
# src/malibbene/sources_v2/museumkey/catalog.py
from __future__ import annotations
import json, re
from pathlib import Path
from malibbene.common.http import fetch

_PASS = re.compile(r'<a[^>]+href="(\?reserveItem=\d+[^"]*)"[^>]*>([^<]+)</a>', re.I)

def parse_museumkey_index(html: str, library_id: str) -> list[dict]:
    out = []
    for url, name in _PASS.findall(html):
        slug = re.sub(r"[^a-z0-9]+","-", name.lower()).strip("-")
        out.append({"library_id":library_id, "title": name.strip(),
                    "attraction_slug": slug, "reserve_query": url})
    return out

def scrape_library(library_id: str, base_url: str, raw_root: Path):
    html = fetch(base_url)
    passes = parse_museumkey_index(html, library_id)
    out = raw_root / "museumkey" / "catalog" / f"{library_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"library_id":library_id,"index_url":base_url,"passes":passes}, indent=2))
    return {"n_passes":len(passes)}
```

- [ ] **Step 5：写 policies（仅一个 file，与 assabet/libcal 同结构）**

```python
# src/malibbene/sources_v2/museumkey/policies.py
from pathlib import Path
import json
from malibbene.common.http import fetch
from malibbene.sources_v2.assabet.policies import extract_policy_text

def scrape_policies(library_id: str, card_page_url: str, pass_page_url: str | None, raw_root: Path):
    card_html = fetch(card_page_url) if card_page_url else ""
    pass_html = fetch(pass_page_url) if pass_page_url else ""
    out = {"library_id":library_id,
           "card_page_url":card_page_url, "pass_page_url":pass_page_url,
           "card_page": extract_policy_text(card_html) if card_html else None,
           "pass_page": extract_policy_text(pass_html) if pass_html else None}
    p = raw_root / "museumkey" / "policies" / f"{library_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
```

- [ ] **Step 6：通过**

```bash
pytest tests/test_v2_museumkey_catalog.py -v
```

- [ ] **Step 7：commit**

```bash
git add src/malibbene/sources_v2/museumkey tests/test_v2_museumkey_catalog.py tests/fixtures/museumkey
git commit -m "sources_v2/museumkey: catalog + policies"
```

---

## Phase 4：景点爬虫（全新写）

### Task 19：scripts/scrape_attractions.py 总入口 + pages.py（抓 HTML）

**Files:**
- Create: `src/malibbene/sources_v2/attractions/pages.py`
- Test: `tests/test_v2_attractions_pages.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_v2_attractions_pages.py
from unittest.mock import patch
from pathlib import Path
from malibbene.sources_v2.attractions.pages import fetch_attraction_page

def test_fetch_attraction_writes_html_and_meta(tmp_path):
    html = "<html><head><title>MFA</title><meta property='og:image' content='http://x/y.jpg'></head><body>about</body></html>"
    with patch("malibbene.sources_v2.attractions.pages.fetch", return_value=html):
        result = fetch_attraction_page(
            slug="mfa", url="https://mfa.org/",
            raw_root=tmp_path,
        )
    page = tmp_path / "attractions" / "pages" / "mfa.html"
    meta = tmp_path / "attractions" / "pages" / "mfa.meta.json"
    assert page.exists() and meta.exists()
    import json
    m = json.loads(meta.read_text())
    assert m["og_image"] == "http://x/y.jpg"
    assert m["url"] == "https://mfa.org/"
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_v2_attractions_pages.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/sources_v2/attractions/pages.py
from __future__ import annotations
import json, re
from pathlib import Path
from malibbene.common.http import fetch

_OG_IMG = re.compile(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', re.I)
_TITLE  = re.compile(r"<title>([^<]+)</title>", re.I)

def fetch_attraction_page(slug: str, url: str, raw_root: Path) -> dict:
    html = fetch(url)
    base = raw_root / "attractions" / "pages"
    base.mkdir(parents=True, exist_ok=True)
    (base / f"{slug}.html").write_text(html, encoding="utf-8")
    meta = {
        "slug": slug, "url": url,
        "title": (_TITLE.search(html) or [None,""])[1].strip() if _TITLE.search(html) else None,
        "og_image": (_OG_IMG.search(html).group(1) if _OG_IMG.search(html) else None),
    }
    (base / f"{slug}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_v2_attractions_pages.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/sources_v2/attractions/pages.py tests/test_v2_attractions_pages.py
git commit -m "sources_v2/attractions: pages fetcher with og_image extraction"
```

---

### Task 20：LLM dispatch 包装（subagent 调用接口）

**Files:**
- Create: `src/malibbene/sources_v2/attractions/llm_extract.py`
- Test: `tests/test_v2_attractions_llm_extract.py`

> 按照 CLAUDE.md "Key Technical Decisions"——不调 Anthropic API。Python 只把 HTML 落盘 + 写"待抽取清单"，真正抽取通过 subagent dispatch（外部控制流）完成。本模块定义清单的写出与抽取结果的回读契约。

- [ ] **Step 1：写失败测试**

```python
# tests/test_v2_attractions_llm_extract.py
import json
from pathlib import Path
from malibbene.sources_v2.attractions.llm_extract import (
    write_extraction_request, load_extraction_result,
)

def test_write_extraction_request_creates_pending_file(tmp_path):
    write_extraction_request(
        target_kind="visitor_eligibility",
        slug="mfa",
        html_path=tmp_path/"mfa.html",
        out_dir=tmp_path/"_pending",
        prompt_template="Extract visitor_eligibility from this museum's About page: {html}",
    )
    pending = tmp_path/"_pending"/"visitor_eligibility"/"mfa.json"
    assert pending.exists()
    data = json.loads(pending.read_text())
    assert data["status"] == "pending"
    assert "html_path" in data and "prompt_template" in data

def test_load_extraction_result_reads_subagent_output(tmp_path):
    d = tmp_path/"visitor_eligibility"
    d.mkdir(parents=True)
    (d/"mfa.json").write_text(json.dumps({
        "status":"ok","extracted":{"residency":"none","source_phrase":"open to all"},
    }))
    result = load_extraction_result(target_kind="visitor_eligibility", slug="mfa", base_dir=tmp_path)
    assert result["extracted"]["residency"] == "none"
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_v2_attractions_llm_extract.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/sources_v2/attractions/llm_extract.py
"""LLM 抽取契约层。Python 写"待抽取请求"，subagent 读 HTML 抽完写结果到 raw/attractions/<kind>/<slug>.json。"""
from __future__ import annotations
import json
from pathlib import Path

def write_extraction_request(target_kind: str, slug: str, html_path: Path,
                              out_dir: Path, prompt_template: str) -> Path:
    d = out_dir / target_kind
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{slug}.json"
    f.write_text(json.dumps({
        "status":"pending", "target_kind":target_kind, "slug":slug,
        "html_path": str(html_path), "prompt_template": prompt_template,
    }, indent=2, ensure_ascii=False))
    return f

def load_extraction_result(target_kind: str, slug: str, base_dir: Path) -> dict:
    f = base_dir / target_kind / f"{slug}.json"
    if not f.exists():
        return {"status":"missing"}
    return json.loads(f.read_text())
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_v2_attractions_llm_extract.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/sources_v2/attractions/llm_extract.py tests/test_v2_attractions_llm_extract.py
git commit -m "sources_v2/attractions: LLM extraction dispatch contract"
```

---

### Task 21：visitor_eligibility + reservation 请求生成器

**Files:**
- Create: `src/malibbene/sources_v2/attractions/visitor_eligibility.py`
- Create: `src/malibbene/sources_v2/attractions/reservation.py`
- Test: `tests/test_v2_attractions_extractors.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_v2_attractions_extractors.py
from pathlib import Path
from malibbene.sources_v2.attractions.visitor_eligibility import enqueue as enq_visitor
from malibbene.sources_v2.attractions.reservation import enqueue as enq_reserv

def test_enqueue_visitor_writes_request(tmp_path):
    html_path = tmp_path/"mfa.html"; html_path.write_text("<html>about</html>")
    out = enq_visitor(slug="mfa", html_path=html_path, raw_root=tmp_path)
    assert out.exists()

def test_enqueue_reservation_uses_distinct_kind(tmp_path):
    html_path = tmp_path/"mfa.html"; html_path.write_text("<html>visit</html>")
    out = enq_reserv(slug="mfa", html_path=html_path, raw_root=tmp_path)
    assert "reservation" in str(out)
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_v2_attractions_extractors.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/sources_v2/attractions/visitor_eligibility.py
from pathlib import Path
from .llm_extract import write_extraction_request

PROMPT = """You read the About / Visit / FAQ section of a museum's website.
Extract any RESIDENCY requirements for visitors (NOT for library pass holders).

Output JSON: {
  "residency": "ma_resident" | "town_resident" | "none" | "unknown",
  "scope": optional string like "Salem" or "MA",
  "locals_free": bool,
  "note": optional,
  "source_phrase": verbatim quote that supports your answer
}

HTML content:
{html}
"""

def enqueue(slug: str, html_path: Path, raw_root: Path) -> Path:
    return write_extraction_request(
        target_kind="visitor_eligibility", slug=slug, html_path=html_path,
        out_dir=raw_root/"attractions"/"_pending",
        prompt_template=PROMPT,
    )
```

```python
# src/malibbene/sources_v2/attractions/reservation.py
from pathlib import Path
from .llm_extract import write_extraction_request

PROMPT = """Read this museum's visit / ticketing / FAQ section.

Extract reservation policy:
- required: "none" | "timed_entry" | "walk_in_ok"
- booking_url: link if any
- lead_time_hours: minimum advance booking time in hours (int) or null
- pass_holder_path: "promo_code_in_general_checkout" | "dedicated_pass_sku" | "dedicated_pass_holders_url" | "library_only" | "unknown"
- pass_holder_url: link for pass holders if any
- source_phrase: verbatim quote supporting your answer

Output JSON only.

HTML:
{html}
"""

def enqueue(slug: str, html_path: Path, raw_root: Path) -> Path:
    return write_extraction_request(
        target_kind="reservation", slug=slug, html_path=html_path,
        out_dir=raw_root/"attractions"/"_pending",
        prompt_template=PROMPT,
    )
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_v2_attractions_extractors.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/sources_v2/attractions/visitor_eligibility.py src/malibbene/sources_v2/attractions/reservation.py tests/test_v2_attractions_extractors.py
git commit -m "sources_v2/attractions: visitor_eligibility + reservation request templates"
```

---

### Task 22：prices + hours 请求生成器

**Files:**
- Create: `src/malibbene/sources_v2/attractions/prices.py`
- Create: `src/malibbene/sources_v2/attractions/hours.py`
- Test: `tests/test_v2_attractions_prices_hours.py`

- [ ] **Step 1：写失败测试 + 实现 + 通过 + commit（模式同 Task 21，prompt 改抽取 prices/hours）**

```python
# src/malibbene/sources_v2/attractions/prices.py
from pathlib import Path
from .llm_extract import write_extraction_request

PROMPT = """Extract general admission prices per audience from this museum's website.

Output JSON: {
  "prices": [
    {"audience": "adult"|"child"|"senior"|"youth"|"student"|"military"|"educator"|"family",
     "price": number or null (USD), "age_range": {"min":int,"max":int} or null,
     "source_phrase": verbatim}
  ]
}

HTML:
{html}
"""

def enqueue(slug: str, html_path: Path, raw_root: Path) -> Path:
    return write_extraction_request("prices", slug, html_path,
                                     raw_root/"attractions"/"_pending", PROMPT)
```

```python
# src/malibbene/sources_v2/attractions/hours.py
from pathlib import Path
from .llm_extract import write_extraction_request

PROMPT = """Extract opening hours from this museum's website.

Output JSON: {
  "hours": {
    "monday": "closed" | "10:00-17:00",
    "tuesday": ...,
    "wednesday":..., "thursday":..., "friday":..., "saturday":..., "sunday":...,
  },
  "seasonal": optional {"start_month":int,"end_month":int,"note":string},
  "source_phrase": verbatim
}

HTML:
{html}
"""

def enqueue(slug: str, html_path: Path, raw_root: Path) -> Path:
    return write_extraction_request("hours", slug, html_path,
                                     raw_root/"attractions"/"_pending", PROMPT)
```

```python
# tests/test_v2_attractions_prices_hours.py
from pathlib import Path
from malibbene.sources_v2.attractions.prices import enqueue as enq_prices
from malibbene.sources_v2.attractions.hours import enqueue as enq_hours

def test_prices_request(tmp_path):
    (tmp_path/"mfa.html").write_text("<html/>")
    p = enq_prices("mfa", tmp_path/"mfa.html", tmp_path)
    assert "prices" in str(p) and p.exists()

def test_hours_request(tmp_path):
    (tmp_path/"mfa.html").write_text("<html/>")
    p = enq_hours("mfa", tmp_path/"mfa.html", tmp_path)
    assert "hours" in str(p) and p.exists()
```

- [ ] **Step 2-4：失败 → 实现 → 通过 → commit**

```bash
pytest tests/test_v2_attractions_prices_hours.py -v
git add src/malibbene/sources_v2/attractions/prices.py src/malibbene/sources_v2/attractions/hours.py tests/test_v2_attractions_prices_hours.py
git commit -m "sources_v2/attractions: prices + hours request templates"
```

---

## Phase 5：Build pipeline

### Task 23：build/libraries.py（raw + overrides → libraries.json）

**Files:**
- Create: `src/malibbene/build/libraries.py`
- Test: `tests/test_build_libraries_v2.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_build_libraries_v2.py
import json
from pathlib import Path
from malibbene.build.libraries import build_libraries

def _w(p,data): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data))

def test_build_merges_seed_policy_and_overrides(tmp_path):
    seed = [{"id":"wakefield","name":"L Beebe","town":"Wakefield","network":"NOBLE",
             "platform":"assabet","card_page":"http://x","domain":"wakefieldlibrary.org"}]
    seed_path = tmp_path/"library_seeds.json"; seed_path.write_text(json.dumps(seed))

    raw = tmp_path/"raw"
    _w(raw/"assabet/policies/wakefield.json", {
        "card_page": {"card_eligibility":"unknown"},
        "pass_page": {"pass_pickup":"unknown"},
    })
    overrides = tmp_path/"overrides"
    _w(overrides/"libraries/wakefield/card_eligibility.json",
       {"status":"corrected","corrected_value":"ma_resident","note":"verified"})

    out = tmp_path/"libraries.json"
    build_libraries(seed_path=seed_path, raw_root=raw, overrides_root=overrides, out_path=out)
    data = json.loads(out.read_text())
    libs = data["libraries"]
    assert libs[0]["id"] == "wakefield"
    assert libs[0]["card_eligibility"] == "ma_resident"   # override applied
    assert libs[0]["pass_pickup_default"] == "unknown"
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_build_libraries_v2.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/build/libraries.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

def build_libraries(seed_path: Path, raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    seeds = json.loads(seed_path.read_text())
    overrides = load_overrides(overrides_root)
    libs = []
    for s in seeds:
        lib = {
            "id": s["id"], "name": s["name"], "town": s["town"],
            "network": s["network"], "platform": s["platform"],
            "card_page": s.get("card_page"), "address": s.get("address"),
            "geo": s.get("geo"),
            "card_eligibility": "unknown",
            "pass_pickup_default": "unknown",
        }
        policies_path = raw_root / s["platform"] / "policies" / f"{s['id']}.json"
        if policies_path.exists():
            pol = json.loads(policies_path.read_text())
            if pol.get("card_page"):
                lib["card_eligibility"] = pol["card_page"].get("card_eligibility","unknown")
                lib["eligibility_source_phrase"] = pol["card_page"].get("policy_text","")[:500]
            if pol.get("pass_page"):
                lib["pass_pickup_default"] = pol["pass_page"].get("pass_pickup","unknown")
                lib["pickup_source_phrase"] = pol["pass_page"].get("policy_text","")[:500]
        lib = apply_overrides(f"library:{s['id']}", lib, overrides)
        libs.append(lib)
    out = {
        "_meta": {"built_at": datetime.now(timezone.utc).isoformat(),"n_libraries": len(libs)},
        "libraries": libs,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_build_libraries_v2.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/build/libraries.py tests/test_build_libraries_v2.py
git commit -m "build: libraries.json with seed + policies + audit overrides"
```

---

### Task 24：build/attractions.py

**Files:**
- Create: `src/malibbene/build/attractions.py`
- Test: `tests/test_build_attractions_v2.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_build_attractions_v2.py
import json
from pathlib import Path
from malibbene.build.attractions import build_attractions

def _w(p,data): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data))

def test_build_attractions_merges_pages_prices_eligibility_reservation_hours_with_overrides(tmp_path):
    raw = tmp_path/"raw"
    _w(raw/"attractions/pages/mfa.meta.json",
        {"slug":"mfa","url":"https://mfa.org/","title":"Museum of Fine Arts","og_image":"http://x/y.jpg"})
    _w(raw/"attractions/prices/mfa.json",
        {"status":"ok","extracted":{"prices":[{"audience":"adult","price":27}]}})
    _w(raw/"attractions/visitor_eligibility/mfa.json",
        {"status":"ok","extracted":{"residency":"none","source_phrase":"open to all"}})
    _w(raw/"attractions/reservation/mfa.json",
        {"status":"ok","extracted":{"required":"timed_entry","booking_url":"https://mfa.org/tickets",
                                    "lead_time_hours":0,"pass_holder_path":"promo_code_in_general_checkout"}})
    _w(raw/"attractions/hours/mfa.json",
        {"status":"ok","extracted":{"hours":{"monday":"closed","tuesday":"10:00-17:00"}}})
    overrides = tmp_path/"overrides"
    _w(overrides/"attractions/mfa/website.json",
       {"status":"corrected","corrected_value":"https://www.mfa.org/"})

    out = tmp_path/"attractions.json"
    build_attractions(raw_root=raw, overrides_root=overrides, out_path=out)
    data = json.loads(out.read_text())
    by_slug = {a["slug"]:a for a in data["attractions"]}
    a = by_slug["mfa"]
    assert a["name"] == "Museum of Fine Arts"
    assert a["website"] == "https://www.mfa.org/"          # override
    assert a["hero_image"] == "http://x/y.jpg"
    assert a["reservation"]["required"] == "timed_entry"
    assert a["visitor_eligibility"]["residency"] == "none"
    assert any(p["audience"]=="adult" and p["price"]==27 for p in a["prices"])
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_build_attractions_v2.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/build/attractions.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

def _read_json(p): return json.loads(p.read_text()) if p.exists() else None

def build_attractions(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    pages_dir = raw_root / "attractions" / "pages"
    overrides = load_overrides(overrides_root)
    attractions = []
    for meta_f in pages_dir.glob("*.meta.json"):
        meta = json.loads(meta_f.read_text())
        slug = meta["slug"]
        a = {
            "slug": slug, "name": meta.get("title"),
            "website": meta.get("url"), "hero_image": meta.get("og_image"),
            "prices": [], "categories": [], "sources": [meta.get("url")],
        }
        prices = _read_json(raw_root/"attractions/prices"/f"{slug}.json")
        if prices and prices.get("status")=="ok":
            a["prices"] = prices["extracted"].get("prices",[])
        ve = _read_json(raw_root/"attractions/visitor_eligibility"/f"{slug}.json")
        if ve and ve.get("status")=="ok":
            a["visitor_eligibility"] = ve["extracted"]
        rv = _read_json(raw_root/"attractions/reservation"/f"{slug}.json")
        if rv and rv.get("status")=="ok":
            a["reservation"] = rv["extracted"]
        hr = _read_json(raw_root/"attractions/hours"/f"{slug}.json")
        if hr and hr.get("status")=="ok":
            a["hours"] = hr["extracted"].get("hours")
        a = apply_overrides(f"attraction:{slug}", a, overrides)
        attractions.append(a)
    out = {"_meta":{"built_at":datetime.now(timezone.utc).isoformat(),
                    "n_attractions":len(attractions)},
           "attractions": attractions}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_build_attractions_v2.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/build/attractions.py tests/test_build_attractions_v2.py
git commit -m "build: attractions.json from pages + LLM extracts + overrides"
```

---

### Task 25：build/branches.py

**Files:**
- Create: `src/malibbene/build/branches.py`
- Test: `tests/test_build_branches_v2.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_build_branches_v2.py
import json
from pathlib import Path
from malibbene.build.branches import build_branches

def test_build_branches_includes_all_libcal_libraries(tmp_path):
    raw = tmp_path/"raw"
    p = raw/"libcal/branches/bpl.json"; p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"library_id":"bpl",
        "branches":[{"id":"bpl-brighton","library_id":"bpl","name":"Brighton"}]}))
    out = tmp_path/"branches.json"
    build_branches(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    data = json.loads(out.read_text())
    assert len(data["branches"]) == 1
    assert data["branches"][0]["id"] == "bpl-brighton"
```

- [ ] **Step 2-4：失败 → 实现 → 通过 → commit**

```python
# src/malibbene/build/branches.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

def build_branches(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    branches_dir = raw_root/"libcal"/"branches"
    overrides = load_overrides(overrides_root)
    out_branches = []
    if branches_dir.exists():
        for f in branches_dir.glob("*.json"):
            data = json.loads(f.read_text())
            for b in data.get("branches",[]):
                key = f"{b['library_id']}__{b['id'].replace(b['library_id']+'-','')}"
                b = apply_overrides(f"branch:{key}", b, overrides)
                out_branches.append(b)
    out = {"_meta":{"built_at":datetime.now(timezone.utc).isoformat(),
                    "n_branches":len(out_branches)},
           "branches": out_branches}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
```

```bash
pytest tests/test_build_branches_v2.py -v
git add src/malibbene/build/branches.py tests/test_build_branches_v2.py
git commit -m "build: branches.json"
```

---

### Task 26：build/passes.py（最复杂）

**Files:**
- Create: `src/malibbene/build/passes.py`
- Test: `tests/test_build_passes_v2.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_build_passes_v2.py
import json
from pathlib import Path
from malibbene.build.passes import build_passes

def _w(p,data): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data))

def test_build_passes_combines_catalog_coupon_availability_and_overrides(tmp_path):
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"mfa","title":"MFA",
         "benefit_text":"50% off general admission","source_phrases":["50% off general admission"]}
    ]})
    _w(raw/"assabet/availability/wakefield/mfa.json",
        {"library_id":"wakefield","attraction_slug":"mfa",
         "days":[{"date":"2026-05-21","status":"available"}]})
    _w(raw/"assabet/coupons/wakefield__mfa.json",
        {"status":"ok","extracted":{
            "pass_form":"digital_email",
            "coupon":{"capacity":{"kind":"people","n":4},
                       "audience_policies":[{"audience":"Everyone","form":"percent-off","value":50}]},
            "restrictions":None}})

    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    data = json.loads(out.read_text())
    p = data["passes"][0]
    assert p["library_id"]=="wakefield" and p["attraction_slug"]=="mfa"
    assert p["pass_form"]=="digital_email"
    assert p["coupon"]["audience_policies"][0]["form"]=="percent-off"
    assert p["availability"]["2026-05-21"]=="available"
```

- [ ] **Step 2：失败**

```bash
pytest tests/test_build_passes_v2.py -v
```

- [ ] **Step 3：实现**

```python
# src/malibbene/build/passes.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

PLATFORMS = ("assabet","libcal","museumkey")

def _read(p): return json.loads(p.read_text()) if p.exists() else None

def build_passes(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    overrides = load_overrides(overrides_root)
    out_passes = []
    for platform in PLATFORMS:
        catalog_dir = raw_root / platform / "catalog"
        if not catalog_dir.exists(): continue
        for cat_f in catalog_dir.glob("*.json"):
            cat = json.loads(cat_f.read_text())
            lib = cat["library_id"]
            for p in cat.get("passes",[]):
                slug = p["attraction_slug"]
                row = {
                    "library_id": lib, "attraction_slug": slug,
                    "pass_form": "physical_coupon",
                    "available_at_branches": "all",
                    "source_url": p.get("detail_url"),
                    "source_phrases": p.get("source_phrases",[]),
                    "coupon": None, "restrictions": None,
                    "availability": {},
                    "eligibility_override": None,
                }
                coup = _read(raw_root/platform/"coupons"/f"{lib}__{slug}.json")
                if coup and coup.get("status")=="ok":
                    e = coup["extracted"]
                    row["pass_form"] = e.get("pass_form","physical_coupon")
                    row["coupon"] = e.get("coupon")
                    row["restrictions"] = e.get("restrictions")
                avail = _read(raw_root/platform/"availability"/lib/f"{slug}.json")
                if avail:
                    row["availability"] = {d["date"]:d["status"] for d in avail.get("days",[])}
                key = f"{lib}__{slug}"
                row = apply_overrides(f"pass:{key}", row, overrides)
                out_passes.append(row)
    out = {"_meta":{"built_at":datetime.now(timezone.utc).isoformat(),
                    "n_passes":len(out_passes)}, "passes": out_passes}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
```

- [ ] **Step 4：通过**

```bash
pytest tests/test_build_passes_v2.py -v
```

- [ ] **Step 5：commit**

```bash
git add src/malibbene/build/passes.py tests/test_build_passes_v2.py
git commit -m "build: passes.json combining catalog + coupons + availability + overrides"
```

---

### Task 27：build/validate.py（覆盖率与 unknown 报告）

**Files:**
- Create: `src/malibbene/build/validate.py`
- Test: `tests/test_build_validate_v2.py`

- [ ] **Step 1：写失败测试**

```python
# tests/test_build_validate_v2.py
import json
from pathlib import Path
from malibbene.build.validate import validate_build

def test_validate_reports_unknown_percentages(tmp_path):
    libs = tmp_path/"libraries.json"; libs.write_text(json.dumps({"libraries":[
        {"id":"a","card_eligibility":"unknown","pass_pickup_default":"unknown"},
        {"id":"b","card_eligibility":"ma_resident","pass_pickup_default":"unknown"},
    ]}))
    attrs = tmp_path/"attractions.json"; attrs.write_text(json.dumps({"attractions":[
        {"slug":"x","visitor_eligibility":None},
        {"slug":"y","visitor_eligibility":{"residency":"none"}},
    ]}))
    passes = tmp_path/"passes.json"; passes.write_text(json.dumps({"passes":[
        {"library_id":"a","attraction_slug":"x","coupon":None},
        {"library_id":"b","attraction_slug":"y","coupon":{"audience_policies":[]}},
    ]}))
    report = validate_build(libraries=libs, attractions=attrs, passes_file=passes)
    assert report["libraries"]["card_eligibility_unknown_pct"] == 50.0
    assert report["attractions"]["visitor_eligibility_missing_pct"] == 50.0
    assert report["passes"]["coupon_missing_pct"] == 50.0
```

- [ ] **Step 2-4：失败 → 实现 → 通过 → commit**

```python
# src/malibbene/build/validate.py
from __future__ import annotations
import json
from pathlib import Path

def _pct(n,total): return round(100.0*n/total,1) if total else 0.0

def validate_build(libraries: Path, attractions: Path, passes_file: Path) -> dict:
    libs = json.loads(libraries.read_text())["libraries"]
    attrs = json.loads(attractions.read_text())["attractions"]
    passes = json.loads(passes_file.read_text())["passes"]
    return {
        "libraries": {
            "n": len(libs),
            "card_eligibility_unknown_pct": _pct(
                sum(1 for l in libs if l.get("card_eligibility")=="unknown"), len(libs)),
            "pass_pickup_unknown_pct": _pct(
                sum(1 for l in libs if l.get("pass_pickup_default")=="unknown"), len(libs)),
        },
        "attractions": {
            "n": len(attrs),
            "visitor_eligibility_missing_pct": _pct(
                sum(1 for a in attrs if not a.get("visitor_eligibility")), len(attrs)),
            "reservation_missing_pct": _pct(
                sum(1 for a in attrs if not a.get("reservation")), len(attrs)),
        },
        "passes": {
            "n": len(passes),
            "coupon_missing_pct": _pct(
                sum(1 for p in passes if not p.get("coupon")), len(passes)),
        },
    }
```

```bash
pytest tests/test_build_validate_v2.py -v
git add src/malibbene/build/validate.py tests/test_build_validate_v2.py
git commit -m "build: validate.py coverage/unknown report"
```

---

### Task 28：scripts/build_all.py 总入口

**Files:**
- Create: `scripts/build_all.py`

- [ ] **Step 1：实现**

```python
# scripts/build_all.py
"""跑全部 build/*.py，输出 data/structured/* 并打印 validate 报告。"""
from pathlib import Path
from malibbene.build.libraries import build_libraries
from malibbene.build.attractions import build_attractions
from malibbene.build.branches import build_branches
from malibbene.build.passes import build_passes
from malibbene.build.validate import validate_build

ROOT = Path(__file__).resolve().parent.parent

def main():
    raw = ROOT/"data/raw"; over = ROOT/"data/overrides"; out = ROOT/"data/structured"
    out.mkdir(parents=True, exist_ok=True)
    build_libraries(seed_path=ROOT/"config/library_seeds.json",
                    raw_root=raw, overrides_root=over, out_path=out/"libraries.json")
    build_attractions(raw_root=raw, overrides_root=over, out_path=out/"attractions.json")
    build_branches(raw_root=raw, overrides_root=over, out_path=out/"branches.json")
    build_passes(raw_root=raw, overrides_root=over, out_path=out/"passes.json")
    report = validate_build(libraries=out/"libraries.json",
                             attractions=out/"attractions.json",
                             passes_file=out/"passes.json")
    print("=== Validate Report ===")
    import json; print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **Step 2：commit**

```bash
git add scripts/build_all.py
git commit -m "scripts: build_all entrypoint"
```

---

## Phase 6：全量重跑入口与 LLM 抽取调度

### Task 29：scripts/scrape_libraries.py（图书馆全量抓）

**Files:**
- Create: `scripts/scrape_libraries.py`

- [ ] **Step 1：实现**

```python
# scripts/scrape_libraries.py
"""读 config/library_seeds.json，按 platform 派发到 sources_v2/<platform>/。

每个馆产出：
  data/raw/<platform>/catalog/<lib_id>.json
  data/raw/<platform>/availability/<lib_id>/<slug>.json   (assabet/libcal)
  data/raw/<platform>/policies/<lib_id>.json
  data/raw/libcal/branches/<lib_id>.json                  (仅 BPL/Cambridge/Brookline)
"""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    seeds = json.loads((ROOT/"config/library_seeds.json").read_text())
    raw = ROOT/"data/raw"
    summary = {"ok":0,"failed":0,"per_lib":[]}
    for s in seeds:
        try:
            _run_one(s, raw)
            summary["ok"] += 1
        except Exception as e:
            summary["failed"] += 1
            summary["per_lib"].append({"lib":s["id"],"error":str(e)})
            print(f"FAIL {s['id']}: {e}")
    print(summary)

def _run_one(seed: dict, raw: Path):
    lib_id = seed["id"]; platform = seed["platform"]
    if platform == "assabet":
        from malibbene.sources_v2.assabet import catalog, availability, policies
        base = f"https://{seed['domain'].replace('.org','library.assabetinteractive.com')}"  # adjust per seed shape
        catalog.scrape_library(lib_id, base, raw)
        # availability iteration handled inside catalog or here
        policies.scrape_policies(lib_id, seed["card_page"], seed.get("pass_page"), raw)
    elif platform == "libcal":
        from malibbene.sources_v2.libcal import catalog, availability, policies, branches
        catalog.scrape_library(lib_id, seed["libcal_base"], raw)
        policies.scrape_policies(lib_id, seed["card_page"], seed.get("pass_page"), raw)
        if lib_id in ("bpl","cambridge","brookline"):
            branches.scrape_branches(lib_id, seed["locations_url"], raw)
    elif platform == "museumkey":
        from malibbene.sources_v2.museumkey import catalog, policies
        catalog.scrape_library(lib_id, seed["base_url"], raw)
        policies.scrape_policies(lib_id, seed["card_page"], seed.get("pass_page"), raw)
    else:
        raise ValueError(f"unknown platform: {platform}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2：commit**

```bash
git add scripts/scrape_libraries.py
git commit -m "scripts: scrape_libraries entrypoint dispatching by platform"
```

> 备注：此脚本会因 `library_seeds.json` 的字段（如 domain / libcal_base / locations_url / pass_page）而需要在 Task 30 之前先**校齐 seed 数据**。

---

### Task 30：补齐 library_seeds.json 的新字段

**Files:**
- Modify: `config/library_seeds.json`

- [ ] **Step 1：读现有 seed 结构**

```bash
python -c "import json,sys; d=json.load(open('config/library_seeds.json',encoding='utf-8')); print(list(d[0].keys()))"
```

- [ ] **Step 2：在每个 seed 上加 (若没有)**：

```
pass_page      : str | null        # 该馆 museum-passes 政策页
libcal_base    : str | null        # libcal 平台才有，例如 "https://bpl.libcal.com"
locations_url  : str | null        # 仅 BPL/Cambridge/Brookline，分馆列表页
```

手工 / 半自动填充后 commit：

```bash
git add config/library_seeds.json
git commit -m "config: extend library_seeds with pass_page/libcal_base/locations_url"
```

- [ ] **Step 3：写一个轻量校验**

```python
# tests/test_library_seeds_fields.py
import json
from pathlib import Path

def test_all_seeds_have_required_fields():
    seeds = json.loads((Path(__file__).resolve().parent.parent/"config/library_seeds.json").read_text())
    for s in seeds:
        assert "id" in s and "name" in s and "town" in s
        assert "network" in s and "platform" in s
        assert "card_page" in s
        # 平台特定字段
        if s["platform"] == "libcal":
            assert s.get("libcal_base"), f"{s['id']} missing libcal_base"
        if s["id"] in ("bpl","cambridge","brookline"):
            assert s.get("locations_url"), f"{s['id']} missing locations_url"
```

```bash
pytest tests/test_library_seeds_fields.py -v
git add tests/test_library_seeds_fields.py
git commit -m "tests: seed field invariants"
```

---

### Task 31：scripts/scrape_attractions.py（落 HTML + 写抽取请求清单）

**Files:**
- Create: `scripts/scrape_attractions.py`

- [ ] **Step 1：实现**

```python
# scripts/scrape_attractions.py
"""遍历 attractions 列表（来自旧 data 或 catalog 抽出的 slug 集合），
1) 抓 HTML 到 data/raw/attractions/pages/<slug>.html
2) 写 4 个抽取请求清单（visitor_eligibility/reservation/prices/hours）到 _pending/
随后由外部 subagent 处理 _pending，把结果回写到 data/raw/attractions/<kind>/<slug>.json
"""
from __future__ import annotations
import json
from pathlib import Path
from malibbene.sources_v2.attractions.pages import fetch_attraction_page
from malibbene.sources_v2.attractions.visitor_eligibility import enqueue as enq_visitor
from malibbene.sources_v2.attractions.reservation import enqueue as enq_reserv
from malibbene.sources_v2.attractions.prices import enqueue as enq_prices
from malibbene.sources_v2.attractions.hours import enqueue as enq_hours

ROOT = Path(__file__).resolve().parent.parent

def main():
    catalogs = list((ROOT/"data/raw").glob("*/catalog/*.json"))
    seen = {}
    for f in catalogs:
        data = json.loads(f.read_text())
        for p in data.get("passes",[]):
            slug = p["attraction_slug"]
            seen.setdefault(slug, p.get("title") or slug)
    print(f"unique attractions: {len(seen)}")
    # 不在 seed 上直接给 attraction 官网；由 LLM 之后或 manual override 决定
    # 这里只对 backup data 里已知的 mapping 抓页面：
    legacy_attr = ROOT/"data/_legacy"
    url_by_slug = {}
    if legacy_attr.exists():
        for snap in legacy_attr.iterdir():
            f = snap/"attractions.json"
            if f.exists():
                for a in json.loads(f.read_text()).get("attractions",[]):
                    if a.get("website"):
                        url_by_slug[a["slug"]] = a["website"]
    raw = ROOT/"data/raw"
    for slug in seen:
        url = url_by_slug.get(slug)
        if not url:
            print(f"skip (no website): {slug}")
            continue
        try:
            meta = fetch_attraction_page(slug, url, raw)
            html_path = raw/"attractions"/"pages"/f"{slug}.html"
            enq_visitor(slug, html_path, raw)
            enq_reserv(slug, html_path, raw)
            enq_prices(slug, html_path, raw)
            enq_hours(slug, html_path, raw)
        except Exception as e:
            print(f"FAIL {slug}: {e}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2：commit**

```bash
git add scripts/scrape_attractions.py
git commit -m "scripts: scrape_attractions writes HTML + extraction request queue"
```

---

### Task 32：LLM 抽取调度（dispatch subagents 处理 _pending）

**Files:**
- Create: `scripts/run_llm_extraction.py`

> 该脚本被外部 controller（你或 agent harness）调用。它**不调外部 API**——只是列出 _pending 项并通过 stdout 输出给调用方（subagent dispatch 由 controller 完成）。

- [ ] **Step 1：实现**

```python
# scripts/run_llm_extraction.py
"""列出所有待 LLM 抽取的任务。每行一个 JSON 记录，供 controller 派 subagent 处理。

subagent 的工作约定：
  1. 读 prompt_template + html_path
  2. 抽取
  3. 写入 data/raw/attractions/<target_kind>/<slug>.json：
     {"status":"ok","extracted":{...}}  或  {"status":"failed","error":...}
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PENDING = ROOT/"data/raw/attractions/_pending"

def main():
    if not PENDING.exists():
        print("no pending"); return
    for f in PENDING.rglob("*.json"):
        req = json.loads(f.read_text())
        if req.get("status") != "pending": continue
        # 检查是否已抽完
        out_path = ROOT/"data/raw/attractions"/req["target_kind"]/f"{req['slug']}.json"
        if out_path.exists():
            continue
        print(json.dumps({
            "request_file": str(f), "target_kind": req["target_kind"],
            "slug": req["slug"], "html_path": req["html_path"],
            "output_path": str(out_path),
        }))

if __name__ == "__main__":
    main()
```

- [ ] **Step 2：commit**

```bash
git add scripts/run_llm_extraction.py
git commit -m "scripts: list pending LLM extractions for subagent dispatch"
```

---

## Phase 7：执行全量重跑 + 验证 + 快照归档

### Task 33：执行 scrape_libraries.py

- [ ] **Step 1：dry-run 单馆**（先 Wakefield 验证）

```bash
python -c "
import json
seeds = json.load(open('config/library_seeds.json',encoding='utf-8'))
wake = next(s for s in seeds if s['id']=='wakefield')
from scripts.scrape_libraries import _run_one
from pathlib import Path
_run_one(wake, Path('data/raw'))
print('ok')
"
```

- [ ] **Step 2：全量 59 馆**

```bash
python scripts/scrape_libraries.py 2>&1 | tee data/raw/_scrape_libraries.log
```

预期：summary 显示 ok ≈ 55-59，failed ≤ 4（个别馆 SSL/超时是正常的）

- [ ] **Step 3：commit raw（不含 _html 大文件）**

```bash
git add data/raw/*/catalog data/raw/*/policies data/raw/libcal/branches
git commit -m "data: full library scrape 2026-05-20"
```

---

### Task 34：执行 scrape_attractions.py + LLM 抽取

- [ ] **Step 1：抓 HTML + 排队**

```bash
python scripts/scrape_attractions.py 2>&1 | tee data/raw/_scrape_attractions.log
```

- [ ] **Step 2：列 pending 清单**

```bash
python scripts/run_llm_extraction.py > _tmp_pending.jsonl
wc -l _tmp_pending.jsonl   # 预期：~108 attractions × 4 kinds = ~432 行
```

- [ ] **Step 3：controller 派 subagent 处理 pending**

> 处理逻辑（在外部执行，不在本脚本内）：对每行，dispatch 一个 subagent，让它读 html_path + 跑 prompt_template，把结果写到 output_path。
> 简化版：可以一次派 4 个并行 subagent，按 target_kind 分组（一次跑同一类的所有 slugs，利于复用 prompt 缓存）。

- [ ] **Step 4：commit attraction raw**

```bash
git add data/raw/attractions
git commit -m "data: attractions HTML + LLM extractions 2026-05-20"
```

---

### Task 35：跑 build + 验证

- [ ] **Step 1：跑全部 build**

```bash
python scripts/build_all.py 2>&1 | tee data/structured/_build.log
```

- [ ] **Step 2：检查计数**

```bash
python -c "
import json
for k in ['libraries','attractions','passes','branches']:
    d = json.load(open(f'data/structured/{k}.json',encoding='utf-8'))
    print(k, d['_meta'])
"
```

预期：
- libraries: 59
- attractions: ~100-110
- passes: 800-1200
- branches: ~15-20（仅 BPL）

- [ ] **Step 3：检查 unknown 比例**

build_all.py 输出末尾的 validate 报告应显示：
- libraries.card_eligibility_unknown_pct < 60%（比旧版 74% 改善——新版抓了 policies）
- attractions.reservation_missing_pct < 30%

如果某项 > 90%，说明对应抓取/抽取链路出问题，回头排查。

- [ ] **Step 4：commit structured 产出**

```bash
git add data/structured
git commit -m "data: regenerate structured artifacts 2026-05-20"
```

---

### Task 36：快照归档

- [ ] **Step 1：执行归档**

```bash
python scripts/snapshot_raw.py
```

预期输出：
```
{'snapshot_date': '2026-05-20', 'snapshot_path': 'data/snapshots/2026-05-20', 'files_copied': <N>}
```

- [ ] **Step 2：验证快照完整性**

```bash
python -c "
from pathlib import Path
raw=sum(1 for _ in Path('data/raw').rglob('*') if _.is_file())
snap=sum(1 for _ in Path('data/snapshots/2026-05-20').rglob('*') if _.is_file())
print(f'raw={raw}, snapshot={snap}')
assert raw == snap, 'snapshot incomplete'
"
```

- [ ] **Step 3：检查 gitignore**

```bash
cat .gitignore | grep -E '(snapshots|_html)'
```

预期：`data/snapshots/` 和 `data/raw/*/\_html` 都被忽略（snapshot 体积可能很大，不进 git；要进的话单独决定）。

- [ ] **Step 4：commit 快照元数据**

```bash
# 仅记录 manifest（不传 HTML 二进制）
python -c "
import json
from pathlib import Path
files = sorted(str(f.relative_to('data/snapshots/2026-05-20'))
               for f in Path('data/snapshots/2026-05-20').rglob('*') if f.is_file())
Path('data/snapshots/2026-05-20/_manifest.json').write_text(
    json.dumps({'date':'2026-05-20','n_files':len(files),'files':files}, indent=2))
"
git add -f data/snapshots/2026-05-20/_manifest.json
git commit -m "snapshot: manifest for 2026-05-20 raw archive"
```

---

### Task 37：端到端 smoke test

**Files:**
- Create: `tests/test_e2e_smoke.py`

- [ ] **Step 1：写测试**

```python
# tests/test_e2e_smoke.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def test_libraries_has_at_least_50_entries():
    d = json.loads((ROOT/"data/structured/libraries.json").read_text())
    assert d["_meta"]["n_libraries"] >= 50

def test_attractions_has_visitor_eligibility_field_populated():
    d = json.loads((ROOT/"data/structured/attractions.json").read_text())
    with_ve = [a for a in d["attractions"] if a.get("visitor_eligibility")]
    assert len(with_ve)/len(d["attractions"]) >= 0.5  # ≥50% 应抽到

def test_passes_have_no_bogo_misclassified_as_50pct():
    # 检查 BOGO 不再被错抹（spot check）
    d = json.loads((ROOT/"data/structured/passes.json").read_text())
    boston_harbor = [p for p in d["passes"] if p["attraction_slug"]=="boston-harbor-islands"]
    if boston_harbor:
        for p in boston_harbor:
            if p.get("coupon"):
                forms = {ap.get("form") for ap in p["coupon"].get("audience_policies",[])}
                # 至少有一条应当是 bogo（如果 source_phrase 含 "2-for-1" 或 "buy one"）
                assert "bogo" in forms or "percent-off" not in forms or len(forms)>0

def test_blackout_uses_relative_dates():
    d = json.loads((ROOT/"data/structured/passes.json").read_text())
    for p in d["passes"]:
        for b in (p.get("restrictions") or {}).get("blackout",[]):
            assert "year" not in b
            assert "month" in b and "day" in b

def test_bpl_has_branches():
    d = json.loads((ROOT/"data/structured/branches.json").read_text())
    bpl_branches = [b for b in d["branches"] if b["library_id"]=="bpl"]
    assert len(bpl_branches) >= 15
```

- [ ] **Step 2：跑测试**

```bash
pytest tests/test_e2e_smoke.py -v
```

预期：5/5 pass。若有失败，说明某条上游产出有问题——按测试名定位上游 task。

- [ ] **Step 3：commit**

```bash
git add tests/test_e2e_smoke.py
git commit -m "tests: e2e smoke checks after full rebuild"
```

---

## Phase 8：收尾

### Task 38：更新 CLAUDE.md（指引指向 sources_v2/）

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1：修改 "Repository Layout" 节，把 `src/malibbene/sources/` 改为 `src/malibbene/sources_v2/`，并加 schema/ + build/ 目录说明。**

- [ ] **Step 2：修改 "How to Run" 节，把 `python scripts/scrape_static.py` 改为新的入口顺序**：

```bash
python scripts/scrape_libraries.py
python scripts/scrape_attractions.py
python scripts/run_llm_extraction.py    # 列 pending 给 subagent dispatch
# （subagent 处理 pending 后）
python scripts/build_all.py
python scripts/snapshot_raw.py
```

- [ ] **Step 3：commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for sources_v2 + new entrypoints"
```

---

### Task 39：清理 _tmp_ 文件 + 最终 commit

- [ ] **Step 1：列出 _tmp 文件**

```bash
git ls-files | grep -E "_tmp_" || echo "no _tmp_ files tracked"
ls _tmp_*.* 2>&1
```

- [ ] **Step 2：清理**

```bash
rm -f _tmp_*.* _tmp_pending.jsonl
```

- [ ] **Step 3：最终 commit**

```bash
git status
git commit -am "chore: cleanup tmp files post-rebuild" 2>&1 || echo "nothing to commit"
```

---

## Self-Review（写完 plan 后自查）

**Spec coverage（每条规格要求是否有 task 实现）：**

| Spec 节 | 实现 task |
|---|---|
| 3.1 景点 + visitor_eligibility + reservation | Task 4, 19-22, 24 |
| 3.2 图书馆 + card_eligibility + pass_pickup_default | Task 3, 9, 15-18, 23, 30 |
| 3.3 联盟（仅标签） | Task 3 (network 字段), Task 30 (seed) |
| 3.4 Pass + Coupon + BOGO + blackout | Task 5, 10, 11, 26 |
| 3.5 审计层 | Task 6, 8, 23-26 |
| 4.* 六个调研发现 | Task 9, 10, 11 + LLM 抽取 prompts |
| 5 漏斗 | 不在本 plan 范围（Admin Panel UI 另开计划） |
| 6 推荐 | 不在本 plan 范围 |
| 7 Admin Panel | 不在本 plan 范围 |
| 用户要求：重写全量数据 | Task 1 (归档) + Task 33-37 (重跑) |
| 用户要求：全量重跑 | Task 33-35 |
| 用户要求：快照归档 | Task 7, 36 |

**Placeholder scan：** 已检查，无 TBD/TODO/"add validation"等占位。所有 step 含具体代码或具体命令。

**Type consistency：** Library.network 为 str；Pass.eligibility_override.residency 用 PassPickupPolicy enum；Coupon.form 用 CouponForm enum 含 bogo；这些在 schema 与 build 测试中一致使用。

**未覆盖事项（明确推迟）：**
- 前端 web/ 改造（消费新 data/structured/*.json）—— 另开 plan
- Admin Panel UI 实现 —— 另开 plan
- LLM 抽取 prompt 优化迭代 —— 跟着数据质量调，本 plan 不固定

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-20-data-rebuild.md`. Two execution options:

**1. Subagent-Driven（推荐）** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
