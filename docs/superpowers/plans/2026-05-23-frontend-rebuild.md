# 前端对接新数据底层 + Admin Panel 重做 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `web/`(React+Vite+HeroUI 用户端)和 `web/public/admin/`(绿色主题 Admin Panel)对接到本轮重建的新数据底层(`data/structured/*.json`),实现「我能不能拿这张 pass」的资格漏斗 + pass 推荐 + 带审计纠错能力的 Admin 透视台。

**Architecture:** 三层 —— (1) **数据层**:TS 类型 + loader,对齐新 JSON 形状(`residency_restriction` / `resident_zips` / `pass_form` / canonical slug / 新 coupon);(2) **纯逻辑引擎**(无 React,可单测):资格漏斗 `eligibility.ts`(L1/L3/L4/L5/L8/L9/L10)+ 推荐 `recommend.ts`(最多 4 条,Email 1 + Pickup/Return 3,按优惠力度+距离打分);(3) **UI**:用户端组件改用新形状 + 引擎,Admin Panel 4 Lens + 漏斗模拟器 + 审计 override 读写。全程沿用现有绿色 token(`web/src/styles/tokens.css` / `web/public/admin/assets/panel.css`,主色 `--g:#1B5740`)。

**Tech Stack:** React 19, Vite, TypeScript, HeroUI, react-router, zustand, vitest。Admin Panel 是独立的原生 HTML/CSS/JS(`web/public/admin/panel.html` + `assets/panel.css|panel.js`),不进 React 构建,数据由 `web/sync-admin.mjs` 在 predev/prebuild 同步到 `web/public/data/`。

**数据形状(本计划的事实来源 —— `data/structured/*.json`):**
- `libraries[]`: `{id, name, town, network, platform, card_page, address|null, geo|null, card_eligibility, pass_pickup_default, eligibility_source_phrase?, pickup_source_phrase?, resident_zips:string[]}`
- `attractions[]`: `{slug, name, website?, phone?, address?, geo?, description?, categories:string[], hero_image?, prices:AudiencePrice[], hours?:{monday..sunday: "HH:MM-HH:MM"|"closed"|"unknown"}, visitor_eligibility?, reservation?, sources:string[]}`
- `passes[]`: `{library_id, attraction_slug(canonical), pass_form:"digital_email"|"physical_circ"|"physical_coupon", available_at_branches:"all"|string[], source_url?, coupon:null|{capacity:{kind,n}, audience_policies:[{audience,form,value?,age_range?,count?,source_phrase?}], summary?, source_phrase_block?}, restrictions:null|{blackout[],blackout_recurring[],weekdays_only,seasonal,advance_booking_required,advance_booking_hours,booking_frequency_limit?,late_return_penalty?}, residency_restriction:{restricted:"yes"|"no"|"unknown", scope:"town"|"ma"|null, source?, evidence?}, availability:{ "YYYY-MM-DD": "available"|"booked"|"unavailable"|"closed" }}`
- `branches[]`: `{id, library_id, name, code?}`
- `config/town_zips.json`: `{towns: {Town: ["01880", ...]}}` — 用于 L4 的「全 MA ZIP 集合」。

**Scope 不包含:** 重抓数据(用现有 `data/structured/*`);自动 booking(只到 Review 之前);L2 完整办卡资格漏斗只用现成 `card_eligibility`;**L6/L7(图书馆/分馆开馆时间)推迟** —— 当前 `libraries.json` 无 hours 字段,计划里显式跳过并在 UI 标注「未建模」。

---

## File Structure

```
web/src/data/
├── types.ts          # 重写:对齐新 JSON(Library/Attraction/Pass/Branch + 子类型)
├── load.ts           # 重写:import 新 JSON + 索引(byLib, byAttraction, passesByAttraction)
├── townZips.ts       # NEW:载入 config/town_zips.json,导出 MA_ZIPS:Set + townZips(town)
└── load.test.ts      # 改:断言新形状
web/src/lib/
├── eligibility.ts    # NEW(纯逻辑):resolvePass(pass, lib, attraction, user) -> Verdict(L1/L3/L4/L8/L9/L10)
├── eligibility.test.ts
├── recommend.ts      # NEW(纯逻辑):recommend(attractionSlug, user) -> RecommendedPass[](≤4)
├── recommend.test.ts
├── couponSummary.ts  # NEW:coupon -> 展示字符串(已有 CouponLine 逻辑抽出/对齐)
└── distance.ts       # NEW:haversine(libGeo,userGeo?) — 无 user geo 时回退到 ZIP 是否本镇
web/src/components/    # 改造为新形状(见 Phase 3 各 Task)
web/src/pages/         # AttractionsList / AttractionDetail / MyLibraryCards 改造
web/public/admin/
├── panel.html        # 重做:4 Lens 切换 + 网络分组透视表 + 漏斗模拟器 + 审计日志
├── assets/panel.css  # 沿用绿色 token,补 Lens/pivot/simulator 样式
└── assets/panel.js   # NEW/重写:载入 public/data/*.json + 引擎(移植 eligibility 逻辑) + audit override 读写
web/sync-admin.mjs    # 改:确认把 structured/*.json + town_zips.json 同步到 public/data/
data/overrides/        # 审计 override 落盘目录(已有 schema:libraries/attractions/passes/branches/<id>/<field>.json)
```

---

## Phase 0 — 数据层对齐(一切的地基)

### Task 1：重写 `web/src/data/types.ts`

**Files:**
- Modify: `web/src/data/types.ts`(整文件替换)

