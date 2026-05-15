# Plan 4 — Frontend Features Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to execute task-by-task.

**Goal:** 在 plan-3 scaffold 之上把 spec(`docs/superpowers/specs/2026-05-15-product-design.md`)的产品功能实现出来:真实卡片 UI、tag 推荐算法、详情页、My passes 设置页、跳转预约 flow。

**Architecture:** 纯函数(tag algorithm / distance / fallback price)放 `lib/`,独立测试;Zustand store 集中用户状态(cardpack / favorites / ZIP);React 组件按 page 划分,从 store + data loader 读数据。Dev server 验证用 `pnpm run build` + `pnpm test`(subagent 不开 dev server),最终人工 smoke test。

**Tech Stack:** plan-3 已就绪(React 19, Vite, HeroUI v2, Tailwind v4, Zustand, react-router 7, Vitest)

---

## 0. 设计 review(从 spec 浓缩)

| 决策 | spec 来源 | 影响 plan-4 |
|---|---|---|
| List 单日,Detail 多日(≤30) | spec §4.4 / §6.3 | List 顶部 date picker = single;detail = range |
| 卡片 4 行 layout | spec §4.6 | header (img+name+town+intro+原价) + 1 tag row |
| Tag 算法 ≤4 个 | spec §5 | digital(1) → physical(N, by 折扣 desc, 距离 asc) → loan-card(N, same) |
| 排序:Favorites → A-Z | spec §4.5 | 默认。Distance/Discount 是可选 |
| Guest/admin banner | spec §4.3 | 顶部条幅,登录后消失 |
| 游客卡片:不显示 tag,显示 "Sign in to view X options" | spec §4.6.5 | 卡片渲染分支 |
| Favorites 双入口 | spec §4.6.3 | 列表卡片左上 + 详情页内按钮 |
| Pass 点击 = copy barcode → 跳转 | spec §7 | confirm modal + clipboard API |
| 卡包字段 | spec §8.3 | barcode + last_name + PIN(optional) per library + ZIP |
| 数据存 localStorage namespaced by username | spec §3.2 | `museumpass-ma.<username>.cardpack` 等 |
| 全 UI 英文 | glossary | 文案全 English |

---

## File / responsibility split

```
web/src/
├── stores/                        # NEW dir
│   ├── cardpack.ts                # cards (barcode/lastname/pin per lib) + ZIP, per-user
│   ├── cardpack.test.ts
│   ├── favorites.ts               # favorited attraction slugs, per-user
│   └── favorites.test.ts
├── lib/
│   ├── localStorage.ts            # (existing, namespace-by-user helpers added)
│   ├── distance.ts                # haversine + getDistanceForLibrary(libId, userZipCoords)
│   ├── distance.test.ts
│   ├── tag-algorithm.ts           # core tag picker
│   ├── tag-algorithm.test.ts
│   ├── price-fallback.ts          # original_price -> display strings (handles null)
│   ├── price-fallback.test.ts
│   └── booking.ts                 # copy barcode + open URL
├── components/
│   ├── TopBar.tsx                 # (existing — add banner slot)
│   ├── Banner.tsx                 # NEW — guest/admin banner
│   ├── AttractionCard.tsx         # NEW — list page card
│   ├── PassTag.tsx                # NEW — single tag (digital/physical/loan-card with color + icon)
│   ├── FavoriteButton.tsx         # NEW — heart toggle, reads/writes favorites store
│   ├── DatePicker.tsx             # NEW — single-day picker for list page
│   ├── DateRangePicker.tsx        # NEW — for detail page
│   ├── SortDropdown.tsx           # NEW — list page sort selector
│   ├── BookingConfirmModal.tsx    # NEW — barcode copy + redirect
│   └── SignInModal.tsx            # (existing)
└── pages/
    ├── AttractionsList.tsx        # (rewrite — real UI)
    ├── AttractionDetail.tsx       # (rewrite — real UI)
    └── MyPasses.tsx               # (rewrite — real settings UI)
```

---

## Task 1 — Cardpack + Favorites stores

**Why:** Foundation: persona-aware per-user state, persisted to localStorage. Mock auth users (alex/rbt/admin) seed default cardpacks so demo state is meaningful.

**Files:**
- Update: `web/src/lib/localStorage.ts` (add `lsGetUser/lsSetUser` namespaced helpers)
- Create: `web/src/stores/cardpack.ts`
- Create: `web/src/stores/cardpack.test.ts`
- Create: `web/src/stores/favorites.ts`
- Create: `web/src/stores/favorites.test.ts`

### Step 1.1: Extend localStorage helpers

Edit `web/src/lib/localStorage.ts` to add user-namespaced helpers:

```typescript
const PREFIX = 'museumpass-ma';

export function lsGet<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`${PREFIX}.${key}`);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function lsSet<T>(key: string, value: T): void {
  try {
    localStorage.setItem(`${PREFIX}.${key}`, JSON.stringify(value));
  } catch { /* swallow */ }
}

export function lsRemove(key: string): void {
  try {
    localStorage.removeItem(`${PREFIX}.${key}`);
  } catch { /* swallow */ }
}

// User-namespaced versions: when username is null (guest), uses 'guest' namespace
function userKey(username: string | null, key: string): string {
  const ns = username ?? 'guest';
  return `${ns}.${key}`;
}

export function lsGetUser<T>(username: string | null, key: string, fallback: T): T {
  return lsGet(userKey(username, key), fallback);
}

export function lsSetUser<T>(username: string | null, key: string, value: T): void {
  lsSet(userKey(username, key), value);
}
```

### Step 1.2: Cardpack store

Create `web/src/stores/cardpack.ts`:

```typescript
import { create } from 'zustand';
import { lsGetUser, lsSetUser } from '../lib/localStorage';

export interface LibraryCard {
  barcode: string;
  lastName: string;
  pin: string; // empty string = not set
}

export interface CardPack {
  zip: string;            // 5-digit, empty = not set
  cards: Record<string, LibraryCard>;  // lib_id -> card
}

const EMPTY: CardPack = { zip: '', cards: {} };

// Persona-driven seed data (loaded for demo accounts on first sign-in)
const SEEDS: Record<string, CardPack> = {
  // alex = heavy user, 5 cards
  alex: {
    zip: '01880',
    cards: {
      wakefield: { barcode: '21000000000001', lastName: 'Alex', pin: '' },
      reading:   { barcode: '21000000000002', lastName: 'Alex', pin: '' },
      bpl:       { barcode: '21000000000003', lastName: 'Alex', pin: '' },
      wilmington:{ barcode: '21000000000004', lastName: 'Alex', pin: '' },
      somerville:{ barcode: '21000000000005', lastName: 'Alex', pin: '' },
    },
  },
  // rbt = light, 1 card
  rbt: {
    zip: '01880',
    cards: {
      wakefield: { barcode: '21000000009999', lastName: 'rbt', pin: '' },
    },
  },
  // admin = empty
  admin: { zip: '', cards: {} },
};

interface CardpackState {
  username: string | null;
  pack: CardPack;
  load: (username: string | null) => void;
  saveZip: (zip: string) => void;
  saveCard: (libId: string, card: LibraryCard) => void;
  removeCard: (libId: string) => void;
}

export const useCardpack = create<CardpackState>((set, get) => ({
  username: null,
  pack: EMPTY,

  load: (username) => {
    // Try localStorage first; if absent, seed from SEEDS for known demo users
    const stored = lsGetUser<CardPack | null>(username, 'cardpack', null);
    let pack: CardPack;
    if (stored) {
      pack = stored;
    } else if (username && SEEDS[username]) {
      pack = SEEDS[username];
      lsSetUser(username, 'cardpack', pack);
    } else {
      pack = EMPTY;
    }
    set({ username, pack });
  },

  saveZip: (zip) => {
    const { username, pack } = get();
    const next = { ...pack, zip };
    lsSetUser(username, 'cardpack', next);
    set({ pack: next });
  },

  saveCard: (libId, card) => {
    const { username, pack } = get();
    const next = { ...pack, cards: { ...pack.cards, [libId]: card } };
    lsSetUser(username, 'cardpack', next);
    set({ pack: next });
  },

  removeCard: (libId) => {
    const { username, pack } = get();
    const cards = { ...pack.cards };
    delete cards[libId];
    const next = { ...pack, cards };
    lsSetUser(username, 'cardpack', next);
    set({ pack: next });
  },
}));
```

