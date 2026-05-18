# AttractionDetail · Research-First Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `web/src/pages/AttractionDetail.tsx` from its current "date-picker first" layout to a **research-first** layout where the hero image, today's key facts, and description lead, and the coupon selection becomes a focused product-value section using a 7-day pill row (with full-calendar expander). Hide no-card pass rows entirely, kill the "Participating libraries" list, and introduce a shared `PassRow` component that uses delivery chips (`✉ Email` / `📍 Pickup Nmi` / `🔄 Borrow Nmi`).

**Architecture:** Bottom-up extraction. Build small focused components first (`PassDeliveryChip`, `AudienceValueLine`, `PassRow`, `HeroBanner`, `TodayFactsCard`, `DescriptionBlock`, `DayPillRow`, `VisitInfoSection`), each TDD'd in isolation. Final task composes them into a rewritten `AttractionDetail.tsx`. Data layer (`getPassesForAttraction`, `cardpack`, `geocode`) is untouched — only JSX and component decomposition change.

**Tech Stack:** React 18 + TypeScript + Vite + HeroUI + Tailwind utility classes + CSS variables (defined in `web/src/styles/tokens.css`) + Vitest + @testing-library/react. Tests render via `renderApp()` helper at `web/src/test-utils.tsx`.

**Design rationale & mockups:** see `F:\pj\NorthShore Kids Events\_tmp_ux_brainstorm.html` (v2 detail-page brainstorm). The "研究页提议(v1 设计)" mockup in §③ is what we're implementing.

---

## File Structure

### Files to create (under `web/src/components/detail/`)

| File | Responsibility |
|---|---|
| `web/src/components/PassDeliveryChip.tsx` | Reusable chip rendering delivery type + distance (`✉ Email` / `📍 Pickup Nmi` / `🔄 Borrow Nmi`). Self-contained, used by `PassRow`. |
| `web/src/components/PassDeliveryChip.test.tsx` | Tests for the 3 chip variants + distance handling. |
| `web/src/components/AudienceValueLine.tsx` | Renders `coupon.audience_policies` as inline `Adult 50% off · Child FREE · up to 4`. Audience deep-green, value dark+bold, capacity light grey. |
| `web/src/components/AudienceValueLine.test.tsx` | Tests single/multi-policy + capacity inclusion. |
| `web/src/components/PassRow.tsx` | Composes chip + AudienceValueLine + library line + Book button. The detail-page row primitive. |
| `web/src/components/PassRow.test.tsx` | Tests digital/pickup/borrow rendering + Book click. |
| `web/src/components/detail/HeroBanner.tsx` | Full-bleed image with overlay back-button / heart / museum name + town gradient. |
| `web/src/components/detail/HeroBanner.test.tsx` | Tests image alt, back nav, heart toggle. |
| `web/src/components/detail/TodayFactsCard.tsx` | Today's open status + price tiers + optional reservation badge. |
| `web/src/components/detail/TodayFactsCard.test.tsx` | Tests open / closed / reservation states. |
| `web/src/components/detail/DescriptionBlock.tsx` | Description with read-more folding at 80/200 chars. |
| `web/src/components/detail/DescriptionBlock.test.tsx` | Tests short/medium/long thresholds. |
| `web/src/components/detail/DayPillRow.tsx` | 7-day pill row + "📅 Pick" pill that opens a full-calendar expander. |
| `web/src/components/detail/DayPillRow.test.tsx` | Tests pill rendering + select + expander toggle. |
| `web/src/components/detail/VisitInfoSection.tsx` | Collapsible section grouping hours / address / phone / website. |
| `web/src/components/detail/VisitInfoSection.test.tsx` | Tests hours visibility + collapse behavior. |
| `web/src/lib/dateRange.ts` | Tiny helper: `next7Days(todayIso): string[]`. |
| `web/src/lib/dateRange.test.ts` | Test for the date-range helper. |

### Files to modify

| File | Change |
|---|---|
| `web/src/pages/AttractionDetail.tsx` | Full JSX rewrite using new components. Data computations (`rowsForDate`, `sortRows`, `cellInfo`, etc.) retained but the no-card-row filter is moved earlier so dim rows are not rendered. The `Participating libraries (N)` section is removed. |

### Files NOT modified

- `web/src/components/CouponCalendar.tsx` — reused as-is inside `DayPillRow`'s expander.
- `web/src/components/CouponLine.tsx` — not used by detail page anymore (replaced by `AudienceValueLine`). It still serves `AttractionCard.tsx` until a future list-page refactor.
- `web/src/components/PassTypeLabel.tsx` — replaced by `PassDeliveryChip` on detail page, but PassTypeLabel still used by `AttractionCard.tsx`. Untouched.
- `web/src/data/load.ts`, `web/src/lib/tag-algorithm.ts`, `web/src/lib/restrictions.ts`, stores — untouched.

---

## CSS tokens you will need (already defined in `web/src/styles/tokens.css`)

```
--ink-1 / --ink-2 / --ink-3 / --ink-4   text colors (dark → light)
--rule                                  border color
--paper                                 light bg
--bg                                    page bg
--white                                 white
--g / --g-pale / --g-deep               brand green
--rd / --rd-pale                        red (borrow + closed)
--au / --au-pale (or --amber/--amber-pale — check file) amber (pickup + warnings)
```

In step 1 below, **verify token names**. The mockup HTML uses `--amber` / `--amber-pale` but the existing `MuseumReservationBanner.tsx` reads `var(--au)`. Match what already exists; do not invent new tokens.

---

### Task 0: Verify environment & token names

**Files:** none

- [ ] **Step 1: Verify dev server runs**

Run: `cd web && pnpm install && pnpm run dev`
Expected: dev server starts on `http://localhost:5173` (default Vite port).

- [ ] **Step 2: Verify tests run green**

Run: `cd web && pnpm vitest run --reporter=verbose`
Expected: all tests PASS. If any fail before our changes, document the failure and DO NOT proceed until told.

- [ ] **Step 3: Inspect `web/src/styles/tokens.css` to confirm color variable names**

Read the file and write a short list of the actual variable names for: brand-green / amber-or-au / red / paper / white / rule / ink-1..4. Throughout the plan below, where it says `var(--amber)` or `var(--amber-pale)`, substitute whatever the actual amber-family token is (likely `var(--au)` / `var(--au-pale)`).

- [ ] **Step 4: Read existing `AttractionDetail.tsx` end-to-end**

Read: `web/src/pages/AttractionDetail.tsx`. Note: `rowsForDate`, `sortRows`, `cellInfo`, `selectedDayRows` are the data computations we keep. The JSX from line ~203 to ~429 is what we replace.

---

### Task 1: `next7Days` date-range helper

**Files:**
- Create: `web/src/lib/dateRange.ts`
- Test: `web/src/lib/dateRange.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/dateRange.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { next7Days } from './dateRange';

describe('next7Days', () => {
  it('returns 7 ISO date strings starting at the given date', () => {
    const out = next7Days('2026-05-18');
    expect(out).toEqual([
      '2026-05-18', '2026-05-19', '2026-05-20', '2026-05-21',
      '2026-05-22', '2026-05-23', '2026-05-24',
    ]);
  });

  it('handles month rollover', () => {
    const out = next7Days('2026-05-28');
    expect(out).toEqual([
      '2026-05-28', '2026-05-29', '2026-05-30', '2026-05-31',
      '2026-06-01', '2026-06-02', '2026-06-03',
    ]);
  });

  it('handles year rollover', () => {
    const out = next7Days('2026-12-29');
    expect(out.slice(0, 4)).toEqual([
      '2026-12-29', '2026-12-30', '2026-12-31', '2027-01-01',
    ]);
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/lib/dateRange.test.ts`
Expected: FAIL — "Cannot find module './dateRange'".