- [ ] **Step 1:写失败测试** `web/src/data/types.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import type { Library, Attraction, Pass } from './types';

describe('types match structured json', () => {
  it('Library has resident_zips + card_eligibility + pass_pickup_default', () => {
    const l: Library = {
      id: 'wakefield', name: 'X', town: 'Wakefield', network: 'NOBLE',
      platform: 'assabet', card_page: 'http://x', address: null, geo: null,
      card_eligibility: 'ma_resident', pass_pickup_default: 'unknown',
      resident_zips: ['01880'],
    };
    expect(l.resident_zips[0]).toBe('01880');
  });
  it('Pass has residency_restriction + pass_form + availability map', () => {
    const p: Pass = {
      library_id: 'wakefield', attraction_slug: 'mfa', pass_form: 'digital_email',
      available_at_branches: 'all', coupon: null, restrictions: null,
      residency_restriction: { restricted: 'yes', scope: 'town', source: null, evidence: null },
      availability: { '2026-06-01': 'available' },
    };
    expect(p.residency_restriction.restricted).toBe('yes');
    expect(p.availability['2026-06-01']).toBe('available');
  });
});
```

- [ ] **Step 2:跑测试确认失败** — Run: `pnpm -C web vitest run src/data/types.test.ts` → FAIL(类型不存在/字段不符)

- [ ] **Step 3:重写 types.ts**

```ts
export interface Geo { lat: number; lon: number; }
export interface Address { street: string | null; city: string | null; state: string | null; zip: string | null; }

export type CardEligibility = 'ma_resident' | 'town_resident' | 'town_or_works' | 'network' | 'none' | 'unknown';
export type PassPickup = 'same_as_card' | 'ma_resident' | 'town_resident' | 'town_cardholder_only' | 'network' | 'walkin_for_nonresidents' | 'none' | 'unknown';

export interface Library {
  id: string; name: string; town: string; network: string; platform: string;
  card_page: string | null; address: Address | null; geo: Geo | null;
  card_eligibility: CardEligibility; pass_pickup_default: PassPickup;
  eligibility_source_phrase?: string | null; pickup_source_phrase?: string | null;
  resident_zips: string[];
}

export type CouponForm = 'free' | 'percent-off' | 'dollar-off' | 'per-person-price' | 'bogo' | 'discount';
export type CapacityKind = 'people' | 'vehicle' | 'ticket' | 'unspecified';
export interface AudiencePrice { audience: string; price: number | null; age_range?: { min: number | null; max: number | null } | null; source_phrase?: string | null; }
export interface AudiencePolicy { audience: string; form: CouponForm; value?: number | null; age_range?: { min: number | null; max: number | null } | null; count?: number | null; source_phrase?: string | null; }
export interface Capacity { kind: CapacityKind; n: number | null; }
export interface Coupon { capacity: Capacity; audience_policies: AudiencePolicy[]; summary?: string | null; source_phrase_block?: string | null; }

export type DayKey = 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday';
export type Hours = Record<DayKey, string>; // "HH:MM-HH:MM" | "closed" | "unknown"

export interface VisitorEligibility { residency: 'ma_resident' | 'town_resident' | 'none' | 'unknown'; scope?: string | null; locals_free?: boolean; note?: string | null; source_phrase?: string | null; }
export interface Reservation { required: 'none' | 'timed_entry' | 'walk_in_ok'; booking_url?: string | null; lead_time_hours?: number | null; pass_holder_path?: string; pass_holder_url?: string | null; notes?: string | null; source_phrase?: string | null; }

export interface Attraction {
  slug: string; name: string; website?: string | null; phone?: string | null;
  address?: Address | null; geo?: Geo | null; description?: string | null;
  categories: string[]; hero_image?: string | null; hours?: Hours | null;
  prices: AudiencePrice[]; visitor_eligibility?: VisitorEligibility | null;
  reservation?: Reservation | null; sources: string[];
}

export type PassForm = 'digital_email' | 'physical_circ' | 'physical_coupon';
export interface Restrictions {
  blackout: { month: number; day: number | null }[]; blackout_recurring: string[];
  weekdays_only: boolean; seasonal: { start_month: number; end_month: number } | null;
  advance_booking_required: boolean; advance_booking_hours: number | null;
  booking_frequency_limit?: string | null; late_return_penalty?: string | null;
}
export interface ResidencyRestriction { restricted: 'yes' | 'no' | 'unknown'; scope: 'town' | 'ma' | null; source?: string | null; evidence?: string | null; }
export interface Pass {
  library_id: string; attraction_slug: string; pass_form: PassForm;
  available_at_branches: 'all' | string[]; source_url?: string | null;
  coupon: Coupon | null; restrictions: Restrictions | null;
  residency_restriction: ResidencyRestriction; availability: Record<string, string>;
  eligibility_override?: unknown;
}
export interface Branch { id: string; library_id: string; name: string; code?: string | null; }

export interface LibrariesJson { _meta: unknown; libraries: Library[]; }
export interface AttractionsJson { _meta: unknown; attractions: Attraction[]; }
export interface PassesJson { _meta: unknown; passes: Pass[]; }
export interface BranchesJson { _meta: unknown; branches: Branch[]; }
```

- [ ] **Step 4:跑测试确认通过** — Run: `pnpm -C web vitest run src/data/types.test.ts` → PASS

- [ ] **Step 5:commit**

```bash
git add web/src/data/types.ts web/src/data/types.test.ts
git commit -m "web/data: rewrite types to new structured shape"
```

---

### Task 2：重写 `web/src/data/load.ts` + 索引

**Files:**
- Modify: `web/src/data/load.ts`
- Modify: `web/src/data/load.test.ts`

- [ ] **Step 1:改测试**(对齐新计数:libraries 59, attractions 96, passes >900)

```ts
import { describe, it, expect } from 'vitest';
import { getLibraries, getAttractions, getAttractionBySlug, getPasses, getPassesForAttraction, getLibrary } from './load';

describe('loader', () => {
  it('59 libraries with resident_zips', () => {
    const ls = getLibraries();
    expect(ls.length).toBe(59);
    expect(getLibrary('wakefield')?.resident_zips).toContain('01880');
  });
  it('96 attractions, lookup by slug', () => {
    expect(getAttractions().length).toBeGreaterThanOrEqual(90);
    expect(getAttractionBySlug('mfa')?.name).toMatch(/Fine Arts/i);
  });
  it('passes join to attractions (no orphans)', () => {
    const slugs = new Set(getAttractions().map(a => a.slug));
    const orphan = getPasses().filter(p => !slugs.has(p.attraction_slug));
    expect(orphan.length).toBe(0);
  });
  it('passesForAttraction returns rows', () => {
    expect(getPassesForAttraction('mfa').length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2:跑失败** — Run: `pnpm -C web vitest run src/data/load.test.ts` → FAIL

- [ ] **Step 3:重写 load.ts**

```ts
import librariesJson from '../../../data/structured/libraries.json';
import attractionsJson from '../../../data/structured/attractions.json';
import passesJson from '../../../data/structured/passes.json';
import branchesJson from '../../../data/structured/branches.json';
import type { LibrariesJson, AttractionsJson, PassesJson, BranchesJson, Library, Attraction, Pass, Branch } from './types';