### Step 1.3: Cardpack test

Create `web/src/stores/cardpack.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useCardpack } from './cardpack';

describe('cardpack store', () => {
  beforeEach(() => {
    localStorage.clear();
    useCardpack.setState({ username: null, pack: { zip: '', cards: {} } });
  });

  it('loads empty pack for guest', () => {
    useCardpack.getState().load(null);
    expect(useCardpack.getState().pack.cards).toEqual({});
    expect(useCardpack.getState().pack.zip).toBe('');
  });

  it('seeds alex with 5 cards on first load', () => {
    useCardpack.getState().load('alex');
    const p = useCardpack.getState().pack;
    expect(Object.keys(p.cards).length).toBe(5);
    expect(p.cards.wakefield.barcode).toBeTruthy();
    expect(p.zip).toBe('01880');
  });

  it('seeds rbt with 1 card on first load', () => {
    useCardpack.getState().load('rbt');
    expect(Object.keys(useCardpack.getState().pack.cards).length).toBe(1);
  });

  it('seeds admin with 0 cards', () => {
    useCardpack.getState().load('admin');
    expect(Object.keys(useCardpack.getState().pack.cards)).toEqual([]);
    expect(useCardpack.getState().pack.zip).toBe('');
  });

  it('persists changes via saveZip', () => {
    useCardpack.getState().load('admin');
    useCardpack.getState().saveZip('02134');
    expect(useCardpack.getState().pack.zip).toBe('02134');
    // verify stored separately by reloading
    useCardpack.setState({ username: null, pack: { zip: '', cards: {} } });
    useCardpack.getState().load('admin');
    expect(useCardpack.getState().pack.zip).toBe('02134');
  });

  it('saveCard adds a new card', () => {
    useCardpack.getState().load('admin');
    useCardpack.getState().saveCard('wakefield', { barcode: '123', lastName: 'X', pin: '' });
    expect(useCardpack.getState().pack.cards.wakefield.barcode).toBe('123');
  });

  it('removeCard deletes', () => {
    useCardpack.getState().load('alex');
    useCardpack.getState().removeCard('wakefield');
    expect(useCardpack.getState().pack.cards.wakefield).toBeUndefined();
    expect(Object.keys(useCardpack.getState().pack.cards).length).toBe(4);
  });

  it('per-user namespace: alex and rbt do not share state', () => {
    useCardpack.getState().load('alex');
    useCardpack.getState().saveZip('02101');
    useCardpack.getState().load('rbt');
    expect(useCardpack.getState().pack.zip).toBe('01880');  // rbt's seed, untouched
    useCardpack.getState().load('alex');
    expect(useCardpack.getState().pack.zip).toBe('02101');  // alex's saved value preserved
  });
});
```

### Step 1.4: Favorites store

Create `web/src/stores/favorites.ts`:

```typescript
import { create } from 'zustand';
import { lsGetUser, lsSetUser } from '../lib/localStorage';

interface FavoritesState {
  username: string | null;
  slugs: Set<string>;
  load: (username: string | null) => void;
  toggle: (slug: string) => void;
  isFavorite: (slug: string) => boolean;
}

export const useFavorites = create<FavoritesState>((set, get) => ({
  username: null,
  slugs: new Set(),

  load: (username) => {
    const arr = lsGetUser<string[]>(username, 'favorites', []);
    set({ username, slugs: new Set(arr) });
  },

  toggle: (slug) => {
    const { username, slugs } = get();
    const next = new Set(slugs);
    if (next.has(slug)) next.delete(slug);
    else next.add(slug);
    lsSetUser(username, 'favorites', Array.from(next));
    set({ slugs: next });
  },

  isFavorite: (slug) => get().slugs.has(slug),
}));
```

### Step 1.5: Favorites test

Create `web/src/stores/favorites.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useFavorites } from './favorites';

describe('favorites store', () => {
  beforeEach(() => {
    localStorage.clear();
    useFavorites.setState({ username: null, slugs: new Set() });
  });

  it('loads empty for new user', () => {
    useFavorites.getState().load('alex');
    expect(useFavorites.getState().slugs.size).toBe(0);
  });

  it('toggle adds then removes', () => {
    useFavorites.getState().load('alex');
    useFavorites.getState().toggle('mos');
    expect(useFavorites.getState().isFavorite('mos')).toBe(true);
    useFavorites.getState().toggle('mos');
    expect(useFavorites.getState().isFavorite('mos')).toBe(false);
  });

  it('persists across reload', () => {
    useFavorites.getState().load('alex');
    useFavorites.getState().toggle('mos');
    useFavorites.getState().toggle('neaq');
    useFavorites.setState({ username: null, slugs: new Set() });
    useFavorites.getState().load('alex');
    expect(useFavorites.getState().slugs).toEqual(new Set(['mos', 'neaq']));
  });

  it('per-user separation', () => {
    useFavorites.getState().load('alex');
    useFavorites.getState().toggle('mos');
    useFavorites.getState().load('rbt');
    expect(useFavorites.getState().isFavorite('mos')).toBe(false);
  });
});
```

### Step 1.6: Run tests + commit

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm test
```

Expected: 15 + 8 + 4 = 27 passed.

```bash
cd "F:/pj/NorthShore Kids Events"
git add web/
git commit -m "feat(web): cardpack + favorites Zustand stores, per-user localStorage"
```

---

## Task 2 — Distance + tag-algorithm pure functions

**Why:** Tag-picking is the visual centerpiece. Must be pure-function, thoroughly tested, no DOM dependency.

**Files:**
- Create: `web/src/lib/distance.ts`
- Create: `web/src/lib/distance.test.ts`
- Create: `web/src/lib/tag-algorithm.ts`
- Create: `web/src/lib/tag-algorithm.test.ts`
- Create: `web/src/lib/price-fallback.ts`
- Create: `web/src/lib/price-fallback.test.ts`

### Step 2.1: Distance helper

Create `web/src/lib/distance.ts`:

```typescript
import type { Geo } from '../data/types';

const R_MILES = 3958.8;

export function haversineMiles(a: Geo, b: Geo): number {
  const phi1 = (a.lat * Math.PI) / 180;
  const phi2 = (b.lat * Math.PI) / 180;
  const dphi = ((b.lat - a.lat) * Math.PI) / 180;
  const dlam = ((b.lon - a.lon) * Math.PI) / 180;
  const x =
    Math.sin(dphi / 2) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlam / 2) ** 2;
  return 2 * R_MILES * Math.asin(Math.sqrt(x));
}

/**
 * Lookup a MA ZIP code → centroid using Nominatim, with localStorage cache.
 * Returns null if ZIP can't be geocoded or input is invalid.
 *
 * Note: browser CORS allows Nominatim queries. We rate-limit to 1 req/sec
 * client-side (Nominatim policy). Cached in localStorage so repeat lookups
 * are free.
 */
const ZIP_CACHE_KEY = 'museumpass-ma.zip-centroids';

interface ZipCache { [zip: string]: { lat: number; lon: number } | null }