- [ ] **Step 3: Implement `next7Days`**

Create `web/src/lib/dateRange.ts`:

```ts
function pad(n: number): string { return n < 10 ? `0${n}` : String(n); }

function toIso(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function next7Days(startIso: string): string[] {
  const start = new Date(`${startIso}T00:00:00`);
  const out: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    out.push(toIso(d));
  }
  return out;
}
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/lib/dateRange.test.ts`
Expected: PASS · 3 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/dateRange.ts web/src/lib/dateRange.test.ts
git commit -m "feat(web): add next7Days date helper for day-pill row"
```

---

### Task 2: `PassDeliveryChip` component

**Files:**
- Create: `web/src/components/PassDeliveryChip.tsx`
- Test: `web/src/components/PassDeliveryChip.test.tsx`

Renders one of three chip variants based on `pass.pass_type` + `pass.pickup_method`. Distance is included for physical types only.

Mapping rules:
- `pass_type === 'digital'` (or `pickup_method === 'digital'`) → `✉ Email`, green palette, no distance.
- `pass_type === 'physical-coupon'` → `📍 Pickup Nmi`, amber palette.
- `pass_type === 'physical-circ'` → `🔄 Borrow Nmi`, red palette.
- Distance rounded to integer (`Math.round`). If `distanceMi` is `null` / `undefined` for a physical type, omit the distance suffix → `📍 Pickup` / `🔄 Borrow`.

- [ ] **Step 1: Write the failing test**

Create `web/src/components/PassDeliveryChip.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PassDeliveryChip } from './PassDeliveryChip';