const libraries = (librariesJson as unknown as LibrariesJson).libraries;
const attractions = (attractionsJson as unknown as AttractionsJson).attractions;
const passes = (passesJson as unknown as PassesJson).passes;
const branches = (branchesJson as unknown as BranchesJson).branches;

const libById = new Map(libraries.map(l => [l.id, l]));
const attrBySlug = new Map(attractions.map(a => [a.slug, a]));
const passesByAttr = new Map<string, Pass[]>();
for (const p of passes) {
  const arr = passesByAttr.get(p.attraction_slug) ?? [];
  arr.push(p); passesByAttr.set(p.attraction_slug, arr);
}
const branchesByLib = new Map<string, Branch[]>();
for (const b of branches) {
  const arr = branchesByLib.get(b.library_id) ?? [];
  arr.push(b); branchesByLib.set(b.library_id, arr);
}

export const getLibraries = (): Library[] => libraries;
export const getLibrary = (id: string): Library | undefined => libById.get(id);
export const getAttractions = (): Attraction[] => attractions;
export const getAttractionBySlug = (slug: string): Attraction | undefined => attrBySlug.get(slug);
export const getPasses = (): Pass[] => passes;
export const getPassesForAttraction = (slug: string): Pass[] => passesByAttr.get(slug) ?? [];
export const getBranchesForLibrary = (id: string): Branch[] => branchesByLib.get(id) ?? [];
```

- [ ] **Step 4:跑通** — Run: `pnpm -C web vitest run src/data/load.test.ts` → PASS（若 tsconfig 报 JSON import,确认 `resolveJsonModule:true` 已开;新数据较大,vite 默认支持）

- [ ] **Step 5:commit**

```bash
git add web/src/data/load.ts web/src/data/load.test.ts
git commit -m "web/data: loader + indexes for new shape (0 orphans assertion)"
```

---

### Task 3：`townZips.ts`（MA 全 ZIP 集合,L4 用）

**Files:**
- Create: `web/src/data/townZips.ts`
- Create: `web/src/data/townZips.test.ts`

- [ ] **Step 1:失败测试**

```ts
import { describe, it, expect } from 'vitest';
import { MA_ZIPS, isMaZip, townZips } from './townZips';
describe('townZips', () => {
  it('Wakefield 01880 is a MA zip', () => { expect(isMaZip('01880')).toBe(true); });
  it('out-of-state zip is not', () => { expect(isMaZip('10001')).toBe(false); });
  it('townZips(Wakefield) -> [01880]', () => { expect(townZips('Wakefield')).toContain('01880'); });
  it('MA_ZIPS non-empty', () => { expect(MA_ZIPS.size).toBeGreaterThan(50); });
});
```

- [ ] **Step 2:失败** — Run: `pnpm -C web vitest run src/data/townZips.test.ts`

- [ ] **Step 3:实现**

```ts
import townZipsJson from '../../../config/town_zips.json';
const towns = (townZipsJson as { towns: Record<string, string[]> }).towns;
export const MA_ZIPS: Set<string> = new Set(Object.values(towns).flat());
export const isMaZip = (zip: string): boolean => MA_ZIPS.has(zip);
export const townZips = (town: string): string[] => towns[town] ?? [];
```

- [ ] **Step 4:通过** — Run: `pnpm -C web vitest run src/data/townZips.test.ts`

- [ ] **Step 5:确认 sync-admin.mjs 把 town_zips.json 同步给 admin**(读 `web/sync-admin.mjs`,若没复制 `config/town_zips.json` → `web/public/data/town_zips.json`,加上)

- [ ] **Step 6:commit**

```bash
git add web/src/data/townZips.ts web/src/data/townZips.test.ts web/sync-admin.mjs
git commit -m "web/data: town->zip + MA zip set for residency layer"
```

---

## Phase 1 — 资格漏斗引擎（纯逻辑,TDD,无 React）

> 用户输入(来自 `useCardpack`):`{ homeZip: string, heldLibraryIds: string[] }`。引擎对一条 Pass 输出能否预订 + 卡在哪层。**只实现有数据支撑的层**:L1(持卡/网络)、L3(取 pass 居住资格 = `residency_restriction` + `resident_zips`/MA)、L4(景点 visitor_eligibility)、L8(blackout/平日/季节)、L9(提前预约)、L10(当日库存)。**L2/L6/L7 推迟**(L2 仅用 card_eligibility 做轻提示;L6/L7 无 library hours,跳过)。unknown 资格 → 判「通过 + ⚠」。

### Task 4：`eligibility.ts` — L1 持卡/网络层

**Files:**
- Create: `web/src/lib/eligibility.ts`
- Create: `web/src/lib/eligibility.test.ts`

- [ ] **Step 1:失败测试**

```ts
import { describe, it, expect } from 'vitest';
import { checkL1Card } from './eligibility';
import { getLibrary } from '../data/types'; // NOTE: use real loader in impl; here stub
// Use real data via load in impl test:
import { getLibrary as realLib } from '../data/load';