function loadZipCache(): ZipCache {
  try {
    const raw = localStorage.getItem(ZIP_CACHE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveZipCache(cache: ZipCache): void {
  try {
    localStorage.setItem(ZIP_CACHE_KEY, JSON.stringify(cache));
  } catch { /* swallow */ }
}

let lastNominatimAt = 0;

async function rateLimit(): Promise<void> {
  const elapsed = Date.now() - lastNominatimAt;
  if (elapsed < 1100) {
    await new Promise((r) => setTimeout(r, 1100 - elapsed));
  }
  lastNominatimAt = Date.now();
}

export async function geocodeZip(zip: string): Promise<Geo | null> {
  if (!/^\d{5}$/.test(zip)) return null;
  const cache = loadZipCache();
  if (zip in cache) return cache[zip];

  await rateLimit();
  try {
    const url = `https://nominatim.openstreetmap.org/search?postalcode=${zip}&country=US&format=json&limit=1`;
    const resp = await fetch(url, {
      headers: { 'Accept': 'application/json' },
    });
    if (!resp.ok) return null;
    const arr = await resp.json();
    if (!Array.isArray(arr) || arr.length === 0) {
      cache[zip] = null;
      saveZipCache(cache);
      return null;
    }
    const entry: Geo = { lat: parseFloat(arr[0].lat), lon: parseFloat(arr[0].lon) };
    cache[zip] = entry;
    saveZipCache(cache);
    return entry;
  } catch {
    return null;  // network error — DON'T cache (per plan-1 geocode design)
  }
}
```

### Step 2.2: Distance test

Create `web/src/lib/distance.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { haversineMiles } from './distance';

describe('haversineMiles', () => {
  it('Boston to Wakefield ~10 mi', () => {
    const d = haversineMiles({ lat: 42.3601, lon: -71.0589 }, { lat: 42.5065, lon: -71.0759 });
    expect(d).toBeGreaterThan(9);
    expect(d).toBeLessThan(13);
  });

  it('Same point ≈ 0', () => {
    const d = haversineMiles({ lat: 42, lon: -71 }, { lat: 42, lon: -71 });
    expect(d).toBeLessThan(0.001);
  });
});
```

(geocodeZip uses real network; intentionally not unit-tested here.)

### Step 2.3: Price fallback

Create `web/src/lib/price-fallback.ts`:

```typescript
import type { OriginalPrice, Discount } from '../data/types';

/**
 * Compute the user's final price given original price and a discount.
 * Returns null if we can't compute (original missing).
 */
export function applyDiscount(original: OriginalPrice | null, discount: Discount): number | null {
  if (!original || original.adult == null) return null;
  const adult = original.adult;
  switch (discount.class) {
    case 'free': return 0;
    case 'half': return adult * 0.5;
    case 'dollar-off': {
      // Parse "$N off" from label
      const m = discount.label.match(/\$(\d+(?:\.\d+)?)/);
      return m ? Math.max(0, adult - parseFloat(m[1])) : null;
    }
    case 'percent-off': {
      const m = discount.label.match(/(\d+(?:\.\d+)?)%/);
      return m ? adult * (1 - parseFloat(m[1]) / 100) : null;
    }
    case 'price': {
      // Label is "$N per person" or similar — use it as the new price
      const m = discount.label.match(/\$(\d+(?:\.\d+)?)/);
      return m ? parseFloat(m[1]) : null;
    }
    default: return null;
  }
}

/**
 * Format an original price + discount into a display string for the card header:
 *   - "Original $30 → Free"
 *   - "Original $30 → $15 (50% off)"
 *   - "$5 off" (no original known)
 *   - "Free" (no original, but discount is genuinely free)
 *   - "" (no useful information)
 */
export function formatPriceLine(original: OriginalPrice | null, discount: Discount | null): string {
  if (!discount) {
    // No discount applicable — just show original
    if (original?.adult != null) return `Original $${original.adult}`;
    return '';
  }
  const final = applyDiscount(original, discount);
  if (original?.adult != null) {
    if (final === 0) return `Original $${original.adult} → Free`;
    if (final != null) {
      const finalStr = Number.isInteger(final) ? `$${final}` : `$${final.toFixed(2)}`;
      return `Original $${original.adult} → ${finalStr}`;
    }
    // can't compute final — at least show the discount label
    return `Original $${original.adult} (${discount.label})`;
  }
  // No original — just the discount label
  return discount.label;
}
```

### Step 2.4: Price fallback test

Create `web/src/lib/price-fallback.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { applyDiscount, formatPriceLine } from './price-fallback';
import type { OriginalPrice, Discount } from '../data/types';

const adult30: OriginalPrice = {
  adult: 30, child: null, senior: null, student: null, family: null,
  free_under_age: null, notes: null, source_url: null,
};

describe('applyDiscount', () => {
  it('free → 0', () => {
    expect(applyDiscount(adult30, { class: 'free', label: 'Free', raw: '' })).toBe(0);
  });
  it('half → 15', () => {
    expect(applyDiscount(adult30, { class: 'half', label: '50% off', raw: '' })).toBe(15);
  });
  it('$5 off → 25', () => {
    expect(applyDiscount(adult30, { class: 'dollar-off', label: '$5 off', raw: '' })).toBe(25);
  });
  it('20% off → 24', () => {
    expect(applyDiscount(adult30, { class: 'percent-off', label: '20% off', raw: '' })).toBe(24);
  });
  it('$5/person price → 5', () => {
    expect(applyDiscount(adult30, { class: 'price', label: '$5 per person', raw: '' })).toBe(5);
  });
  it('unknown discount → null', () => {
    expect(applyDiscount(adult30, { class: 'unknown', label: '', raw: '' })).toBeNull();
  });
  it('no original → null', () => {
    expect(applyDiscount(null, { class: 'free', label: 'Free', raw: '' })).toBeNull();
  });
});

describe('formatPriceLine', () => {
  it('original + free', () => {
    expect(formatPriceLine(adult30, { class: 'free', label: 'Free', raw: '' }))
      .toBe('Original $30 → Free');
  });
  it('original + half', () => {
    expect(formatPriceLine(adult30, { class: 'half', label: '50% off', raw: '' }))
      .toBe('Original $30 → $15');
  });
  it('no original + free', () => {
    expect(formatPriceLine(null, { class: 'free', label: 'Free', raw: '' }))
      .toBe('Free');
  });
  it('no original + $5 off', () => {
    expect(formatPriceLine(null, { class: 'dollar-off', label: '$5 off', raw: '' }))
      .toBe('$5 off');
  });
  it('only original', () => {
    expect(formatPriceLine(adult30, null)).toBe('Original $30');
  });
  it('nothing useful', () => {
    expect(formatPriceLine(null, null)).toBe('');
  });
});
```

### Step 2.5: Tag algorithm

Create `web/src/lib/tag-algorithm.ts`:

```typescript
import type { Pass, Library, Geo } from '../data/types';
import { haversineMiles } from './distance';

export type DiscountRank = number; // lower is better

const DISCOUNT_RANK: Record<string, DiscountRank> = {
  free: 0,
  half: 1,
  'percent-off': 2,
  'dollar-off': 3,
  price: 4,
  discount: 5,
  unknown: 99,
};

export interface PickedTag {
  pass: Pass;
  library: Library;
  distanceMi: number | null;  // null if user has no ZIP or no library geo
}

export interface PickTagsInput {
  passes: Pass[];                       // all passes for one attraction
  libraries: Library[];                 // all libraries (will be filtered)
  userCardLibIds: Set<string> | null;   // null = no filter (guest), set = filter to these lib IDs
  date: string;                         // YYYY-MM-DD
  userGeo: Geo | null;                  // ZIP centroid, null = no distance
  maxTags?: number;                     // default 4
}

/**
 * Pick ≤4 tags for one attraction × one day.
 *
 * Order (spec §5.2):
 *   1. Digital (zero distance) — at most 1, highest discount class
 *   2. Physical (sorted by discount desc, distance asc) — fills remaining slots
 *   3. Loan-card (same sort) — fills remaining slots
 *
 * Filters before sorting:
 *   - Pass's library must be in user_cards (if set)
 *   - calendar[date] must be "available"
 */
export function pickTags(input: PickTagsInput): PickedTag[] {
  const { passes, libraries, userCardLibIds, date, userGeo } = input;
  const maxTags = input.maxTags ?? 4;
  const libById = new Map(libraries.map(l => [l.id, l]));

  const candidates: PickedTag[] = [];
  for (const pass of passes) {
    if (userCardLibIds && !userCardLibIds.has(pass.library_id)) continue;
    if (pass.availability && pass.availability[date] !== 'available') continue;
    // If pass has a calendar but date isn't in it, skip (no data)
    if (pass.availability && !(date in pass.availability)) continue;
    const library = libById.get(pass.library_id);
    if (!library) continue;
    const dist = userGeo && library.geo
      ? haversineMiles(userGeo, library.geo)
      : null;
    candidates.push({ pass, library, distanceMi: dist });
  }

  // Split into 3 groups
  const digital = candidates.filter(c => c.pass.pass_type === 'digital');
  const physical = candidates.filter(c => c.pass.pass_type === 'physical-coupon');
  const loan = candidates.filter(c => c.pass.pass_type === 'loan-card');

  const tagsOut: PickedTag[] = [];

  // 1. Digital: only 1 tag, highest discount (lowest rank). Tie-break by library_id alpha.
  if (digital.length > 0) {
    digital.sort((a, b) => {
      const ra = DISCOUNT_RANK[a.pass.discount.class] ?? 99;
      const rb = DISCOUNT_RANK[b.pass.discount.class] ?? 99;
      if (ra !== rb) return ra - rb;
      return a.library.id.localeCompare(b.library.id);
    });
    tagsOut.push(digital[0]);
  }

  const distCmp = (a: PickedTag, b: PickedTag) => {
    if (a.distanceMi == null && b.distanceMi == null) return 0;
    if (a.distanceMi == null) return 1;
    if (b.distanceMi == null) return -1;
    return a.distanceMi - b.distanceMi;
  };

  const sortByDiscThenDist = (group: PickedTag[]) => {
    group.sort((a, b) => {
      const ra = DISCOUNT_RANK[a.pass.discount.class] ?? 99;
      const rb = DISCOUNT_RANK[b.pass.discount.class] ?? 99;
      if (ra !== rb) return ra - rb;
      return distCmp(a, b);
    });
  };

  sortByDiscThenDist(physical);
  for (const t of physical) {
    if (tagsOut.length >= maxTags) break;
    tagsOut.push(t);
  }

  sortByDiscThenDist(loan);
  for (const t of loan) {
    if (tagsOut.length >= maxTags) break;
    tagsOut.push(t);
  }

  return tagsOut;
}
```

### Step 2.6: Tag algorithm test

Create `web/src/lib/tag-algorithm.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { pickTags } from './tag-algorithm';
import type { Pass, Library, Geo } from '../data/types';

const lib = (id: string, geo: Geo | null = null): Library => ({
  id, name: id, town: id, network: 'X', platform: 'assabet',
  card_page: '', eligibility: 'open_ma_resident', supports_availability: true,
  address: null, geo,
});

const pass = (
  library_id: string,
  pass_type: Pass['pass_type'],
  discountClass: Pass['discount']['class'],
  label: string,
  availability: Pass['availability'] = null,
): Pass => ({
  library_id, attraction_slug: 'mos', pass_type, pass_type_raw: '',
  discount: { class: discountClass, label, raw: '' },
  source_url: '', availability,
});

describe('pickTags', () => {
  const wak = lib('wakefield', { lat: 42.5, lon: -71.07 });
  const rea = lib('reading', { lat: 42.52, lon: -71.10 });
  const bpl = lib('bpl', { lat: 42.36, lon: -71.07 });
  const wil = lib('wilmington', { lat: 42.55, lon: -71.17 });

  const userZip = { lat: 42.5, lon: -71.07 };  // pretend Wakefield ZIP

  it('digital free wins slot 1; other groups fill rest', () => {
    const passes = [
      pass('bpl', 'digital', 'free', 'Free'),
      pass('wakefield', 'physical-coupon', 'half', '50% off'),
      pass('reading', 'physical-coupon', 'dollar-off', '$5 off'),
      pass('wilmington', 'loan-card', 'free', 'Free'),
    ];
    const out = pickTags({
      passes, libraries: [wak, rea, bpl, wil], userCardLibIds: null,
      date: '2026-05-16', userGeo: userZip,
    });
    expect(out.length).toBe(4);
    expect(out[0].pass.library_id).toBe('bpl');
    expect(out[0].pass.pass_type).toBe('digital');
    expect(out[1].pass.pass_type).toBe('physical-coupon');
    expect(out[1].pass.discount.class).toBe('half');  // higher rank than dollar-off
    expect(out[2].pass.pass_type).toBe('physical-coupon');
    expect(out[3].pass.pass_type).toBe('loan-card');
  });

  it('only one digital tag even when multiple digital passes exist', () => {
    const passes = [
      pass('bpl', 'digital', 'free', 'Free'),
      pass('somerville', 'digital', 'half', '50% off'),
      pass('cambridge', 'digital', 'half', '50% off'),
    ];
    const out = pickTags({
      passes, libraries: [bpl, lib('somerville'), lib('cambridge')], userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.discount.class).toBe('free');  // free beats half
  });

  it('physical group: discount tier first, then distance', () => {
    const passes = [
      pass('reading', 'physical-coupon', 'half', '50% off'),
      pass('wakefield', 'physical-coupon', 'half', '50% off'),
    ];
    const out = pickTags({
      passes, libraries: [wak, rea], userCardLibIds: null,
      date: '2026-05-16', userGeo: userZip,
    });
    // Both half-price, but wakefield is closer
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('filters by userCardLibIds', () => {
    const passes = [
      pass('bpl', 'digital', 'free', 'Free'),
      pass('wakefield', 'physical-coupon', 'half', '50% off'),
    ];
    const out = pickTags({
      passes, libraries: [wak, bpl], userCardLibIds: new Set(['wakefield']),
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('filters out passes whose calendar marks date booked', () => {
    const passes = [
      pass('bpl', 'digital', 'free', 'Free', { '2026-05-16': 'booked' }),
      pass('wakefield', 'physical-coupon', 'half', '50% off', { '2026-05-16': 'available' }),
    ];
    const out = pickTags({
      passes, libraries: [wak, bpl], userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('caps at maxTags', () => {
    const passes = Array.from({ length: 10 }, (_, i) =>
      pass(`lib${i}`, 'physical-coupon', 'half', '50% off'));
    const libs = Array.from({ length: 10 }, (_, i) => lib(`lib${i}`));
    const out = pickTags({
      passes, libraries: libs, userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(4);
  });

  it('no candidates returns []', () => {
    const out = pickTags({
      passes: [], libraries: [], userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out).toEqual([]);
  });
});
```

### Step 2.7: Run tests + commit

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm test
```

Expected: 27 (Task 1) + 2 distance + 13 price-fallback + 7 tag-algorithm = 49 passed.

```bash
cd "F:/pj/NorthShore Kids Events"
git add web/
git commit -m "feat(web): distance + price-fallback + tag-algorithm pure functions"
```

---

## Task 3 — Card + Tag UI components

**Why:** Visual building blocks for list page. Each is small and testable in isolation.

**Files:**
- Create: `web/src/components/PassTag.tsx`
- Create: `web/src/components/FavoriteButton.tsx`
- Create: `web/src/components/AttractionCard.tsx`
- Create: `web/src/components/Banner.tsx`

### Step 3.1: PassTag

Create `web/src/components/PassTag.tsx`:

```typescript
import type { PassTypeKind } from '../data/types';

interface Props {
  passType: PassTypeKind;
  discountLabel: string;      // e.g., "Free", "50% off", "$5 off"
  libraryTown?: string;       // shown for non-digital
  distanceMi?: number | null; // shown for non-digital if not null
}

const STYLE_BY_TYPE: Record<PassTypeKind, { bg: string; fg: string; icon: string }> = {
  'digital':         { bg: 'var(--g-pale)', fg: 'var(--g)',  icon: '⚡' },
  'physical-coupon': { bg: 'var(--au-pale)', fg: 'var(--au)', icon: '🎫' },
  'loan-card':       { bg: 'var(--or-pale)', fg: 'var(--or)', icon: '🔁' },
  'unknown':         { bg: 'var(--paper)',  fg: 'var(--ink-3)', icon: '?' },
};

export function PassTag({ passType, discountLabel, libraryTown, distanceMi }: Props) {
  const s = STYLE_BY_TYPE[passType];
  const showLocation = passType !== 'digital' && libraryTown;
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      padding: '4px 9px',
      borderRadius: '3px',
      background: s.bg,
      color: s.fg,
      fontSize: '12px',
      whiteSpace: 'nowrap',
    }}>
      <span aria-hidden>{s.icon}</span>
      <span style={{ fontWeight: 500 }}>{discountLabel}</span>
      {showLocation && (
        <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}>
          · {libraryTown}
          {distanceMi != null && ` ${Math.round(distanceMi)} mi`}
        </span>
      )}
    </span>
  );
}
```

### Step 3.2: FavoriteButton

Create `web/src/components/FavoriteButton.tsx`:

```typescript
import { useFavorites } from '../stores/favorites';

interface Props {
  slug: string;
  size?: number;
}

export function FavoriteButton({ slug, size = 18 }: Props) {
  const isFav = useFavorites(s => s.isFavorite(slug));
  const toggle = useFavorites(s => s.toggle);

  return (
    <button
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggle(slug); }}
      aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
      style={{
        background: 'transparent',
        border: 'none',
        cursor: 'pointer',
        fontSize: `${size}px`,
        lineHeight: 1,
        color: isFav ? 'var(--rd)' : 'var(--ink-3)',
        padding: '2px',
      }}
    >
      {isFav ? '❤' : '♡'}
    </button>
  );
}
```

### Step 3.3: AttractionCard

Create `web/src/components/AttractionCard.tsx`:

```typescript
import { Link } from 'react-router';
import type { Attraction } from '../data/types';
import type { PickedTag } from '../lib/tag-algorithm';
import { PassTag } from './PassTag';
import { FavoriteButton } from './FavoriteButton';
import { formatPriceLine } from '../lib/price-fallback';

interface Props {
  attraction: Attraction;
  pickedTags: PickedTag[];
  isGuestOrEmpty?: boolean;
  sourceCountForGuest?: number; // shown only when isGuestOrEmpty
}

function heroSrc(a: Attraction): string {
  if (a.hero_image?.local_path) {
    // local_path is like 'static/images/mos.jpg' or 'data/static/images/mos.jpg'
    // We mirrored these into web/public/images/, so use just '/images/<slug>.<ext>'.
    const filename = a.hero_image.local_path.split(/[\\/]/).pop() ?? '';
    if (filename) return `/images/${filename}`;
  }
  const cat = a.categories?.[0]?.toLowerCase() ?? 'default';
  const known = ['family','children','history','nature','art','science','ocean','recreation'];
  const slug = known.includes(cat) ? cat : 'default';
  return `/placeholders/${slug}.svg`;
}

export function AttractionCard({
  attraction, pickedTags, isGuestOrEmpty = false, sourceCountForGuest = 0,
}: Props) {
  const primaryDiscount = pickedTags[0]?.pass.discount ?? null;
  const priceLine = formatPriceLine(attraction.original_price, primaryDiscount);
  const introSnippet = attraction.categories.slice(0, 3).join(' · ');

  return (
    <Link to={`/attractions/${attraction.slug}`} style={{
      display: 'block',
      borderBottom: '1px solid var(--rule)',
      padding: '12px 8px',
      color: 'inherit',
      textDecoration: 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <FavoriteButton slug={attraction.slug} />
        <img
          src={heroSrc(attraction)}
          alt=""
          loading="lazy"
          style={{
            width: 80, height: 80, borderRadius: 4, objectFit: 'cover',
            background: 'var(--paper)', flexShrink: 0,
          }}
        />
        <div style={{ flexGrow: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline' }}>
            <div className="font-serif" style={{ fontSize: 16, color: 'var(--ink-2)', fontWeight: 700 }}>
              {attraction.museum_name}
            </div>
            {priceLine && (
              <div style={{ fontSize: 12, color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>
                {priceLine}
              </div>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>
            {introSnippet || ' '}
          </div>
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {isGuestOrEmpty ? (
              <span style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
                Sign in to view {sourceCountForGuest} discount option{sourceCountForGuest === 1 ? '' : 's'}
              </span>
            ) : pickedTags.length === 0 ? (
              <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>No passes available</span>
            ) : pickedTags.map((t, i) => (
              <PassTag
                key={`${t.pass.library_id}-${i}`}
                passType={t.pass.pass_type}
                discountLabel={t.pass.discount.label || t.pass.discount.class}
                libraryTown={t.library.town}
                distanceMi={t.distanceMi}
              />
            ))}
          </div>
        </div>
      </div>
    </Link>
  );
}
```

### Step 3.4: Banner

Create `web/src/components/Banner.tsx`:

```typescript
import { Link } from 'react-router';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';

interface Props {
  onSignInClick: () => void;
}

export function Banner({ onSignInClick }: Props) {
  const user = useAuth(s => s.currentUser);
  const cards = useCardpack(s => s.pack.cards);
  const hasCards = Object.keys(cards).length > 0;

  if (user && hasCards) return null;

  const text = user
    ? 'Set up your library passes to see your discounts →'
    : 'Add your library pass to unlock discounts →';
  const action = user
    ? <Link to="/settings/passes" style={{ color: 'var(--g)', fontWeight: 500 }}>Open My passes</Link>
    : <button onClick={onSignInClick} style={{
        background: 'transparent', border: 'none', color: 'var(--g)',
        fontWeight: 500, cursor: 'pointer', font: 'inherit',
      }}>Sign in</button>;

  return (
    <div style={{
      borderBottom: '1px solid var(--g-light)',
      background: 'var(--g-pale)',
      padding: '10px 24px',
      fontSize: 13,
      color: 'var(--ink-2)',
      display: 'flex',
      gap: 12,
      alignItems: 'center',
    }}>
      <span style={{ color: 'var(--g)' }}>ⓘ</span>
      <span>{text}</span>
      <span style={{ marginLeft: 'auto' }}>{action}</span>
    </div>
  );
}
```

### Step 3.5: Build check

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm run build
```

Should compile cleanly.

### Step 3.6: Run tests

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm test
```

Should still pass (no new tests, components are visual).

### Step 3.7: Commit

```bash
cd "F:/pj/NorthShore Kids Events"
git add web/
git commit -m "feat(web): PassTag, FavoriteButton, AttractionCard, Banner components"
```

---

## Task 4 — Real List page UI

**Files:**
- Update: `web/src/pages/AttractionsList.tsx` (full rewrite)
- Create: `web/src/components/SortDropdown.tsx`
- Create: `web/src/components/DatePicker.tsx`
- Update: `web/src/App.tsx` (banner needs sign-in-modal accessor)

### Step 4.1: SortDropdown

Create `web/src/components/SortDropdown.tsx`:

```typescript
import { Select, SelectItem } from '@heroui/react';

export type SortOption = 'favorites' | 'alpha' | 'distance' | 'discount';

interface Props {
  value: SortOption;
  onChange: (v: SortOption) => void;
  distanceEnabled: boolean;
}

export function SortDropdown({ value, onChange, distanceEnabled }: Props) {
  return (
    <Select
      label="Sort by"
      labelPlacement="outside-left"
      size="sm"
      selectedKeys={new Set([value])}
      onSelectionChange={(keys) => {
        const first = Array.from(keys)[0] as SortOption | undefined;
        if (first) onChange(first);
      }}
      className="max-w-xs"
    >
      <SelectItem key="favorites">Favorites first</SelectItem>
      <SelectItem key="alpha">A–Z</SelectItem>
      <SelectItem key="distance" textValue="Distance">
        {distanceEnabled ? 'Distance' : 'Distance (set ZIP)'}
      </SelectItem>
      <SelectItem key="discount">Discount</SelectItem>
    </Select>
  );
}
```

### Step 4.2: DatePicker

Create `web/src/components/DatePicker.tsx`:

```typescript
import { Input } from '@heroui/react';

interface Props {
  value: string;          // YYYY-MM-DD
  onChange: (v: string) => void;
}

export function DatePicker({ value, onChange }: Props) {
  return (
    <Input
      type="date"
      label="Date"
      labelPlacement="outside-left"
      size="sm"
      value={value}
      onValueChange={onChange}
      className="max-w-xs"
    />
  );
}
```

### Step 4.3: Rewrite AttractionsList

Replace `web/src/pages/AttractionsList.tsx`:

```typescript
import { useEffect, useMemo, useState } from 'react';
import { getAttractions, getPasses, getLibraries } from '../data/load';
import { AttractionCard } from '../components/AttractionCard';
import { Banner } from '../components/Banner';
import { DatePicker } from '../components/DatePicker';
import { SortDropdown, type SortOption } from '../components/SortDropdown';
import { pickTags, type PickedTag } from '../lib/tag-algorithm';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip } from '../lib/distance';
import { SignInModal } from '../components/SignInModal';
import type { Geo } from '../data/types';

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function AttractionsList() {
  const user = useAuth(s => s.currentUser);
  const cardpack = useCardpack(s => s.pack);
  const favorites = useFavorites(s => s.slugs);
  const loadCardpack = useCardpack(s => s.load);
  const loadFavorites = useFavorites(s => s.load);

  const [signInOpen, setSignInOpen] = useState(false);
  const [date, setDate] = useState(() => todayIso());
  const [sort, setSort] = useState<SortOption>('favorites');
  const [userGeo, setUserGeo] = useState<Geo | null>(null);

  // Sync stores to current user
  useEffect(() => {
    loadCardpack(user?.username ?? null);
    loadFavorites(user?.username ?? null);
  }, [user, loadCardpack, loadFavorites]);

  // Geocode ZIP if present
  useEffect(() => {
    const zip = cardpack.zip;
    if (!zip || zip.length !== 5) { setUserGeo(null); return; }
    let cancelled = false;
    geocodeZip(zip).then(g => { if (!cancelled) setUserGeo(g); });
    return () => { cancelled = true; };
  }, [cardpack.zip]);

  const attractions = useMemo(() => getAttractions(), []);
  const allPasses = useMemo(() => getPasses(), []);
  const libraries = useMemo(() => getLibraries(), []);

  const userCardLibIds = useMemo(() => {
    if (!user) return null;  // guest
    const ids = new Set(Object.keys(cardpack.cards));
    if (ids.size === 0) return null;  // admin/empty: behave like guest for tag picking
    return ids;
  }, [user, cardpack.cards]);

  const isGuestOrEmpty = !user || Object.keys(cardpack.cards).length === 0;

  const passesBySlug = useMemo(() => {
    const m = new Map<string, typeof allPasses>();
    for (const p of allPasses) {
      const arr = m.get(p.attraction_slug) ?? [];
      arr.push(p);
      m.set(p.attraction_slug, arr);
    }
    return m;
  }, [allPasses]);

  // Compute picked tags per attraction
  const rows = useMemo(() => {
    return attractions.map(a => {
      const passes = passesBySlug.get(a.slug) ?? [];
      const tags: PickedTag[] = isGuestOrEmpty ? [] : pickTags({
        passes, libraries, userCardLibIds, date, userGeo,
      });
      return { attraction: a, tags, sourceCount: a.sources.length };
    });
  }, [attractions, passesBySlug, libraries, userCardLibIds, date, userGeo, isGuestOrEmpty]);

  // Sort
  const sortedRows = useMemo(() => {
    const copy = [...rows];
    const isFav = (slug: string) => favorites.has(slug);
    const compareName = (a: typeof copy[0], b: typeof copy[0]) =>
      a.attraction.museum_name.localeCompare(b.attraction.museum_name);

    switch (sort) {
      case 'favorites':
        copy.sort((a, b) => {
          const fa = isFav(a.attraction.slug);
          const fb = isFav(b.attraction.slug);
          if (fa !== fb) return fa ? -1 : 1;
          return compareName(a, b);
        });
        break;
      case 'alpha':
        copy.sort(compareName);
        break;
      case 'distance': {
        // sort by min distance among picked tags (or Infinity)
        const minDist = (r: typeof copy[0]) => {
          let best = Infinity;
          for (const t of r.tags) {
            if (t.distanceMi != null && t.distanceMi < best) best = t.distanceMi;
          }
          return best;
        };
        copy.sort((a, b) => minDist(a) - minDist(b));
        break;
      }
      case 'discount': {
        const rank = (r: typeof copy[0]) => {
          if (r.tags.length === 0) return 99;
          const cls = r.tags[0].pass.discount.class;
          const rankMap: Record<string, number> = {
            free: 0, half: 1, 'percent-off': 2, 'dollar-off': 3, price: 4, discount: 5, unknown: 99,
          };
          return rankMap[cls] ?? 99;
        };
        copy.sort((a, b) => rank(a) - rank(b));
        break;
      }
    }
    // "No passes available" sinks to bottom unless Favorited
    copy.sort((a, b) => {
      const ea = a.tags.length === 0 && !isFav(a.attraction.slug);
      const eb = b.tags.length === 0 && !isFav(b.attraction.slug);
      if (ea !== eb) return ea ? 1 : -1;
      return 0;
    });
    return copy;
  }, [rows, favorites, sort]);

  return (
    <>
      <Banner onSignInClick={() => setSignInOpen(true)} />
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
      <div className="max-w-6xl mx-auto px-4 py-6">
        <h1 className="font-serif" style={{ fontSize: 24, marginBottom: 12, color: 'var(--ink-2)' }}>
          Attractions
        </h1>
        <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
          <DatePicker value={date} onChange={setDate} />
          <SortDropdown value={sort} onChange={setSort} distanceEnabled={!!userGeo} />
        </div>
        <p style={{ color: 'var(--ink-3)', fontSize: 11, marginBottom: 12 }}>
          Showing {sortedRows.length} attractions for {date}
        </p>
        <div>
          {sortedRows.map(r => (
            <AttractionCard
              key={r.attraction.slug}
              attraction={r.attraction}
              pickedTags={r.tags}
              isGuestOrEmpty={isGuestOrEmpty}
              sourceCountForGuest={r.sourceCount}
            />
          ))}
        </div>
      </div>
    </>
  );
}
```

### Step 4.4: Move the `<main>` wrapper out

Since AttractionsList now renders its own banner + padded container, the `<main className="max-w-6xl mx-auto px-4 py-6">` in `App.tsx` would double up. Update `App.tsx`:

```typescript
import { BrowserRouter, Routes, Route } from 'react-router';
import { useEffect } from 'react';
import { TopBar } from './components/TopBar';
import { AttractionsList } from './pages/AttractionsList';
import { AttractionDetail } from './pages/AttractionDetail';
import { MyPasses } from './pages/MyPasses';
import { NotFound } from './pages/NotFound';
import { useAuth } from './auth/store';

function App() {
  const loadFromStorage = useAuth(s => s.loadFromStorage);
  useEffect(() => { loadFromStorage(); }, [loadFromStorage]);

  return (
    <BrowserRouter>
      <TopBar />
      <Routes>
        <Route path="/" element={<AttractionsList />} />
        <Route path="/attractions/:slug" element={<AttractionDetail />} />
        <Route path="/settings/passes" element={<MyPasses />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

(Each page now owns its own padding/banner.)

### Step 4.5: Build + test

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm run build
pnpm test
```

Both should pass.

### Step 4.6: Commit

```bash
cd "F:/pj/NorthShore Kids Events"
git add web/
git commit -m "feat(web): real list page with tag algorithm, sort, date picker, banner"
```

---

## Task 5 — Real Attraction Detail page

**Files:**
- Update: `web/src/pages/AttractionDetail.tsx` (rewrite)

### Step 5.1: Detail page

Replace `web/src/pages/AttractionDetail.tsx`:

```typescript
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { Button } from '@heroui/react';
import {
  getAttractionBySlug, getPassesForAttraction, getLibraries,
} from '../data/load';
import { PassTag } from '../components/PassTag';
import { FavoriteButton } from '../components/FavoriteButton';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip, haversineMiles } from '../lib/distance';
import { formatPriceLine } from '../lib/price-fallback';
import { BookingConfirmModal } from '../components/BookingConfirmModal';
import type { Geo, Pass, Library } from '../data/types';

function days(start: string, n: number): string[] {
  const out: string[] = [];
  const d = new Date(start);
  for (let i = 0; i < n; i++) {
    const dd = new Date(d);
    dd.setDate(d.getDate() + i);
    out.push(`${dd.getFullYear()}-${String(dd.getMonth()+1).padStart(2,'0')}-${String(dd.getDate()).padStart(2,'0')}`);
  }
  return out;
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

interface Row {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  available: boolean;
}

export function AttractionDetail() {
  const { slug } = useParams<{ slug: string }>();
  const user = useAuth(s => s.currentUser);
  const cardpack = useCardpack(s => s.pack);
  const loadCardpack = useCardpack(s => s.load);
  const loadFavorites = useFavorites(s => s.load);
  const [userGeo, setUserGeo] = useState<Geo | null>(null);
  const [startDate, setStartDate] = useState(() => todayIso());
  const [windowSize, setWindowSize] = useState(7);
  const [bookingPass, setBookingPass] = useState<Pass | null>(null);

  useEffect(() => {
    loadCardpack(user?.username ?? null);
    loadFavorites(user?.username ?? null);
  }, [user, loadCardpack, loadFavorites]);

  useEffect(() => {
    if (!cardpack.zip || cardpack.zip.length !== 5) { setUserGeo(null); return; }
    let cancelled = false;
    geocodeZip(cardpack.zip).then(g => { if (!cancelled) setUserGeo(g); });
    return () => { cancelled = true; };
  }, [cardpack.zip]);

  const attraction = useMemo(() => slug ? getAttractionBySlug(slug) : undefined, [slug]);
  const allPasses = useMemo(() => slug ? getPassesForAttraction(slug) : [], [slug]);
  const libraries = useMemo(() => getLibraries(), []);
  const libById = useMemo(() => new Map(libraries.map(l => [l.id, l])), [libraries]);

  if (!slug) return <div className="max-w-6xl mx-auto px-4 py-6">Missing slug.</div>;
  if (!attraction) return <div className="max-w-6xl mx-auto px-4 py-6">Attraction "{slug}" not found.</div>;

  const userCardLibIds = (user && Object.keys(cardpack.cards).length > 0)
    ? new Set(Object.keys(cardpack.cards))
    : null;

  const dateList = days(startDate, windowSize);

  const rowsForDate = (date: string): Row[] => {
    const rows: Row[] = [];
    for (const pass of allPasses) {
      const library = libById.get(pass.library_id);
      if (!library) continue;
      const userCanUse = !userCardLibIds || userCardLibIds.has(pass.library_id);
      if (userCardLibIds && !userCanUse) continue;
      const availStatus = pass.availability?.[date];
      const available = availStatus === 'available' || availStatus === undefined;
      const dist = userGeo && library.geo ? haversineMiles(userGeo, library.geo) : null;
      rows.push({ pass, library, distanceMi: dist, available });
    }
    return rows;
  };

  const rank: Record<string, number> = {
    free: 0, half: 1, 'percent-off': 2, 'dollar-off': 3, price: 4, discount: 5, unknown: 99,
  };
  const sortRows = (rows: Row[]) => {
    return [...rows].sort((a, b) => {
      const ra = rank[a.pass.discount.class] ?? 99;
      const rb = rank[b.pass.discount.class] ?? 99;
      if (ra !== rb) return ra - rb;
      if (a.distanceMi == null && b.distanceMi != null) return 1;
      if (a.distanceMi != null && b.distanceMi == null) return -1;
      if (a.distanceMi != null && b.distanceMi != null) return a.distanceMi - b.distanceMi;
      return a.library.id.localeCompare(b.library.id);
    });
  };

  const heroSrc = (() => {
    if (attraction.hero_image?.local_path) {
      const filename = attraction.hero_image.local_path.split(/[\\/]/).pop() ?? '';
      if (filename) return `/images/${filename}`;
    }
    const cat = attraction.categories?.[0]?.toLowerCase() ?? 'default';
    const known = ['family','children','history','nature','art','science','ocean','recreation'];
    return `/placeholders/${known.includes(cat) ? cat : 'default'}.svg`;
  })();

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Link to="/" style={{ color: 'var(--ink-3)', fontSize: 13 }}>← Back to attractions</Link>
        <FavoriteButton slug={attraction.slug} size={22} />
      </div>
      <div style={{ display: 'flex', gap: 24, marginBottom: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <img src={heroSrc} alt="" style={{
          width: 280, height: 210, objectFit: 'cover', borderRadius: 4, background: 'var(--paper)',
        }} />
        <div style={{ flexGrow: 1, minWidth: 280 }}>
          <h1 className="font-serif" style={{ fontSize: 28, color: 'var(--ink-2)', marginBottom: 4 }}>
            {attraction.museum_name}
          </h1>
          <p style={{ color: 'var(--ink-3)', fontSize: 13 }}>
            {attraction.address || 'Address unavailable'}
          </p>
          <p style={{ color: 'var(--ink-3)', fontSize: 12, marginTop: 4 }}>
            Categories: {attraction.categories.join(' · ')}
          </p>
          <p style={{ marginTop: 12, fontSize: 13 }}>
            {formatPriceLine(attraction.original_price, null) || 'Price unavailable'}
          </p>
          {attraction.website && (
            <p style={{ marginTop: 12, fontSize: 13 }}>
              <a href={attraction.website} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--g)' }}>
                Visit official site →
              </a>
            </p>
          )}
        </div>
      </div>

      <h2 className="font-serif" style={{ fontSize: 18, marginBottom: 8, color: 'var(--ink-2)' }}>
        Discount options
      </h2>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontSize: 12, color: 'var(--ink-3)' }}>From:</label>
        <input
          type="date"
          value={startDate}
          onChange={e => setStartDate(e.target.value)}
          style={{ padding: '4px 8px', border: '1px solid var(--rule)', borderRadius: 4, fontSize: 13 }}
        />
        <label style={{ fontSize: 12, color: 'var(--ink-3)' }}>Window:</label>
        <select
          value={windowSize}
          onChange={e => setWindowSize(parseInt(e.target.value))}
          style={{ padding: '4px 8px', border: '1px solid var(--rule)', borderRadius: 4, fontSize: 13 }}
        >
          <option value={3}>3 days</option>
          <option value={7}>7 days</option>
          <option value={14}>14 days</option>
          <option value={30}>30 days</option>
        </select>
      </div>

      {dateList.map(date => {
        const rows = sortRows(rowsForDate(date).filter(r => r.available));
        return (
          <div key={date} style={{ marginBottom: 16, borderBottom: '1px solid var(--rule)', paddingBottom: 12 }}>
            <div style={{ fontSize: 13, color: 'var(--ink-3)', marginBottom: 6 }}>
              {date} · {rows.length} option{rows.length === 1 ? '' : 's'}
            </div>
            {rows.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
                No passes available on this day.
              </div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {rows.slice(0, 10).map((r, i) => (
                  <button
                    key={`${r.pass.library_id}-${i}`}
                    onClick={() => setBookingPass(r.pass)}
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0 }}
                  >
                    <PassTag
                      passType={r.pass.pass_type}
                      discountLabel={r.pass.discount.label || r.pass.discount.class}
                      libraryTown={r.library.town}
                      distanceMi={r.distanceMi}
                    />
                  </button>
                ))}
                {rows.length > 10 && (
                  <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>+{rows.length - 10} more</span>
                )}
              </div>
            )}
          </div>
        );
      })}

      <h2 className="font-serif" style={{ fontSize: 18, marginTop: 24, marginBottom: 8 }}>
        Participating libraries ({attraction.sources.length})
      </h2>
      <ul style={{ fontSize: 13, color: 'var(--ink-3)' }}>
        {attraction.sources.slice(0, 30).map(libId => {
          const l = libById.get(libId);
          return <li key={libId} style={{ padding: '2px 0' }}>
            {l ? `${l.name} (${l.town})` : libId}
          </li>;
        })}
      </ul>

      <BookingConfirmModal
        pass={bookingPass}
        cardpack={cardpack}
        onClose={() => setBookingPass(null)}
      />
    </div>
  );
}
```

### Step 5.2: Booking confirmation modal

Create `web/src/components/BookingConfirmModal.tsx`:

```typescript
import {
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button,
} from '@heroui/react';
import type { Pass } from '../data/types';
import type { CardPack } from '../stores/cardpack';

interface Props {
  pass: Pass | null;
  cardpack: CardPack;
  onClose: () => void;
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function BookingConfirmModal({ pass, cardpack, onClose }: Props) {
  if (!pass) return null;
  const card = cardpack.cards[pass.library_id];
  const hasCard = !!card?.barcode;

  const handleOpen = async () => {
    if (hasCard) {
      await copyToClipboard(card.barcode);
    }
    if (pass.source_url) {
      window.open(pass.source_url, '_blank', 'noopener,noreferrer');
    }
    onClose();
  };

  return (
    <Modal isOpen={!!pass} onClose={onClose}>
      <ModalContent>
        <ModalHeader>Open booking page</ModalHeader>
        <ModalBody>
          {hasCard ? (
            <>
              <p>Your barcode for <b>{pass.library_id}</b> will be copied to clipboard.</p>
              <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                On the next page, paste it into the library&apos;s reservation form.
              </p>
            </>
          ) : (
            <>
              <p style={{ color: 'var(--rd)' }}>
                You don&apos;t have a card for this library yet.
              </p>
              <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                Add one in <a href="/settings/passes" style={{ color: 'var(--g)' }}>My passes</a> first.
              </p>
            </>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={onClose}>Cancel</Button>
          {hasCard && (
            <Button color="primary" onClick={handleOpen}>
              Open booking page →
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
```

### Step 5.3: Build + commit

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm run build
pnpm test
cd "F:/pj/NorthShore Kids Events"
git add web/
git commit -m "feat(web): real attraction detail page with date range + booking modal"
```

---

## Task 6 — Real My Passes settings page

**Files:**
- Update: `web/src/pages/MyPasses.tsx` (rewrite)

### Step 6.1: Settings page

Replace `web/src/pages/MyPasses.tsx`:

```typescript
import { useEffect, useMemo, useState } from 'react';
import { Input, Button, Checkbox } from '@heroui/react';
import { useAuth } from '../auth/store';
import { useCardpack, type LibraryCard } from '../stores/cardpack';
import { getLibraries } from '../data/load';

export function MyPasses() {
  const user = useAuth(s => s.currentUser);
  const pack = useCardpack(s => s.pack);
  const load = useCardpack(s => s.load);
  const saveZip = useCardpack(s => s.saveZip);
  const saveCard = useCardpack(s => s.saveCard);
  const removeCard = useCardpack(s => s.removeCard);

  useEffect(() => { load(user?.username ?? null); }, [user, load]);

  const libraries = useMemo(() => {
    const list = getLibraries();
    return [...list].sort((a, b) => a.town.localeCompare(b.town));
  }, []);

  const [zipDraft, setZipDraft] = useState('');
  useEffect(() => { setZipDraft(pack.zip); }, [pack.zip]);

  if (!user) {
    return <div className="max-w-3xl mx-auto px-4 py-6">
      <p>Sign in to manage your passes.</p>
    </div>;
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <h1 className="font-serif" style={{ fontSize: 24, marginBottom: 4, color: 'var(--ink-2)' }}>
        My passes
      </h1>
      <p style={{ color: 'var(--ink-3)', fontSize: 12, marginBottom: 16 }}>
        Stored only in your browser, namespaced by your username.
      </p>

      <div style={{ borderBottom: '1px solid var(--rule)', paddingBottom: 16, marginBottom: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 500, marginBottom: 8 }}>ZIP code</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'end' }}>
          <Input
            size="sm"
            value={zipDraft}
            onValueChange={setZipDraft}
            placeholder="01880"
            maxLength={5}
            className="max-w-[160px]"
          />
          <Button size="sm" color="primary" onClick={() => saveZip(zipDraft)}>
            Save
          </Button>
        </div>
        <p style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 4 }}>
          Used to calculate distance to pickup libraries.
        </p>
      </div>

      <h2 style={{ fontSize: 14, fontWeight: 500, marginBottom: 8 }}>
        Your library cards ({Object.keys(pack.cards).length})
      </h2>

      <div>
        {libraries.map(l => {
          const card = pack.cards[l.id];
          const has = !!card;
          return (
            <LibraryRow
              key={l.id}
              libraryId={l.id}
              libraryName={l.name}
              town={l.town}
              card={card}
              hasCard={has}
              onAdd={() => saveCard(l.id, { barcode: '', lastName: '', pin: '' })}
              onSave={(updates) => saveCard(l.id, updates)}
              onRemove={() => removeCard(l.id)}
            />
          );
        })}
      </div>
    </div>
  );
}

interface RowProps {
  libraryId: string;
  libraryName: string;
  town: string;
  card?: LibraryCard;
  hasCard: boolean;
  onAdd: () => void;
  onSave: (updates: LibraryCard) => void;
  onRemove: () => void;
}

function LibraryRow({ libraryId, libraryName, town, card, hasCard, onAdd, onSave, onRemove }: RowProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<LibraryCard>(card ?? { barcode: '', lastName: '', pin: '' });

  useEffect(() => {
    if (card) setDraft(card);
  }, [card]);

  return (
    <div style={{ borderBottom: '1px solid var(--rule)', padding: '10px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Checkbox
          isSelected={hasCard}
          onValueChange={(checked) => {
            if (checked) { onAdd(); setOpen(true); }
            else onRemove();
          }}
        />
        <button
          onClick={() => setOpen(o => !o)}
          style={{
            flex: 1, textAlign: 'left', background: 'transparent', border: 'none',
            cursor: 'pointer', font: 'inherit', padding: 0,
          }}
        >
          <span style={{ fontWeight: 500, color: 'var(--ink-2)' }}>{libraryName}</span>
          <span style={{ color: 'var(--ink-3)', marginLeft: 8 }}>({town})</span>
        </button>
      </div>
      {hasCard && open && (
        <div style={{ marginLeft: 32, marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Input
            label="Barcode"
            size="sm"
            value={draft.barcode}
            onValueChange={(v) => setDraft({ ...draft, barcode: v })}
            className="max-w-[220px]"
          />
          <Input
            label="Last name"
            size="sm"
            value={draft.lastName}
            onValueChange={(v) => setDraft({ ...draft, lastName: v })}
            className="max-w-[160px]"
          />
          <Input
            label="PIN (optional)"
            size="sm"
            value={draft.pin}
            onValueChange={(v) => setDraft({ ...draft, pin: v })}
            className="max-w-[100px]"
          />
          <Button size="sm" color="primary" onClick={() => { onSave(draft); setOpen(false); }}>
            Save
          </Button>
        </div>
      )}
    </div>
  );
}
```

### Step 6.2: Build + commit

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm run build
pnpm test
cd "F:/pj/NorthShore Kids Events"
git add web/
git commit -m "feat(web): real My passes settings page with per-library card form"
```

---

## Task 7 — Final verification & docs

### Step 7.1: Run all tests

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm test
```

Expected: ≥49 frontend tests (15 from plan-3 + 34 from plan-4).

```bash
cd "F:/pj/NorthShore Kids Events"
python -m pytest tests/ 2>&1 | tail -3
```

Expected: 114 backend tests still pass.

### Step 7.2: Production build

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm run build
```

Should compile in <30s without TypeScript errors.

### Step 7.3: Dev server (manual)

The user (controller) will start `pnpm run dev` and manually verify:

- ☐ Home page shows attraction list with cards
- ☐ Default sort = Favorites first (alphabetical underneath)
- ☐ Date defaults to today
- ☐ Without sign-in, cards show "Sign in to view N options" instead of tags
- ☐ Banner appears (green) at top with "Add your library pass" CTA
- ☐ Click an attraction → detail page renders with hero + price + date range + 3-group tags
- ☐ Sign in as alex → banner disappears, cards now show real tags (digital ⚡ first, then physical 🎫, then loan 🔁)
- ☐ Hover/click a tag in detail page → BookingConfirmModal opens, "barcode copied" message
- ☐ Click ❤ on a card → moves to top of list
- ☐ Visit /settings/passes → see ZIP input + library list with checkboxes
- ☐ Sign in as admin → banner reads "Set up your library passes" + has direct link
- ☐ Sign out → state resets, banner reappears

The subagent for Task 7 does NOT start the dev server. It just runs build + tests and reports.

### Step 7.4: Update CLAUDE.md

Add a single line under "How to Run" if not already there:

```bash
cd web && pnpm install && pnpm run dev   # frontend dev server
```

And under Repository Layout, ensure `web/src/{stores,lib,components,pages,...}` is reflected.

### Step 7.5: Commit

```bash
cd "F:/pj/NorthShore Kids Events"
git add CLAUDE.md
git commit -m "docs: reflect plan-4 web/src structure"
```

---

## Verification Summary

After all 7 tasks:

| Artifact | Status |
|---|---|
| Cardpack + Favorites stores | ✅ Zustand + localStorage per-user |
| Tag algorithm | ✅ pure function, 7+ tests |
| AttractionCard / PassTag / Banner / FavoriteButton | ✅ HeroUI + token-styled |
| List page real UI | ✅ date picker + sort + cards |
| Detail page real UI | ✅ hero + date range + 3-group tags + BookingConfirmModal |
| My passes settings | ✅ ZIP + per-library card form |
| Frontend tests | ≥49 passed |
| Backend tests | 114 passed |
| Production build | clean |

After this, the v0.1 frontend is functionally complete and ready for visual review.