describe('PassDeliveryChip', () => {
  it('renders Email chip for digital pass without distance', () => {
    render(<PassDeliveryChip passType="digital" distanceMi={42} />);
    const chip = screen.getByText(/Email/);
    expect(chip).toBeInTheDocument();
    expect(chip.textContent).not.toMatch(/mi/);
  });

  it('renders Pickup chip with rounded distance', () => {
    render(<PassDeliveryChip passType="physical-coupon" distanceMi={6.7} />);
    expect(screen.getByText(/Pickup 7mi/)).toBeInTheDocument();
  });

  it('renders Borrow chip with rounded distance', () => {
    render(<PassDeliveryChip passType="physical-circ" distanceMi={12.3} />);
    expect(screen.getByText(/Borrow 12mi/)).toBeInTheDocument();
  });

  it('omits distance for physical pass when distanceMi is null', () => {
    render(<PassDeliveryChip passType="physical-coupon" distanceMi={null} />);
    const chip = screen.getByText(/Pickup/);
    expect(chip.textContent).not.toMatch(/mi/);
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/components/PassDeliveryChip.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `PassDeliveryChip`**

Create `web/src/components/PassDeliveryChip.tsx`:

```tsx
import type { Pass } from '../data/types';

interface Props {
  passType: Pass['pass_type'];
  distanceMi: number | null | undefined;
}

const BASE_STYLE: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 3,
  padding: '2px 7px',
  borderRadius: 10,
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  whiteSpace: 'nowrap',
};

export function PassDeliveryChip({ passType, distanceMi }: Props) {
  if (passType === 'digital') {
    return (
      <span style={{ ...BASE_STYLE, background: 'var(--g-pale)', color: 'var(--g-deep)' }}>
        ✉ Email
      </span>
    );
  }

  const distSuffix = distanceMi != null ? ` ${Math.round(distanceMi)}mi` : '';

  if (passType === 'physical-coupon') {
    return (
      <span style={{ ...BASE_STYLE, background: 'var(--au-pale)', color: 'var(--au)' }}>
        📍 Pickup{distSuffix}
      </span>
    );
  }

  // physical-circ
  return (
    <span style={{ ...BASE_STYLE, background: 'var(--rd-pale)', color: 'var(--rd)' }}>
      🔄 Borrow{distSuffix}
    </span>
  );
}
```

**Note:** If Task 0 step 3 found different amber-family token names, substitute them here (e.g. `--amber-pale` instead of `--au-pale`).

- [ ] **Step 4: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/components/PassDeliveryChip.test.tsx`
Expected: PASS · 4 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/PassDeliveryChip.tsx web/src/components/PassDeliveryChip.test.tsx
git commit -m "feat(web): add PassDeliveryChip — Email/Pickup/Borrow delivery chip"
```

---

### Task 3: `AudienceValueLine` component

**Files:**
- Create: `web/src/components/AudienceValueLine.tsx`
- Test: `web/src/components/AudienceValueLine.test.tsx`

Renders the coupon's audience_policies inline: `Adult 50% off · Child FREE · up to 4`.

Style spec:
- Audience word (`Adult` / `Child` / `Youth` / `<3` etc.): font-weight 600, color `var(--g-deep)`.
- Value (`50% off` / `FREE` / `$10 off` / `$5/person`): font-weight 700, color `var(--ink-2)`.
- Capacity suffix (`up to 4`): font-weight 400, color `var(--ink-3)`, prefixed by ` · `.
- Separator between policies: ` · ` in `var(--ink-3)`.

Audience bucketing rules (mirror existing `CouponLine.tsx` logic):
- `'Adult'` or `'Senior'` → "Adult"
- `'Child'` → "Child"
- `'Youth'` → "Youth"
- `'Everyone'` → "Everyone"
- `'Vehicle'` or `'Single ticket'` → skip (don't render this policy)
- Special suppression: if `age.max != null && age.max <= 5` AND `bucket === 'Child'`, render audience as `<{max+1}` (e.g. "<3"). Mirror existing `isRedundantAge` suppression rules.

Value formatting:
- `free` → "FREE"
- `percent-off` with value 50 → "50% off"
- `dollar-off` with value 10 → "$10 off"
- `per-person-price` with value 8 → "$8/person"
- `discount` → "discount"

Capacity:
- If `coupon.capacity.kind === 'people'` and `n` is positive → " · up to N"
- Otherwise omit.

- [ ] **Step 1: Write the failing test**

Create `web/src/components/AudienceValueLine.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AudienceValueLine } from './AudienceValueLine';
import type { Coupon } from '../data/types';

function makeCoupon(over: Partial<Coupon> = {}): Coupon {
  return {
    capacity: { kind: 'people', n: 4 },
    audience_policies: [
      { audience: 'Adult', age_range: { min: null, max: null }, count: null, form: 'percent-off', value: 50 },
    ],
    summary: '50% off',
    ...over,
  };
}

describe('AudienceValueLine', () => {
  it('renders single policy with capacity', () => {
    const { container } = render(<AudienceValueLine coupon={makeCoupon()} />);
    const text = container.textContent ?? '';
    expect(text).toMatch(/Adult/);
    expect(text).toMatch(/50% off/);
    expect(text).toMatch(/up to 4/);
  });

  it('renders multi-policy stack', () => {
    const c = makeCoupon({
      audience_policies: [
        { audience: 'Adult', age_range: { min: null, max: null }, count: null, form: 'percent-off', value: 50 },
        { audience: 'Child', age_range: { min: null, max: null }, count: null, form: 'free', value: null },
      ],
    });
    const { container } = render(<AudienceValueLine coupon={c} />);
    const text = container.textContent ?? '';
    expect(text).toMatch(/Adult/);
    expect(text).toMatch(/50% off/);
    expect(text).toMatch(/Child/);
    expect(text).toMatch(/FREE/);
  });

  it('omits capacity when n is 0 or kind is not people', () => {
    const c = makeCoupon({ capacity: { kind: 'unlimited', n: null } });
    const { container } = render(<AudienceValueLine coupon={c} />);
    expect(container.textContent ?? '').not.toMatch(/up to/);
  });

  it('formats per-person-price as $N/person', () => {
    const c = makeCoupon({
      audience_policies: [
        { audience: 'Everyone', age_range: { min: null, max: null }, count: null, form: 'per-person-price', value: 8 },
      ],
    });
    expect(render(<AudienceValueLine coupon={c} />).container.textContent ?? '').toMatch(/\$8\/person/);
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/components/AudienceValueLine.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `AudienceValueLine`**

Create `web/src/components/AudienceValueLine.tsx`:

```tsx
import type { AudiencePolicy, Coupon } from '../data/types';

interface Props {
  coupon: Coupon;
}

function audienceLabel(p: AudiencePolicy): string | null {
  const a = p.audience;
  if (a === 'Vehicle' || a === 'Single ticket') return null;
  // Narrow-age override: "<{max+1}" for child policies with explicit small max.
  if (a === 'Child' && p.age_range?.max != null && p.age_range.max <= 5) {
    return `<${p.age_range.max + 1}`;
  }
  if (a === 'Senior') return 'Adult';
  return a;
}

function valueLabel(p: AudiencePolicy): string {
  switch (p.form) {
    case 'free': return 'FREE';
    case 'percent-off': return p.value != null ? `${p.value}% off` : 'discount';
    case 'dollar-off': return p.value != null ? `$${p.value} off` : 'discount';
    case 'per-person-price': return p.value != null ? `$${p.value}/person` : 'discount';
    case 'discount': return 'discount';
  }
}

export function AudienceValueLine({ coupon }: Props) {
  const policies = coupon.audience_policies
    .map(p => ({ aud: audienceLabel(p), val: valueLabel(p) }))
    .filter((x): x is { aud: string; val: string } => x.aud !== null);

  const showCapacity =
    coupon.capacity?.kind === 'people' && typeof coupon.capacity.n === 'number' && coupon.capacity.n > 0;

  return (
    <span style={{ font: '600 12px/1.35 Source Serif 4, Georgia, serif', color: 'var(--g-deep)' }}>
      {policies.map((p, i) => (
        <span key={i}>
          {i > 0 && <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}> · </span>}
          {p.aud}{' '}
          <span style={{ color: 'var(--ink-2)', fontWeight: 700 }}>{p.val}</span>
        </span>
      ))}
      {showCapacity && (
        <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}>
          {' · '}up to {coupon.capacity.n}
        </span>
      )}
    </span>
  );
}
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/components/AudienceValueLine.test.tsx`
Expected: PASS · 4 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/AudienceValueLine.tsx web/src/components/AudienceValueLine.test.tsx
git commit -m "feat(web): add AudienceValueLine — audience · value · capacity inline"
```

---

### Task 4: `PassRow` component

**Files:**
- Create: `web/src/components/PassRow.tsx`
- Test: `web/src/components/PassRow.test.tsx`

Layout (left → right): chip + AudienceValueLine + (newline) library name (+ loan duration if circ) + Book button on the right.

Props:

```ts
interface PassRowProps {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  onBook: (pass: Pass) => void;
}
```

Rules:
- For `pass_type === 'physical-circ'`, append `· {N}-day loan` if `pass.loan_days != null` (check `Pass` type for the actual field; if it's `pass.loan_period_days` or similar, use that — read `web/src/data/types.ts` first).
- For digital, library line shows `library.name` (full).
- For physical, library line shows `library.name` (full) — the distance is already in the chip, so we don't repeat it on line 2.

- [ ] **Step 1: Read `web/src/data/types.ts` to confirm `Pass` field names for loan duration.**

Note the exact field name. If no field exists, omit the loan-duration suffix entirely (data not present yet).

- [ ] **Step 2: Write the failing test**

Create `web/src/components/PassRow.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PassRow } from './PassRow';
import type { Pass, Library, Coupon } from '../data/types';

const baseCoupon: Coupon = {
  capacity: { kind: 'people', n: 4 },
  audience_policies: [
    { audience: 'Everyone', age_range: { min: null, max: null }, count: null, form: 'free', value: null },
  ],
  summary: 'FREE',
};

function makePass(over: Partial<Pass> = {}): Pass {
  return {
    library_id: 'wakefield',
    attraction_slug: 'test',
    pass_type: 'digital',
    pickup_method: 'digital',
    coupon: baseCoupon,
    availability: null,
    restrictions: null,
    ...over,
  } as Pass;
}

const libWakefield: Library = {
  id: 'wakefield', name: 'Wakefield Public Library', town: 'Wakefield',
} as Library;

describe('PassRow', () => {
  it('renders digital pass with Email chip + library name', () => {
    render(
      <PassRow pass={makePass()} library={libWakefield} distanceMi={null} onBook={() => {}} />,
    );
    expect(screen.getByText(/Email/)).toBeInTheDocument();
    expect(screen.getByText(/Wakefield Public Library/)).toBeInTheDocument();
    expect(screen.getByText(/FREE/)).toBeInTheDocument();
  });

  it('renders pickup pass with chip + distance + library', () => {
    render(
      <PassRow
        pass={makePass({ pass_type: 'physical-coupon' })}
        library={libWakefield}
        distanceMi={7.2}
        onBook={() => {}}
      />,
    );
    expect(screen.getByText(/Pickup 7mi/)).toBeInTheDocument();
    expect(screen.getByText(/Wakefield Public Library/)).toBeInTheDocument();
  });

  it('invokes onBook when Book button clicked', () => {
    const onBook = vi.fn();
    render(
      <PassRow pass={makePass()} library={libWakefield} distanceMi={null} onBook={onBook} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /book/i }));
    expect(onBook).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 3: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/components/PassRow.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `PassRow`**

Create `web/src/components/PassRow.tsx`:

```tsx
import type { Pass, Library } from '../data/types';
import { PassDeliveryChip } from './PassDeliveryChip';
import { AudienceValueLine } from './AudienceValueLine';

interface Props {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  onBook: (pass: Pass) => void;
}

export function PassRow({ pass, library, distanceMi, onBook }: Props) {
  // If Task 4 step 1 found a loan-duration field on Pass (e.g. pass.loan_days),
  // wire it here as: const loanSuffix = pass.loan_days ? ` · ${pass.loan_days}-day loan` : '';
  const loanSuffix = '';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        padding: '10px 0',
        borderBottom: '1px solid var(--rule)',
      }}
    >
      <div style={{ flexGrow: 1, minWidth: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          marginBottom: 2, flexWrap: 'wrap',
        }}>
          <PassDeliveryChip passType={pass.pass_type} distanceMi={distanceMi} />
          <AudienceValueLine coupon={pass.coupon} />
        </div>
        <div style={{ fontSize: 11, color: 'var(--ink-3)' }}>
          {library.name}{loanSuffix}
        </div>
      </div>
      <button
        type="button"
        onClick={() => onBook(pass)}
        style={{
          background: 'var(--g)', color: 'var(--white)', border: 'none',
          borderRadius: 5, padding: '7px 14px',
          font: '600 12px sans-serif', cursor: 'pointer', alignSelf: 'center',
        }}
      >
        Book
      </button>
    </div>
  );
}
```

- [ ] **Step 5: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/components/PassRow.test.tsx`
Expected: PASS · 3 tests.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/PassRow.tsx web/src/components/PassRow.test.tsx
git commit -m "feat(web): add PassRow — chip + audience/value + library + Book"
```

---

### Task 5: `HeroBanner` component

**Files:**
- Create: `web/src/components/detail/HeroBanner.tsx`
- Test: `web/src/components/detail/HeroBanner.test.tsx`

Full-bleed (page-width) image, height 180px on mobile / 240px on desktop. Bottom-of-image gradient overlay (transparent → black 55%) carries the museum name in serif white. Back button top-left, FavoriteButton top-right, both with semi-transparent dark backgrounds for legibility on any photo.

Props:

```ts
interface HeroBannerProps {
  imageSrc: string;
  museumName: string;
  town?: string;       // shown small under museumName on the gradient
  favoriteSlug: string;  // passed to existing <FavoriteButton variant="overlay" />
}
```

- [ ] **Step 1: Write the failing test**

Create `web/src/components/detail/HeroBanner.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from '../../test-utils';
import { HeroBanner } from './HeroBanner';

describe('HeroBanner', () => {
  it('renders museum name and image', () => {
    renderApp(
      <HeroBanner
        imageSrc="/test.jpg"
        museumName="Museum of Fine Arts"
        town="Boston"
        favoriteSlug="mfa"
      />,
    );
    expect(screen.getByText('Museum of Fine Arts')).toBeInTheDocument();
    const img = screen.getByRole('img') as HTMLImageElement;
    expect(img.src).toContain('/test.jpg');
  });

  it('renders a back button', () => {
    renderApp(
      <HeroBanner imageSrc="/x.jpg" museumName="X" favoriteSlug="x" />,
    );
    expect(screen.getByRole('link', { name: /back/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/components/detail/HeroBanner.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `HeroBanner`**

Create `web/src/components/detail/HeroBanner.tsx`:

```tsx
import { Link } from 'react-router';
import { FavoriteButton } from '../FavoriteButton';

interface Props {
  imageSrc: string;
  museumName: string;
  town?: string;
  favoriteSlug: string;
}

export function HeroBanner({ imageSrc, museumName, town, favoriteSlug }: Props) {
  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <img
        src={imageSrc}
        alt=""
        style={{
          width: '100%', height: 180, objectFit: 'cover',
          display: 'block', background: 'var(--paper)',
        }}
      />
      <div
        aria-hidden
        style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(to top, rgba(0,0,0,0.55), transparent 55%)',
          pointerEvents: 'none',
        }}
      />
      <Link
        to="/"
        aria-label="Back to attractions"
        style={{
          position: 'absolute', top: 10, left: 10, zIndex: 2,
          background: 'rgba(0,0,0,0.5)', color: 'var(--white)',
          padding: '5px 9px', borderRadius: 4,
          fontSize: 12, fontWeight: 600, textDecoration: 'none',
        }}
      >
        ← Back
      </Link>
      <div style={{ position: 'absolute', top: 10, right: 10, zIndex: 2 }}>
        <FavoriteButton slug={favoriteSlug} variant="overlay" />
      </div>
      <div
        style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 1,
          padding: 14, color: 'var(--white)',
        }}
      >
        <h1 style={{
          font: '700 20px/1.2 Source Serif 4, Georgia, serif',
          margin: 0, color: 'var(--white)',
          textShadow: '0 1px 3px rgba(0,0,0,0.5)',
        }}>
          {museumName}
        </h1>
        {town && (
          <div style={{ fontSize: 12, marginTop: 2, opacity: 0.9 }}>📍 {town}</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/components/detail/HeroBanner.test.tsx`
Expected: PASS · 2 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/detail/HeroBanner.tsx web/src/components/detail/HeroBanner.test.tsx
git commit -m "feat(web): add HeroBanner — full-bleed image with overlay name/back/heart"
```

---

### Task 6: `TodayFactsCard` component

**Files:**
- Create: `web/src/components/detail/TodayFactsCard.tsx`
- Test: `web/src/components/detail/TodayFactsCard.test.tsx`

Renders a section card showing:
1. Heading: "Today · {weekday short, Mon DD}"
2. Open status line: `● Open now · 10am – 5pm` (green dot when open) OR `● Closed today` (red dot)
3. Price line: `$27 adult · FREE under 7` (use the existing helper `formatOriginalAdult` from AttractionDetail but extract it; OR import it fresh).
4. Optional `MuseumReservationBanner` shown if `museum_reservation` is present (reuse existing component).

Props:

```ts
interface TodayFactsCardProps {
  attraction: Attraction;
  todayIso: string;
}
```

- [ ] **Step 1: Extract `formatOriginalAdult` into a helper**

The helper currently lives inline in `web/src/pages/AttractionDetail.tsx:21-28`. Move it to `web/src/lib/originalPrice.ts`:

```ts
import type { OriginalPrice } from '../data/types';

export function formatOriginalAdult(op: OriginalPrice | null): string {
  const adult = op?.age_pricing?.adult?.price;
  const free = op?.age_pricing?.free_under_age;
  const suffix = free != null ? ` · FREE age<${free}` : '';
  if (adult != null) return `Adult $${adult}${suffix}`;
  if (free != null) return `FREE age<${free}`;
  return 'Price unavailable';
}
```

Delete the inline copy from `AttractionDetail.tsx` (this leaves a temporary unused import / broken reference — will be reconciled in Task 9 when we rewrite that file).

- [ ] **Step 2: Write the failing test**

Create `web/src/components/detail/TodayFactsCard.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TodayFactsCard } from './TodayFactsCard';
import type { Attraction } from '../../data/types';

function makeAttraction(over: Partial<Attraction> = {}): Attraction {
  return {
    slug: 'mfa', museum_name: 'MFA',
    address: '', website: null, phone: null, description: null,
    categories: [], sources: [],
    original_price: {
      age_pricing: {
        adult: { price: 27, min_age: null, max_age: null },
        youth: null, child: null, senior: null, free_under_age: 7,
      },
      identity_pricing: { student: null, educator: null, military: null },
      family: null, notes: null, source_url: null,
    },
    hero_image: null,
    hours: null,
    museum_reservation: null,
    ...over,
  } as Attraction;
}

describe('TodayFactsCard', () => {
  it('renders today heading and price line', () => {
    render(<TodayFactsCard attraction={makeAttraction()} todayIso="2026-05-18" />);
    expect(screen.getByText(/Today/)).toBeInTheDocument();
    expect(screen.getByText(/Adult \$27/)).toBeInTheDocument();
    expect(screen.getByText(/FREE/)).toBeInTheDocument();
  });

  it('shows reservation banner when reservation present', () => {
    const a = makeAttraction({
      museum_reservation: { required: true, url: null, notes: null } as any,
    });
    render(<TodayFactsCard attraction={a} todayIso="2026-05-18" />);
    expect(screen.getByText(/reservation/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/components/detail/TodayFactsCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `TodayFactsCard`**

Create `web/src/components/detail/TodayFactsCard.tsx`:

```tsx
import type { Attraction } from '../../data/types';
import { MuseumReservationBanner } from '../MuseumReservationBanner';
import { hoursDisplay, isClosedOn } from '../../lib/hours';
import { formatOriginalAdult } from '../../lib/originalPrice';

interface Props {
  attraction: Attraction;
  todayIso: string;
}

function formatHeading(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export function TodayFactsCard({ attraction, todayIso }: Props) {
  const closed = isClosedOn(attraction, todayIso);
  const hours = hoursDisplay(attraction, todayIso);
  return (
    <section style={{ padding: 14, borderBottom: '1px solid var(--rule)' }}>
      <h3 style={{
        margin: '0 0 8px',
        font: '600 13px sans-serif',
        color: 'var(--ink-3)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}>
        Today · {formatHeading(todayIso)}
      </h3>
      <div style={{ font: '500 13px sans-serif', color: 'var(--ink-2)', marginBottom: 6 }}>
        {closed ? (
          <span style={{ color: 'var(--rd)', fontWeight: 600 }}>● Closed today</span>
        ) : (
          <>
            <span style={{ color: 'var(--g)', fontWeight: 600 }}>● Open now</span>
            {hours && <> · {hours.value}</>}
          </>
        )}
      </div>
      <div style={{ font: '700 16px Source Serif 4, Georgia, serif', color: 'var(--ink-2)' }}>
        {formatOriginalAdult(attraction.original_price)}
      </div>
      {attraction.museum_reservation && (
        <div style={{ marginTop: 8 }}>
          <MuseumReservationBanner
            reservation={attraction.museum_reservation}
            attractionName={attraction.museum_name}
            variant="detail"
          />
        </div>
      )}
    </section>
  );
}
```

Note: `hoursDisplay` and `isClosedOn` already exist in `web/src/lib/hours.ts`. Verify their signatures before use.

- [ ] **Step 5: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/components/detail/TodayFactsCard.test.tsx`
Expected: PASS · 2 tests.

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/originalPrice.ts web/src/components/detail/TodayFactsCard.tsx web/src/components/detail/TodayFactsCard.test.tsx web/src/pages/AttractionDetail.tsx
git commit -m "feat(web): add TodayFactsCard; extract formatOriginalAdult helper"
```

---

### Task 7: `DescriptionBlock` component

**Files:**
- Create: `web/src/components/detail/DescriptionBlock.tsx`
- Test: `web/src/components/detail/DescriptionBlock.test.tsx`

Folding rules:
- length ≤ 80 chars → render full, no read-more
- 80 < length ≤ 200 → render full, no read-more (single paragraph is fine)
- length > 200 → render first ~150 chars + "Read more" toggle. When expanded, show full.

Props:

```ts
interface DescriptionBlockProps {
  description: string | null;
}
```

If `description` is null or empty string, render nothing.

- [ ] **Step 1: Write the failing test**

Create `web/src/components/detail/DescriptionBlock.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DescriptionBlock } from './DescriptionBlock';

describe('DescriptionBlock', () => {
  it('renders nothing when description is null', () => {
    const { container } = render(<DescriptionBlock description={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders short description without Read more', () => {
    render(<DescriptionBlock description="Short blurb about the museum." />);
    expect(screen.getByText(/Short blurb/)).toBeInTheDocument();
    expect(screen.queryByText(/Read more/i)).not.toBeInTheDocument();
  });

  it('shows Read more for long description and expands on click', () => {
    const long = 'X'.repeat(250);
    render(<DescriptionBlock description={long} />);
    const btn = screen.getByText(/Read more/i);
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.queryByText(/Read more/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/components/detail/DescriptionBlock.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `DescriptionBlock`**

Create `web/src/components/detail/DescriptionBlock.tsx`:

```tsx
import { useState } from 'react';

interface Props {
  description: string | null;
}

const FOLD_THRESHOLD = 200;
const PREVIEW_CHARS = 150;

export function DescriptionBlock({ description }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (!description) return null;
  const needsFold = description.length > FOLD_THRESHOLD;
  const shown = !needsFold || expanded
    ? description
    : description.slice(0, PREVIEW_CHARS).trimEnd() + '…';

  return (
    <section style={{ padding: 14, borderBottom: '1px solid var(--rule)' }}>
      <h3 style={{
        margin: '0 0 8px',
        font: '600 13px sans-serif',
        color: 'var(--ink-3)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}>About</h3>
      <div style={{ fontSize: 13, color: 'var(--ink-3)', lineHeight: 1.55 }}>
        {shown}
        {needsFold && !expanded && (
          <>
            {' '}
            <button
              type="button"
              onClick={() => setExpanded(true)}
              style={{
                background: 'transparent', border: 'none', padding: 0,
                color: 'var(--g)', fontWeight: 500, cursor: 'pointer', fontSize: 13,
              }}
            >Read more →</button>
          </>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/components/detail/DescriptionBlock.test.tsx`
Expected: PASS · 3 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/detail/DescriptionBlock.tsx web/src/components/detail/DescriptionBlock.test.tsx
git commit -m "feat(web): add DescriptionBlock with read-more folding"
```

---

### Task 8: `DayPillRow` component

**Files:**
- Create: `web/src/components/detail/DayPillRow.tsx`
- Test: `web/src/components/detail/DayPillRow.test.tsx`

Renders a horizontal scrollable row of 7 day pills + 1 trailing "📅 Pick" pill that, when clicked, toggles a full-calendar expander below the row. The full calendar uses the existing `CouponCalendar` component.

Each pill shows:
- Top line: `TODAY` / `SAT` / `SUN` / `MON` etc. (uppercase, 10px, light)
- Bottom line: best-deal label for that date (`FREE` / `50%` / `$5` / blank)

Active pill = brand green background, white text.

Props:

```ts
interface DayPillRowProps {
  todayIso: string;
  selectedDate: string;
  onSelect: (iso: string) => void;
  // For the expander:
  month: string;
  setMonth: (m: string) => void;
  cellInfo: Record<string, { best: string; isFree: boolean }>;
  monthPills: string[];   // already-computed list of selectable months
}
```

When the user clicks 📅 Pick, an expander opens showing `month pill row + CouponCalendar`. When user clicks any of the 7 day pills, the expander closes.

- [ ] **Step 1: Write the failing test**

Create `web/src/components/detail/DayPillRow.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DayPillRow } from './DayPillRow';

describe('DayPillRow', () => {
  const baseProps = {
    todayIso: '2026-05-18',
    selectedDate: '2026-05-18',
    month: '2026-05',
    setMonth: vi.fn(),
    cellInfo: {},
    monthPills: ['2026-05'],
  };

  it('renders 7 day pills + a pick pill', () => {
    render(<DayPillRow {...baseProps} onSelect={() => {}} />);
    expect(screen.getByText(/TODAY/)).toBeInTheDocument();
    expect(screen.getByText(/📅/)).toBeInTheDocument();
  });

  it('calls onSelect when a day pill is clicked', () => {
    const onSelect = vi.fn();
    render(<DayPillRow {...baseProps} onSelect={onSelect} />);
    // click any day pill (today is selected; click another)
    const pills = screen.getAllByRole('button');
    fireEvent.click(pills[1]); // second pill = tomorrow
    expect(onSelect).toHaveBeenCalled();
  });

  it('toggles calendar expander when pick pill clicked', () => {
    render(<DayPillRow {...baseProps} onSelect={() => {}} />);
    expect(screen.queryByText(/May 2026/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/📅/));
    expect(screen.getByText(/May 2026/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/components/detail/DayPillRow.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `DayPillRow`**

Create `web/src/components/detail/DayPillRow.tsx`:

```tsx
import { useState } from 'react';
import { next7Days } from '../../lib/dateRange';
import { CouponCalendar } from '../CouponCalendar';

interface Props {
  todayIso: string;
  selectedDate: string;
  onSelect: (iso: string) => void;
  month: string;
  setMonth: (m: string) => void;
  cellInfo: Record<string, { best: string; isFree: boolean }>;
  monthPills: string[];
}

const DOW = ['SUN','MON','TUE','WED','THU','FRI','SAT'];

function pillLabel(iso: string, todayIso: string): string {
  if (iso === todayIso) return 'TODAY';
  const d = new Date(`${iso}T00:00:00`);
  return DOW[d.getDay()];
}

export function DayPillRow({
  todayIso, selectedDate, onSelect, month, setMonth, cellInfo, monthPills,
}: Props) {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const days = next7Days(todayIso);

  const handleDayClick = (iso: string) => {
    onSelect(iso);
    setCalendarOpen(false);
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
        {days.map(iso => {
          const active = iso === selectedDate && !calendarOpen;
          const best = cellInfo[iso]?.best ?? '';
          return (
            <button
              key={iso}
              type="button"
              onClick={() => handleDayClick(iso)}
              style={{
                padding: '6px 12px', borderRadius: 14,
                border: `1px solid ${active ? 'var(--g)' : 'var(--rule)'}`,
                background: active ? 'var(--g)' : 'var(--white)',
                color: active ? 'var(--white)' : 'var(--ink-2)',
                font: '500 12px sans-serif', whiteSpace: 'nowrap', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 50,
              }}
            >
              <span style={{
                fontSize: 10,
                color: active ? 'rgba(255,255,255,0.7)' : 'var(--ink-3)',
                marginBottom: 1,
              }}>{pillLabel(iso, todayIso)}</span>
              <span style={{ fontWeight: 600 }}>{best || '—'}</span>
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => setCalendarOpen(o => !o)}
          style={{
            padding: '6px 12px', borderRadius: 14,
            border: `1px solid ${calendarOpen ? 'var(--g)' : 'var(--rule)'}`,
            background: calendarOpen ? 'var(--g)' : 'var(--white)',
            color: calendarOpen ? 'var(--white)' : 'var(--ink-2)',
            font: '500 12px sans-serif', cursor: 'pointer',
            display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 50,
          }}
        >
          <span style={{
            fontSize: 10,
            color: calendarOpen ? 'rgba(255,255,255,0.7)' : 'var(--ink-3)',
            marginBottom: 1,
          }}>PICK</span>
          <span>📅</span>
        </button>
      </div>
      {calendarOpen && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            {monthPills.map(m => {
              const active = m === month;
              const d = new Date(`${m}-01T00:00:00`);
              const lbl = d.toLocaleString('en-US', { month: 'short', year: 'numeric' });
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMonth(m)}
                  style={{
                    padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500,
                    background: active ? 'var(--g)' : 'transparent',
                    color: active ? 'var(--white)' : 'var(--ink-2)',
                    border: `1px solid ${active ? 'var(--g)' : 'var(--rule)'}`,
                    cursor: 'pointer',
                  }}
                >{lbl}</button>
              );
            })}
          </div>
          <CouponCalendar
            month={month}
            selectedDate={selectedDate}
            todayIso={todayIso}
            cellInfo={cellInfo}
            onSelect={(iso) => { onSelect(iso); setCalendarOpen(false); }}
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/components/detail/DayPillRow.test.tsx`
Expected: PASS · 3 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/detail/DayPillRow.tsx web/src/components/detail/DayPillRow.test.tsx
git commit -m "feat(web): add DayPillRow — 7-day pills + calendar expander"
```

---

### Task 9: `VisitInfoSection` component

**Files:**
- Create: `web/src/components/detail/VisitInfoSection.tsx`
- Test: `web/src/components/detail/VisitInfoSection.test.tsx`

Section showing:
- "Hours this week" — single-line summary (e.g. "closed Mon · open Tue–Sun") + "See all →" toggle that expands to weekly grid (reuse the existing weekly-grid markup from `AttractionDetail.tsx:262-292`).
- Address (plaintext)
- Phone (`tel:` link) + Website link (`target=_blank`)

Props:

```ts
interface VisitInfoSectionProps {
  attraction: Attraction;
}
```

- [ ] **Step 1: Write the failing test**

Create `web/src/components/detail/VisitInfoSection.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VisitInfoSection } from './VisitInfoSection';
import type { Attraction } from '../../data/types';

function makeAttraction(): Attraction {
  return {
    slug: 'mfa', museum_name: 'MFA',
    address: '465 Huntington Ave, Boston, MA 02115',
    website: 'https://mfa.org',
    phone: '617-267-9300',
    description: null, categories: [], sources: [],
    original_price: null as any,
    hero_image: null,
    hours: {
      status: 'regular',
      regular_hours: {
        sun: '10am – 5pm', mon: 'Closed', tue: '10am – 5pm', wed: '10am – 5pm',
        thu: '10am – 10pm', fri: '10am – 10pm', sat: '10am – 5pm',
      },
      notes: null,
    } as any,
    museum_reservation: null,
  } as Attraction;
}

describe('VisitInfoSection', () => {
  it('renders address, phone, website', () => {
    render(<VisitInfoSection attraction={makeAttraction()} />);
    expect(screen.getByText(/465 Huntington/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /617-267-9300/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /mfa\.org/ })).toBeInTheDocument();
  });

  it('shows full weekly hours when See all clicked', () => {
    render(<VisitInfoSection attraction={makeAttraction()} />);
    // weekly grid hidden initially
    expect(screen.queryByText(/THU/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/See all/i));
    expect(screen.getByText(/THU/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd web && pnpm vitest run src/components/detail/VisitInfoSection.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `VisitInfoSection`**

Create `web/src/components/detail/VisitInfoSection.tsx`:

```tsx
import { useState } from 'react';
import type { Attraction } from '../../data/types';
import { weeklyHoursList } from '../../lib/hours';

interface Props {
  attraction: Attraction;
}

function weeklySummary(attraction: Attraction): string {
  if (!attraction.hours || attraction.hours.status === 'varies' || !attraction.hours.regular_hours) {
    return 'Hours vary — see museum website';
  }
  const rh = attraction.hours.regular_hours;
  const closedDays: string[] = [];
  const openDays: string[] = [];
  const order: Array<[string, keyof typeof rh]> = [
    ['Sun','sun'],['Mon','mon'],['Tue','tue'],['Wed','wed'],
    ['Thu','thu'],['Fri','fri'],['Sat','sat'],
  ];
  for (const [label, key] of order) {
    const v = rh[key];
    if (!v || /closed/i.test(v)) closedDays.push(label);
    else openDays.push(label);
  }
  if (closedDays.length === 0) return 'open daily';
  if (closedDays.length === 7) return 'closed all week';
  return `closed ${closedDays.join(', ')} · open ${openDays.join(', ')}`;
}

export function VisitInfoSection({ attraction }: Props) {
  const [showAll, setShowAll] = useState(false);
  return (
    <section style={{ padding: 14, borderBottom: '1px solid var(--rule)' }}>
      <h3 style={{
        margin: '0 0 8px', font: '600 13px sans-serif', color: 'var(--ink-3)',
        textTransform: 'uppercase', letterSpacing: '0.05em',
      }}>Visit info</h3>

      <div style={{ fontSize: 12, color: 'var(--ink-2)', margin: '4px 0' }}>
        <b>Hours this week</b>{' '}
        <span style={{ color: 'var(--ink-3)' }}>· {weeklySummary(attraction)}</span>
        {attraction.hours && attraction.hours.status !== 'varies' && (
          <button
            type="button"
            onClick={() => setShowAll(s => !s)}
            style={{
              background: 'transparent', border: 'none', padding: 0,
              color: 'var(--g)', fontWeight: 500, fontSize: 11, marginLeft: 6, cursor: 'pointer',
            }}
          >{showAll ? 'Hide' : 'See all →'}</button>
        )}
      </div>

      {showAll && attraction.hours && attraction.hours.status !== 'varies' && attraction.hours.regular_hours && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px', margin: '8px 0' }}>
          {weeklyHoursList(attraction.hours).map(row => {
            const isClosed = row.value.toLowerCase() === 'closed';
            return (
              <div key={row.key} style={{ display: 'flex', gap: 6, fontSize: 11 }}>
                <span style={{ color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.04em', width: 32 }}>
                  {row.label}
                </span>
                <span style={{ color: isClosed ? 'var(--rd)' : 'var(--ink-2)', fontWeight: 500 }}>
                  {row.value}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {attraction.address && (
        <div style={{ fontSize: 12, color: 'var(--ink-2)', margin: '8px 0' }}>
          <b>Address</b>
          <div style={{ color: 'var(--ink-3)', marginTop: 2 }}>{attraction.address}</div>
        </div>
      )}

      <div style={{ fontSize: 12, color: 'var(--ink-2)', margin: '8px 0', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {attraction.phone && (
          <span>📞 <a href={`tel:${attraction.phone.replace(/[^\d+]/g, '')}`} style={{ color: 'var(--g)' }}>{attraction.phone}</a></span>
        )}
        {attraction.website && (
          <span>🌐 <a href={attraction.website} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--g)' }}>
            {attraction.website.replace(/^https?:\/\//, '').replace(/\/$/, '')} →
          </a></span>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd web && pnpm vitest run src/components/detail/VisitInfoSection.test.tsx`
Expected: PASS · 2 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/detail/VisitInfoSection.tsx web/src/components/detail/VisitInfoSection.test.tsx
git commit -m "feat(web): add VisitInfoSection — collapsed weekly hours + address + contact"
```

---

### Task 10: Rewrite `AttractionDetail.tsx` to compose new sections

**Files:**
- Modify: `web/src/pages/AttractionDetail.tsx`

Keep the data computation block (`rowsForDate`, `sortRows`, `dataHorizon`, `monthPills`, `datesOfMonth`, `cellInfo`, `selectedDayRows`). Replace the entire JSX return.

Changes:
1. Filter `selectedDayRows` to **exclude rows where `!userHasCard`** (no-card rows are hidden, not dimmed).
2. Remove the `Participating libraries (N)` section entirely.
3. Use the new components for layout. The page wraps in a `<div className="max-w-md mx-auto bg-white">` (mobile-first single column; the old `max-w-6xl` is dropped since this is now a mobile-shaped page).

- [ ] **Step 1: Read the current full `AttractionDetail.tsx`** to capture the data-layer code we keep.

- [ ] **Step 2: Rewrite the file**

Replace the entire contents of `web/src/pages/AttractionDetail.tsx` with:

```tsx
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router';
import {
  getAttractionBySlug, getPassesForAttraction, getLibraries,
} from '../data/load';
import { CouponCalendar } from '../components/CouponCalendar';
import { PassRow } from '../components/PassRow';
import { HeroBanner } from '../components/detail/HeroBanner';
import { TodayFactsCard } from '../components/detail/TodayFactsCard';
import { DescriptionBlock } from '../components/detail/DescriptionBlock';
import { DayPillRow } from '../components/detail/DayPillRow';
import { VisitInfoSection } from '../components/detail/VisitInfoSection';
import { GuestLockedRow } from '../components/GuestLockedRow';
import { SignInModal } from '../components/SignInModal';
import { BookingConfirmModal } from '../components/BookingConfirmModal';
import { passBlockedByRestrictions } from '../lib/restrictions';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip, haversineMiles } from '../lib/distance';
import { couponRank } from '../lib/tag-algorithm';
import { heroSrc } from '../lib/hero';
import { todayIso } from '../lib/dates';
import type { Geo, Pass, Library } from '../data/types';

interface Row {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  available: boolean;
  userHasCard: boolean;
}

function townFromAddress(addr: string): string {
  const m = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\s+\d{5}/);
  if (m) return m[1].trim();
  const m2 = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\b/);
  return m2 ? m2[1].trim() : '';
}

export function AttractionDetail() {
  const { slug } = useParams<{ slug: string }>();
  const user = useAuth(s => s.currentUser);
  const cardpack = useCardpack(s => s.pack);
  const loadCardpack = useCardpack(s => s.load);
  const loadFavorites = useFavorites(s => s.load);
  const [userGeo, setUserGeo] = useState<Geo | null>(null);
  const today = useMemo(() => todayIso(), []);
  const [month, setMonth] = useState(() => today.slice(0, 7));
  const [selectedDate, setSelectedDate] = useState<string>(today);
  const [bookingPass, setBookingPass] = useState<Pass | null>(null);
  const [signInOpen, setSignInOpen] = useState(false);

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

  const userCardLibIds = useMemo(
    () => (user && Object.keys(cardpack.cards).length > 0)
      ? new Set(Object.keys(cardpack.cards))
      : null,
    [user, cardpack.cards],
  );

  const dataHorizon = useMemo(() => {
    let max = '';
    for (const p of allPasses) {
      if (!p.availability) continue;
      for (const d in p.availability) if (d > max) max = d;
    }
    return max;
  }, [allPasses]);

  const monthPills = useMemo(() => {
    const out: string[] = [];
    const base = new Date(`${today}T00:00:00`);
    base.setDate(1);
    const horizonMonth = dataHorizon.slice(0, 7);
    for (let i = 0; i < 6; i++) {
      const d = new Date(base);
      d.setMonth(base.getMonth() + i);
      const m = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
      if (horizonMonth && m > horizonMonth) break;
      out.push(m);
      if (!horizonMonth) break;
    }
    return out;
  }, [today, dataHorizon]);

  const datesOfMonth = useMemo(() => {
    const [yStr, mStr] = month.split('-');
    const year = Number(yStr); const m = Number(mStr);
    const lastDay = new Date(year, m, 0).getDate();
    return Array.from({ length: lastDay }, (_, i) =>
      `${yStr}-${mStr}-${String(i + 1).padStart(2, '0')}`,
    );
  }, [month]);

  const rowsForDate = useMemo(() => (date: string): Row[] => {
    const rows: Row[] = [];
    for (const pass of allPasses) {
      const library = libById.get(pass.library_id);
      if (!library) continue;
      if (passBlockedByRestrictions(pass.restrictions, date)) continue;
      const available = pass.availability === null
        ? true
        : pass.availability[date] === 'available';
      const dist = userGeo && library.geo ? haversineMiles(userGeo, library.geo) : null;
      const userHasCard = userCardLibIds ? userCardLibIds.has(pass.library_id) : true;
      rows.push({ pass, library, distanceMi: dist, available, userHasCard });
    }
    return rows;
  }, [allPasses, libById, userCardLibIds, userGeo]);

  const sortRows = useMemo(() => (rows: Row[]) => {
    return [...rows].sort((a, b) => {
      const ra = couponRank(a.pass.coupon);
      const rb = couponRank(b.pass.coupon);
      if (ra !== rb) return ra - rb;
      if (a.distanceMi == null && b.distanceMi != null) return 1;
      if (a.distanceMi != null && b.distanceMi == null) return -1;
      if (a.distanceMi != null && b.distanceMi != null) return a.distanceMi - b.distanceMi;
      return a.library.id.localeCompare(b.library.id);
    });
  }, []);

  const heroImg = useMemo(
    () => attraction ? heroSrc(attraction) : '/placeholders/default.svg',
    [attraction],
  );

  const cellInfo = useMemo(() => {
    const out: Record<string, { best: string; isFree: boolean }> = {};
    for (const d of datesOfMonth) {
      // Compute best deal ONLY among rows the user can actually use.
      const rows = rowsForDate(d)
        .filter(r => r.available)
        .filter(r => userCardLibIds === null || r.userHasCard);
      if (rows.length === 0) { out[d] = { best: '', isFree: false }; continue; }
      const sorted = sortRows(rows);
      const top = sorted[0].pass.coupon.audience_policies[0];
      let label = ''; let isFree = false;
      if (top) {
        switch (top.form) {
          case 'free': label = 'FREE'; isFree = true; break;
          case 'percent-off': label = top.value != null ? `${top.value}%` : '%'; break;
          case 'dollar-off': label = top.value != null ? `-$${top.value}` : '$ off'; break;
          case 'per-person-price': label = top.value != null ? `$${top.value}` : '$'; break;
          case 'discount': label = 'disc'; break;
        }
      }
      out[d] = { best: label, isFree };
    }
    return out;
  }, [datesOfMonth, rowsForDate, sortRows, userCardLibIds]);

  // Selected day's rows — HIDE no-card rows entirely (do not dim).
  const selectedDayRows = useMemo(
    () => sortRows(
      rowsForDate(selectedDate)
        .filter(r => r.available)
        .filter(r => userCardLibIds === null || r.userHasCard),
    ),
    [selectedDate, rowsForDate, sortRows, userCardLibIds],
  );

  if (!slug) return <div className="max-w-md mx-auto p-4">Missing slug.</div>;
  if (!attraction) return <div className="max-w-md mx-auto p-4">Attraction "{slug}" not found.</div>;

  const town = townFromAddress(attraction.address);

  return (
    <div className="max-w-md mx-auto" style={{ background: 'var(--white)', minHeight: '100vh' }}>
      <HeroBanner
        imageSrc={heroImg}
        museumName={attraction.museum_name}
        town={town}
        favoriteSlug={attraction.slug}
      />

      {attraction.categories.length > 0 && (
        <div style={{ padding: '14px 14px 0' }}>
          {attraction.categories.map(c => (
            <span key={c} style={{
              display: 'inline-block', padding: '2px 8px', borderRadius: 10,
              background: 'var(--paper)', color: 'var(--ink-3)',
              fontSize: 10, fontWeight: 500, marginRight: 4, marginBottom: 4,
            }}>{c}</span>
          ))}
        </div>
      )}

      <TodayFactsCard attraction={attraction} todayIso={today} />

      <DescriptionBlock description={attraction.description} />

      {/* Coupon / perks section — green tint to mark product UVP */}
      <section style={{ padding: 14, background: 'var(--g-pale)', borderBottom: '1px solid var(--rule)' }}>
        <h3 style={{
          margin: '0 0 8px', font: '600 13px sans-serif',
          color: 'var(--g-deep)', textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>Your perks · what it'll cost you</h3>

        <DayPillRow
          todayIso={today}
          selectedDate={selectedDate}
          onSelect={setSelectedDate}
          month={month}
          setMonth={setMonth}
          cellInfo={cellInfo}
          monthPills={monthPills}
        />

        <div style={{ marginTop: 12 }}>
          {selectedDayRows.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              No coupons available on this date
            </div>
          ) : (
            selectedDayRows.slice(0, 10).map((r, i) => {
              if (!user) {
                return (
                  <GuestLockedRow
                    key={`${r.pass.library_id}-${i}`}
                    pass={r.pass}
                    library={r.library}
                    onSignInRequest={() => setSignInOpen(true)}
                  />
                );
              }
              return (
                <PassRow
                  key={`${r.pass.library_id}-${i}`}
                  pass={r.pass}
                  library={r.library}
                  distanceMi={r.distanceMi}
                  onBook={setBookingPass}
                />
              );
            })
          )}
          {selectedDayRows.length > 10 && (
            <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 6 }}>
              +{selectedDayRows.length - 10} more
            </div>
          )}
        </div>
      </section>

      <VisitInfoSection attraction={attraction} />

      <BookingConfirmModal
        pass={bookingPass}
        library={bookingPass ? (libById.get(bookingPass.library_id) ?? null) : null}
        cardpack={cardpack}
        onClose={() => setBookingPass(null)}
      />
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
    </div>
  );
}
```

- [ ] **Step 3: Run typecheck**

Run: `cd web && pnpm tsc --noEmit`
Expected: no errors. If there are, fix them — common issues:
- `hoursDisplay` import path or signature changed → adjust
- `userHasCard` filter when `userCardLibIds` is null (guest user) — current code lets all through, which is correct because the GuestLockedRow path will handle gating

- [ ] **Step 4: Run all tests**

Run: `cd web && pnpm vitest run`
Expected: all PASS. There is no existing `AttractionDetail.test.tsx` at the time this plan was written, so only the new component tests should be affected. If a test file has appeared since (check `web/src/pages/AttractionDetail.test.tsx`), read it and update the queries to target the new structure (HeroBanner / TodayFactsCard / DayPillRow / PassRow / VisitInfoSection).

- [ ] **Step 5: Manual smoke test in browser**

Run: `cd web && pnpm run dev`. Open `http://localhost:5173`, navigate into any attraction.

Verify visually:
- Hero image is full-bleed with name overlay
- Back arrow top-left, heart top-right
- Category chips below hero
- "Today · {day}" card with open/closed status + price
- Description (or nothing if missing)
- Green-tinted "Your perks" section with day pills + pass rows
- Click 📅 Pick → calendar expander opens
- "Visit info" with collapsed hours + address + phone + website
- No "Participating libraries" section anywhere
- No grayed-out "no card" rows

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/AttractionDetail.tsx
git commit -m "feat(web): rewrite AttractionDetail to research-first layout"
```

---

## Self-Review Checklist

After all tasks done, verify:

1. **All new component files exist** with paired `.test.tsx` files.
2. **`pnpm vitest run` is green** across the whole web project.
3. **`pnpm tsc --noEmit` is green**.
4. **Manual smoke**: open detail page in dev server. Verify research-first order matches the mockup in `_tmp_ux_brainstorm.html`.
5. **No-card rows hidden**: sign in as a user with one card (Wakefield), pick an attraction with multi-library coverage, verify only Wakefield rows appear in "Your perks".
6. **`Participating libraries` is gone** from the page.
7. **Calendar expander works**: click 📅 Pick, full month calendar appears; clicking a date both selects it AND closes the expander.

---

## Out of scope (NOT in this plan)

- Migrating `AttractionCard.tsx` (list page) to use `PassRow`. Future plan.
- Hero price badge ("FREE with Wakefield card today"). User undecided.
- Closed-museum sort policy for list page. Separate decision.
- Search / sort changes on list page.

---

## Design references

- Brainstorm doc: `F:\pj\NorthShore Kids Events\_tmp_ux_brainstorm.html` (§③ "研究页提议(v1 设计)" mockup)
- Original screenshot: `F:\pj\NorthShore Kids Events\ScreenShot_2026-05-18_220603_150.png`