describe('L1 card/network', () => {
  it('holding the issuing library card passes', () => {
    const lib = realLib('reading')!;
    expect(checkL1Card(lib, ['reading']).ok).toBe(true);
  });
  it('holding a same-network sibling card passes', () => {
    const lib = realLib('reading')!; // NOBLE
    expect(checkL1Card(lib, ['wakefield']).ok).toBe(true); // wakefield NOBLE
  });
  it('holding only a different-network card fails', () => {
    const lib = realLib('reading')!; // NOBLE
    expect(checkL1Card(lib, ['somerville']).ok).toBe(false); // Minuteman
  });
});
```

- [ ] **Step 2:失败** — Run: `pnpm -C web vitest run src/lib/eligibility.test.ts`

- [ ] **Step 3:实现 L1**(加到 eligibility.ts)

```ts
import type { Library, Attraction, Pass } from '../data/types';
import { getLibrary } from '../data/load';
import { isMaZip } from '../data/townZips';

export interface LayerResult { ok: boolean; reason?: string; warn?: boolean; }

export function checkL1Card(lib: Library, heldLibraryIds: string[]): LayerResult {
  if (heldLibraryIds.includes(lib.id)) return { ok: true };
  const heldNetworks = new Set(
    heldLibraryIds.map(id => getLibrary(id)?.network).filter(Boolean) as string[]
  );
  if (heldNetworks.has(lib.network)) return { ok: true };
  return { ok: false, reason: `你没有 ${lib.network} 网络的卡` };
}
```

- [ ] **Step 4:通过** — Run: `pnpm -C web vitest run src/lib/eligibility.test.ts`

- [ ] **Step 5:commit**

```bash
git add web/src/lib/eligibility.ts web/src/lib/eligibility.test.ts
git commit -m "web/lib: eligibility L1 card/network layer"
```

---

### Task 5：`eligibility.ts` — L3 取 pass 居住资格层

**Files:**
- Modify: `web/src/lib/eligibility.ts`
- Modify: `web/src/lib/eligibility.test.ts`

- [ ] **Step 1:加失败测试**

```ts
import { checkL3Residency } from './eligibility';
import { getLibrary as RL } from '../data/load';

describe('L3 residency (pass pickup)', () => {
  const lib = RL('wakefield')!; // resident_zips ['01880']
  it('town-restricted pass: home zip in town -> ok', () => {
    const r = checkL3Residency({ restricted: 'yes', scope: 'town', source: null, evidence: null }, lib, '01880');
    expect(r.ok).toBe(true);
  });
  it('town-restricted pass: home zip elsewhere -> blocked', () => {
    const r = checkL3Residency({ restricted: 'yes', scope: 'town', source: null, evidence: null }, lib, '02139');
    expect(r.ok).toBe(false);
  });
  it('ma-scope: any MA zip ok', () => {
    const r = checkL3Residency({ restricted: 'yes', scope: 'ma', source: null, evidence: null }, lib, '02139');
    expect(r.ok).toBe(true);
  });
  it('open pass -> ok', () => {
    expect(checkL3Residency({ restricted: 'no', scope: null, source: null, evidence: null }, lib, '99999').ok).toBe(true);
  });
  it('unknown -> ok but warn', () => {
    const r = checkL3Residency({ restricted: 'unknown', scope: null, source: null, evidence: null }, lib, '99999');
    expect(r.ok).toBe(true); expect(r.warn).toBe(true);
  });
});
```

- [ ] **Step 2:失败** — Run vitest

- [ ] **Step 3:实现 L3**

```ts
import type { ResidencyRestriction } from '../data/types';

export function checkL3Residency(rr: ResidencyRestriction, lib: Library, homeZip: string): LayerResult {
  if (rr.restricted === 'no') return { ok: true };
  if (rr.restricted === 'unknown') return { ok: true, warn: true, reason: '取 pass 资格未确认' };
  // restricted === 'yes'
  if (rr.scope === 'town') {
    return lib.resident_zips.includes(homeZip)
      ? { ok: true }
      : { ok: false, reason: `${lib.town} 仅本镇居民可取此 pass` };
  }
  if (rr.scope === 'ma') {
    return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: '此 pass 仅 MA 居民可取' };
  }
  return { ok: true, warn: true };
}
```

- [ ] **Step 4:通过** — Run vitest

- [ ] **Step 5:commit** `git commit -am "web/lib: eligibility L3 residency layer"`

---

### Task 6：`eligibility.ts` — L4 景点 visitor residency 层

**Files:** Modify `eligibility.ts` + test

- [ ] **Step 1:失败测试**

```ts
import { checkL4VisitorResidency } from './eligibility';
describe('L4 attraction visitor residency', () => {
  it('no rule -> ok', () => { expect(checkL4VisitorResidency(null, '99999').ok).toBe(true); });
  it('residency none -> ok', () => { expect(checkL4VisitorResidency({ residency:'none' }, '99999').ok).toBe(true); });
  it('ma_resident: MA zip ok, non-MA blocked', () => {
    expect(checkL4VisitorResidency({ residency:'ma_resident' }, '01880').ok).toBe(true);
    expect(checkL4VisitorResidency({ residency:'ma_resident' }, '10001').ok).toBe(false);
  });
  it('unknown -> ok+warn', () => {
    expect(checkL4VisitorResidency({ residency:'unknown' }, '10001')).toMatchObject({ ok:true, warn:true });
  });
});
```

- [ ] **Step 2:失败** — Run vitest
- [ ] **Step 3:实现**

```ts
import type { VisitorEligibility } from '../data/types';
export function checkL4VisitorResidency(ve: VisitorEligibility | null | undefined, homeZip: string): LayerResult {
  if (!ve || ve.residency === 'none') return { ok: true };
  if (ve.residency === 'unknown') return { ok: true, warn: true, reason: '景点访客资格未确认' };
  if (ve.residency === 'ma_resident') return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: '该景点仅 MA 居民可入' };
  // town_resident: scope is the town name; we only have ZIP -> can't verify town precisely -> warn-pass
  return { ok: true, warn: true, reason: `该景点可能仅 ${ve.scope ?? '本镇'} 居民,建议核对` };
}
```

- [ ] **Step 4:通过** — Run vitest
- [ ] **Step 5:commit** `git commit -am "web/lib: eligibility L4 visitor residency layer"`

---

### Task 7：`eligibility.ts` — L8/L9/L10 时效层（针对某一天）

**Files:** Modify `eligibility.ts` + test

- [ ] **Step 1:失败测试**

```ts
import { checkL8Restrictions, checkL10Availability } from './eligibility';
describe('time layers', () => {
  it('blackout month/day on target date blocks (L8)', () => {
    const r = checkL8Restrictions({ blackout:[{month:7,day:4}], blackout_recurring:[], weekdays_only:false, seasonal:null, advance_booking_required:false, advance_booking_hours:null }, new Date('2026-07-04'));
    expect(r.ok).toBe(false);
  });
  it('weekdays_only blocks weekend (L8)', () => {
    const r = checkL8Restrictions({ blackout:[], blackout_recurring:[], weekdays_only:true, seasonal:null, advance_booking_required:false, advance_booking_hours:null }, new Date('2026-06-06')); // Saturday
    expect(r.ok).toBe(false);
  });
  it('availability available -> ok, booked -> blocked (L10)', () => {
    expect(checkL10Availability({ '2026-06-01':'available' }, '2026-06-01').ok).toBe(true);
    expect(checkL10Availability({ '2026-06-01':'booked' }, '2026-06-01').ok).toBe(false);
  });
  it('availability missing date -> unknown warn (L10)', () => {
    expect(checkL10Availability({}, '2026-06-01')).toMatchObject({ ok:true, warn:true });
  });
});
```

- [ ] **Step 2:失败** — Run vitest
- [ ] **Step 3:实现**

```ts
import type { Restrictions } from '../data/types';
const WD = ['sundays','mondays','tuesdays','wednesdays','thursdays','fridays','saturdays'];
export function checkL8Restrictions(r: Restrictions | null, date: Date): LayerResult {
  if (!r) return { ok: true };
  const m = date.getMonth() + 1, d = date.getDate(), dow = date.getDay();
  for (const b of r.blackout) if (b.month === m && (b.day == null || b.day === d)) return { ok: false, reason: '该日为 blackout' };
  if (r.blackout_recurring.includes(WD[dow])) return { ok: false, reason: '该星期几不可用' };
  if (r.weekdays_only && (dow === 0 || dow === 6)) return { ok: false, reason: '仅平日可用' };
  if (r.seasonal) { const { start_month, end_month } = r.seasonal; const inSeason = start_month <= end_month ? (m >= start_month && m <= end_month) : (m >= start_month || m <= end_month); if (!inSeason) return { ok: false, reason: '季节性闭区' }; }
  return { ok: true };
}
export function checkL10Availability(av: Record<string,string>, isoDate: string): LayerResult {
  const s = av[isoDate];
  if (s === 'available') return { ok: true };
  if (s == null) return { ok: true, warn: true, reason: '该日库存未知' };
  return { ok: false, reason: s === 'booked' ? '该日已订满' : '该日不可预约' };
}
```

- [ ] **Step 4:通过** — Run vitest
- [ ] **Step 5:commit** `git commit -am "web/lib: eligibility L8/L10 time layers"`

---

### Task 8：`resolvePass` — 串起所有层 + 「卡在哪层」

**Files:** Modify `eligibility.ts` + test

- [ ] **Step 1:失败测试**

```ts
import { resolvePass } from './eligibility';
import { getLibrary as RL, getAttractionBySlug as RA } from '../data/load';
describe('resolvePass', () => {
  it('wakefield resident-only pass: Wakefield home ok, other-zip blocked at L3', () => {
    const lib = RL('wakefield')!; const attr = RA('mfa')!;
    const pass = { library_id:'wakefield', attraction_slug:'mfa', pass_form:'physical_coupon' as const, available_at_branches:'all' as const, coupon:null, restrictions:null, residency_restriction:{restricted:'yes' as const, scope:'town' as const, source:null, evidence:null}, availability:{} };
    const home = resolvePass(pass, lib, attr, { homeZip:'01880', heldLibraryIds:['wakefield'] });
    expect(home.eligible).toBe(true);
    const away = resolvePass(pass, lib, attr, { homeZip:'02139', heldLibraryIds:['wakefield'] });
    expect(away.eligible).toBe(false);
    expect(away.blockedLayer).toBe('L3');
  });
});
```

- [ ] **Step 2:失败** — Run vitest
- [ ] **Step 3:实现**

```ts
export interface User { homeZip: string; heldLibraryIds: string[]; }
export interface PassVerdict { eligible: boolean; blockedLayer?: string; reasons: string[]; warnings: string[]; }

export function resolvePass(pass: Pass, lib: Library, attr: Attraction, user: User, date?: Date): PassVerdict {
  const reasons: string[] = [], warnings: string[] = [];
  const layers: [string, LayerResult][] = [
    ['L1', checkL1Card(lib, user.heldLibraryIds)],
    ['L3', checkL3Residency(pass.residency_restriction, lib, user.homeZip)],
    ['L4', checkL4VisitorResidency(attr.visitor_eligibility, user.homeZip)],
  ];
  if (date) {
    layers.push(['L8', checkL8Restrictions(pass.restrictions, date)]);
    const iso = date.toISOString().slice(0, 10);
    layers.push(['L10', checkL10Availability(pass.availability, iso)]);
  }
  for (const [name, r] of layers) {
    if (r.warn && r.reason) warnings.push(r.reason);
    if (!r.ok) return { eligible: false, blockedLayer: name, reasons: [r.reason ?? name], warnings };
  }
  return { eligible: true, reasons, warnings };
}
```

- [ ] **Step 4:通过** — Run vitest
- [ ] **Step 5:commit** `git commit -am "web/lib: resolvePass funnel + blockedLayer"`

---

## Phase 2 — 推荐引擎

### Task 9：`couponSummary.ts`（coupon → 展示串 + 力度分）

**Files:** Create `web/src/lib/couponSummary.ts` + test

- [ ] **Step 1:失败测试**

```ts
import { couponSummary, couponStrength } from './couponSummary';
describe('couponSummary', () => {
  it('uses backend summary when present', () => {
    expect(couponSummary({ capacity:{kind:'people',n:4}, audience_policies:[{audience:'Everyone',form:'percent-off',value:50}], summary:'50% off' })).toBe('50% off');
  });
  it('free strongest, bogo weakest in strength order', () => {
    expect(couponStrength('free')).toBeGreaterThan(couponStrength('percent-off'));
    expect(couponStrength('percent-off')).toBeGreaterThan(couponStrength('bogo'));
  });
  it('null coupon -> placeholder', () => { expect(couponSummary(null)).toBe('优惠详情未知'); });
});
```

- [ ] **Step 2:失败** — Run vitest
- [ ] **Step 3:实现**

```ts
import type { Coupon, CouponForm } from '../data/types';
const STRENGTH: Record<CouponForm, number> = { free:6, 'percent-off':5, 'dollar-off':4, 'per-person-price':3, discount:2, bogo:1 };
export const couponStrength = (f: CouponForm): number => STRENGTH[f] ?? 0;
export function couponSummary(c: Coupon | null): string {
  if (!c) return '优惠详情未知';
  if (c.summary) return c.summary;
  const p = c.audience_policies[0];
  if (!p) return '优惠详情未知';
  switch (p.form) {
    case 'free': return 'FREE';
    case 'percent-off': return `${p.value ?? ''}% off`;
    case 'dollar-off': return `$${p.value ?? ''} off`;
    case 'per-person-price': return `$${p.value ?? ''}/人`;
    case 'bogo': return '买一送一';
    default: return '折扣';
  }
}
export function passStrength(c: Coupon | null): number {
  if (!c || !c.audience_policies.length) return 0;
  return Math.max(...c.audience_policies.map(p => couponStrength(p.form)));
}
```

- [ ] **Step 4:通过** — Run vitest
- [ ] **Step 5:commit** `git commit -am "web/lib: coupon summary + strength"`

---

### Task 10：`recommend.ts`（≤4 条:Email 1 + Pickup/Return 3,打分排序）

**Files:** Create `web/src/lib/recommend.ts` + test

- [ ] **Step 1:失败测试**

```ts
import { recommend } from './recommend';
describe('recommend', () => {
  it('returns at most 4, dedups email passes, eligible-first', () => {
    const recs = recommend('mfa', { homeZip:'01880', heldLibraryIds:['wakefield','reading','somerville','wilmington','bpl'] });
    expect(recs.length).toBeLessThanOrEqual(4);
    const emails = recs.filter(r => r.pass.pass_form === 'digital_email');
    expect(emails.length).toBeLessThanOrEqual(1);
  });
});
```

- [ ] **Step 2:失败** — Run vitest
- [ ] **Step 3:实现**

```ts
import { getPassesForAttraction, getLibrary, getAttractionBySlug } from '../data/load';
import { resolvePass, type User, type PassVerdict } from './eligibility';
import { passStrength } from './couponSummary';
import type { Pass } from '../data/types';

export interface RecommendedPass { pass: Pass; verdict: PassVerdict; score: number; }

export function recommend(slug: string, user: User, date?: Date): RecommendedPass[] {
  const attr = getAttractionBySlug(slug); if (!attr) return [];
  const scored: RecommendedPass[] = [];
  for (const pass of getPassesForAttraction(slug)) {
    const lib = getLibrary(pass.library_id); if (!lib) continue;
    const verdict = resolvePass(pass, lib, attr, user, date);
    let score = passStrength(pass.coupon) * 10;
    if (!verdict.eligible) score -= 1000;            // ineligible sinks
    if (verdict.warnings.length) score -= 5;          // unknown to the back
    scored.push({ pass, verdict, score });
  }
  scored.sort((a, b) => b.score - a.score);
  // Email: dedup to best 1; Pickup/Return: up to 3.
  const out: RecommendedPass[] = [];
  const email = scored.find(r => r.pass.pass_form === 'digital_email');
  if (email) out.push(email);
  for (const r of scored) {
    if (out.length >= 4) break;
    if (r.pass.pass_form === 'digital_email') continue;
    out.push(r);
  }
  return out.slice(0, 4);
}
```

- [ ] **Step 4:通过** — Run vitest
- [ ] **Step 5:commit** `git commit -am "web/lib: pass recommendation (<=4, email-dedup, scored)"`

---

## Phase 3 — 用户端 UI 改造

> 现有组件按 v0.1 形状写。逐个改到新形状 + 接引擎。每个 Task:改组件 → 改/加该组件的 `*.test.tsx` → vitest 通过 → commit。HeroUI + 现有绿色 token 不变。

### Task 11：`MyLibraryCards` + ZIP —— 用户输入(home ZIP + 持卡)

**Files:** Modify `web/src/pages/MyLibraryCards.tsx`, `web/src/components/ZipPill.tsx`, 读 `web/src/stores/cardpack.ts`

- [ ] **Step 1**:确认 `useCardpack().pack` = `{ zip, cards }`;页面允许设 home ZIP(校验 5 位数字)+ 增删某馆卡(`saveCard/removeCard`)。BPL 卡时显著提示「必须实体卡,eCard 不能借 pass」(发现 3)。
- [ ] **Step 2**:测试 `MyLibraryCards.test.tsx`:设 ZIP「01880」后 `pack.zip==='01880'`;加 bpl 卡时渲染出 eCard 警示文案。
- [ ] **Step 3**:实现(HeroUI Input + Button;BPL 警示用 `--or`/`--rd` token)。
- [ ] **Step 4**:`pnpm -C web vitest run src/pages/MyLibraryCards.test.tsx` PASS
- [ ] **Step 5**:commit `git commit -am "web/ui: home ZIP + card pack input, BPL eCard warning"`

### Task 12：`AttractionCard` —— 列表卡片显示资格角标 + 最优优惠

**Files:** Modify `web/src/components/AttractionCard.tsx` + test

- [ ] **Step 1**:卡片输入 `attraction` + `user`(来自 cardpack)。用 `recommend(slug,user)` 取最优一条:显示其 `couponSummary`;若 `verdict.eligible===false` 显示灰态「不可领」+ `blockedLayer` 简短原因;若 `warnings` 非空显示 ⚠「资格未确认」。hero_image 缺失时回退 `public/placeholders/<category>.svg`。
- [ ] **Step 2**:`AttractionCard.test.tsx`:给定持 wakefield 卡 + home 01880,mfa 卡片显示优惠摘要且非灰态;给定 home 02139 + 仅 wakefield 卡,显示 ⚠ 或受限态。
- [ ] **Step 3**:实现(沿用现有卡片结构 + 绿色 token;角标:eligible 绿 `--g`,warn 橙 `--or`,blocked 灰)。
- [ ] **Step 4**:vitest PASS
- [ ] **Step 5**:commit `git commit -am "web/ui: AttractionCard eligibility badge + best coupon"`

### Task 13：`AttractionDetail` —— 4 条推荐 + 两步指引 + 限制提示

**Files:** Modify `web/src/pages/AttractionDetail.tsx`, `web/src/components/CouponRow.tsx`/`CouponLine.tsx`, `web/src/components/detail/*`

- [ ] **Step 1**:详情页用 `recommend(slug,user,date?)` 渲染最多 4 条 pass 行,每行:图书馆名 + 距离/town、`couponSummary`、`PassTypeLabel`(digital/pickup/pickup-return)、资格判定(eligible/blocked+层/⚠)。
- [ ] **Step 2**:若 `attraction.reservation.required==='timed_entry'` → 顶部显示**两步指引**(「① 从图书馆领码/取 pass ② 去景点官网用码订时段」+ `reservation.booking_url`)(发现 4)。
- [ ] **Step 3**:`physical_circ` 行显示 blanket 提示「需到馆取并归还,注意逾期罚金」;若 `restrictions.late_return_penalty` 有原文则展示;`restrictions.booking_frequency_limit` 有则展示「预订频率限制:<原文>」。
- [ ] **Step 4**:测试 `AttractionDetail.test.tsx`:timed_entry 景点渲染两步指引;physical_circ pass 渲染归还提示;有 booking_frequency_limit 的渲染该原文。
- [ ] **Step 5**:vitest PASS;commit `git commit -am "web/ui: AttractionDetail 4 recs + two-step + restriction notes"`

### Task 14：`CouponCalendar` / `DatePicker` —— 按日 availability

**Files:** Modify `web/src/components/CouponCalendar.tsx`, `web/src/components/DatePicker.tsx` + tests

- [ ] **Step 1**:日历从 `pass.availability`(`{date:status}`)渲染:available 绿可点、booked/unavailable 灰、closed 划掉;选日后把 `date` 传给 `resolvePass` 重算该行资格(L8/L10)。
- [ ] **Step 2**:测试:available 日可点且 `resolvePass(...,date)` eligible;booked 日不可点。
- [ ] **Step 3**:实现(绿色 token:available `--g-light` 底 / `--g` 字)。
- [ ] **Step 4**:vitest PASS;commit `git commit -am "web/ui: calendar from availability map + per-date verdict"`

### Task 15：`BookingConfirmModal` —— 跳转图书馆预订页(不自动下单)

**Files:** Modify `web/src/components/BookingConfirmModal.tsx` + test

- [ ] **Step 1**:确认按钮打开 `pass.source_url`(图书馆该 pass 预订页)新标签;若 timed_entry 再提示去景点官网。**绝不**在站内自动提交预订。
- [ ] **Step 2**:测试:点确认调用 `window.open(pass.source_url)`(mock)。
- [ ] **Step 3**:实现。
- [ ] **Step 4**:vitest PASS;commit `git commit -am "web/ui: booking modal opens library page (no auto-book)"`

### Task 16：用户端整体跑通

- [ ] **Step 1**:`pnpm -C web run dev`,手动验证:设 home ZIP=01880 + 持 wakefield/reading/somerville/wilmington/bpl 5 卡 → 浏览列表 → 进 mfa 详情 → 看 4 条推荐资格正确(wakefield resident-only 在 01880 显示可领;切 home 到 02139 后 wakefield 行变受限,reading 行仍可领)。
- [ ] **Step 2**:`pnpm -C web run build` 通过(`tsc -b && vite build`)。
- [ ] **Step 3**:commit(若有构建期修复)`git commit -am "web: user app builds + manual e2e ok"`

---

## Phase 4 — Admin Panel 重做(绿色主题,4 Lens + 漏斗模拟器 + 审计 override)

> 原生 HTML/CSS/JS,**不进 React**。沿用 `web/public/admin/assets/panel.css` 的绿色 token(`--g:#1B5740` 等),只新增布局/控件样式。数据由 `web/sync-admin.mjs` 同步到 `web/public/data/`(libraries/attractions/passes/branches/town_zips)。

### Task 17：panel.js 数据加载 + 引擎移植

**Files:** Modify `web/public/admin/assets/panel.js`(或新建),`web/sync-admin.mjs`

- [ ] **Step 1**:确认 sync-admin.mjs 把 4 个 structured + town_zips.json 复制到 `web/public/data/`。
- [ ] **Step 2**:panel.js `fetch('./data/*.json')` 载入;移植 `checkL1Card/checkL3Residency/checkL4/.../resolvePass`(纯 JS 版,逻辑同 Phase 1)。
- [ ] **Step 3**:浏览器手测:`resolvePass` 对 wakefield/mfa/01880 返回 eligible。
- [ ] **Step 4**:commit `git commit -am "admin: load structured data + funnel engine (vanilla JS)"`

### Task 18：4 个 Lens 切换 + 网络分组透视表

**Files:** Modify `panel.html` + `panel.css` + `panel.js`

- [ ] **Step 1**:顶栏 4 个 Lens 按钮(A 卡覆盖查询/B 资格政策审查/C 优惠细节/D 分馆与景点预约),对应 spec §7.1 的行单位与默认列。
- [ ] **Step 2**:中部大表**按 network 分组折叠**(列头「NOBLE · 16 家 [+]」);顶栏可输入 home ZIP + 持卡列表 + 日期先过滤再渲染。
- [ ] **Step 3**:样式全用绿色 token(分组头 `--g` 底白字,行 hover `--g-pale`)。
- [ ] **Step 4**:手测 4 个 Lens 切换显示对应列;分组可展开折叠。
- [ ] **Step 5**:commit `git commit -am "admin: 4 lenses + network-grouped pivot (green theme)"`

### Task 19：漏斗模拟器(L1–L10,给「下一个可用日」)

**Files:** Modify `panel.html` + `panel.js`

- [ ] **Step 1**:右上小工具:输入 town/home ZIP + 持卡 + 景点 + 日期 → 调 `resolvePass` 显示卡在哪层 + 原因;对时效层(L8/L10)用 `pass.availability` 找「下一个 available 日」。
- [ ] **Step 2**:手测:wakefield/mfa + 02139 → 卡在 L3 显示「仅本镇」;reading/mfa + 02139 → 全通过。
- [ ] **Step 3**:commit `git commit -am "admin: funnel simulator with next-available day"`

### Task 20：审计 override 读写 + 日志

**Files:** Modify `panel.js`;写 `data/overrides/<entity>/<id>/<field>.json`(浏览器端无法直接写盘 → 用「导出 override JSON」按钮下载,或 localStorage 暂存 + 复制按钮;落盘由人工/脚本放进 `data/overrides/`,build 时 `apply_overrides` 合并)

- [ ] **Step 1**:单元格 hover 出 ✅已核 / ✏️改值 / 📝备注;改值/备注生成一条 override 记录 `{target, status, corrected_value, note, audited_at, audited_by}`。
- [ ] **Step 2**:override 暂存 localStorage;「导出」按钮下载成 `<entity>/<id>/<field>.json` 结构(对齐 `src/malibbene/common/audit_overrides.py` 的 target 命名 `entity:id:field`)。
- [ ] **Step 3**:底部审计日志:按字段/审计人/日期/状态反查 localStorage 里的 override。
- [ ] **Step 4**:手测:改 mfa 成人票价 → 导出 JSON → 放进 `data/overrides/attractions/mfa/price.json` → `python scripts/build_all.py` → `attractions.json` 该值被覆盖(验证审计层闭环)。
- [ ] **Step 5**:commit `git commit -am "admin: audit override capture/export + audit log query"`

### Task 21：Admin 整体跑通

- [ ] **Step 1**:`pnpm -C web run dev`,开 `/admin/panel.html`,4 Lens + 分组 + 模拟器 + override 全可用,绿色主题一致。
- [ ] **Step 2**:commit `git commit -am "admin: panel redesign complete"`

---

## Phase 5 — 集成验证

### Task 22：构建 + 测试 + 数据回归

- [ ] **Step 1**:`pnpm -C web run test`(vitest 全绿)
- [ ] **Step 2**:`pnpm -C web run build`(用户端构建通过)
- [ ] **Step 3**:`python scripts/audit_data.py`(数据仍 0 FAIL — 确认前端没改坏 structured)
- [ ] **Step 4**:`pnpm -C web run preview`,验证用户端 SPA 路由 + admin panel 都能直接刷新打开
- [ ] **Step 5**:commit `git commit -am "web: integration verified (vitest + build + audit + preview)"`

---

## Self-Review

**Spec coverage(对 `docs/specs/2026-05-20-admin-panel-redesign.md`):**
| Spec 节 | 实现 Task |
|---|---|
| 3.1 景点(prices/visitor_eligibility/reservation/persona) | Task 1, 13 |
| 3.2 图书馆(card_eligibility / pass_pickup_default 两字段) | Task 1, 11 |
| 3.3 联盟(仅标签 + 分组) | Task 4(L1 network), 18(分组) |
| 3.4 Pass 四层(领取方式/coupon/override/时间限制) | Task 1, 9, 10, 13, 7 |
| 3.5 审计层 override | Task 20 |
| 四 发现 1(办卡≠取pass) | Task 1(两字段), 5 |
| 发现 2(联盟内不通用) | Task 5(residency_restriction 逐 pass) |
| 发现 3(BPL eCard) | Task 11(警示) |
| 发现 4(timed-entry 两步) | Task 13 |
| 发现 5(BOGO/blackout/资助混淆) | Task 9(BOGO 力度最低), 7(blackout 月日), override(资助误判靠人工) |
| 发现 6(景点 residency) | Task 6(L4) |
| 发现 7(BPL 分馆) | Task 18/19(branches 展示);L7 推迟(无 hours) |
| 五 漏斗 L1–L10 | Task 4–8(L1/L3/L4/L8/L10);**L2/L6/L7/L9 部分或推迟,见 Scope** |
| 六 推荐逻辑(≤4,Email 1+3,打分) | Task 9, 10 |
| 七 Admin(4 Lens/透视/模拟器/日志) | Task 17–21 |
| 绿色主题 | Phase 3/4 全程沿用 token |

**已知缺口(诚实标注,执行时按此对待):**
- **L6/L7(图书馆/分馆开馆时间)无数据** —— `libraries.json`/`branches.json` 无 hours。UI/模拟器跳过这两层,标「未建模」。若要补:需爬库馆 hours(另开数据任务)。
- **L2 办卡资格漏斗**仅用现成 `card_eligibility` 做轻提示,不做完整「能否办卡」拦截。
- **L9 提前预约**:`restrictions.advance_booking_required/hours` 存在但精确「距今 +N 小时」判断依赖实时时钟,UI 仅提示不硬拦。
- **距离权重**:`distance.ts` 需 user geo;当前只有 home ZIP → 退化为「图书馆 town 是否=用户镇」加分,无精确距离(可后续补 ZIP→geo)。

**Placeholder 扫描:** 已检查,逻辑层(Phase 0–2)每步含完整代码;UI 层(Phase 3–4)每个 Task 给出组件契约 + 关键渲染规则 + 测试断言 + 绿色 token 用法,无 TBD。

**Type 一致性:** `User{homeZip,heldLibraryIds}`、`LayerResult{ok,reason?,warn?}`、`PassVerdict{eligible,blockedLayer?,reasons,warnings}`、`RecommendedPass{pass,verdict,score}`、`couponSummary/passStrength/recommend/resolvePass` 在 Phase 1/2/3 引用一致。
