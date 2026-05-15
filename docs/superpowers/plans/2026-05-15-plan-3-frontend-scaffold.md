# Plan 3 — Frontend Scaffolding Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to execute task-by-task.

**Goal:** 在 `web/` 目录搭一个能跑起来的 React + Vite + TypeScript + HeroUI 空壳:配色 token、路由、mock auth、数据加载管道、占位页面。实际 UI 实现是 plan-4。

**Architecture:** Vite + React 18 + TypeScript + HeroUI v2 (Tailwind v4) + react-router v6 + Zustand 状态管理。`data/structured/{libraries,attractions,passes}.json` 通过 Vite import 编译进 bundle(总 ~3-5MB,够用)。`data/static/images/` 软链/拷贝到 `web/public/images/`。Mock auth = 3 个硬编码 user 写在 `src/mock/users.json`,session/卡包/收藏存 `localStorage`。

**Tech Stack:** Node 22 / pnpm / Vite 7 / React 19 / TypeScript 5 / HeroUI v2 / Tailwind 4 / react-router 7 / Zustand 5 / Vitest

---

## 0. 目录布局(本 plan 产出)

```
web/                         # NEW — 整个前端独立子目录
├── public/
│   ├── images/              # 软链/拷贝自 data/static/images/(gitignored)
│   └── placeholders/        # 软链自 data/static/placeholders/
├── src/
│   ├── main.tsx             # Vite entry
│   ├── App.tsx              # 路由根
│   ├── styles/
│   │   └── tokens.css       # CSS variables (spec §2.1)
│   ├── data/
│   │   ├── load.ts          # 导入 3 个 JSON,导出 typed accessors
│   │   └── types.ts         # Library / Attraction / Pass TypeScript 类型
│   ├── auth/
│   │   ├── store.ts         # Zustand store: current user, sign in/out
│   │   └── users.json       # 3 硬编码账号 (alex/rbt/admin)
│   ├── pages/               # 占位 stub 页面
│   │   ├── AttractionsList.tsx
│   │   ├── AttractionDetail.tsx
│   │   ├── MyPasses.tsx
│   │   └── NotFound.tsx
│   ├── components/
│   │   ├── TopBar.tsx       # logo + search + user menu
│   │   └── SignInModal.tsx
│   └── lib/
│       └── localStorage.ts  # typed wrappers (cardpack, favorites, ZIP)
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── README.md                # how to run

# 顶层(repo root)新增 .gitignore 条目:
web/node_modules
web/dist
web/public/images/           # symlinked from data/static/images (large)
```

## File / responsibility split (前端)

- `tokens.css` — only declares CSS custom properties. No selectors beyond `:root`.
- `data/load.ts` — single source of truth for loading the 3 structured JSONs. Other modules import from here, not from JSON directly.
- `data/types.ts` — TypeScript interfaces matching the build pipeline output schema. **One file, kept in sync with `src/malibbene/build/*.py` manually.**
- `auth/store.ts` — Zustand store with `currentUser`, `signIn(username, password)`, `signOut()`, `loadFromStorage()`.
- `pages/*.tsx` — each one is a stub: render the page name + minimal placeholder so we can visually confirm routing works.
- `components/TopBar.tsx` — minimal: brand text, search input (non-functional), user menu (Sign in button OR avatar dropdown).
- `components/SignInModal.tsx` — HeroUI Modal with username/password inputs, calls `store.signIn()`.

---

## Task 1 — Scaffold the Vite + React project

**Files created by Vite scaffold:** `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, etc.

### Step 1.1: Create web/ via Vite

```bash
cd "F:/pj/NorthShore Kids Events"
pnpm create vite@latest web --template react-ts
```

When prompted for project name, just press Enter (it'll use `web`). After creation, Vite outputs install instructions.

### Step 1.2: Install dependencies

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm install
```

### Step 1.3: Install runtime libraries

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm add react-router@^7 zustand@^5 @heroui/react@^2 framer-motion@^11
pnpm add -D tailwindcss@^4 @tailwindcss/vite@^4 vitest@^3 @testing-library/react@^16 @testing-library/jest-dom@^6 jsdom@^25
```

> Versions: HeroUI v2 + Tailwind v4 (the current major). If install fails on specific versions, use the latest available.

### Step 1.4: Smoke test dev server starts

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm run dev
```

Wait ~3 seconds — dev server should report `Local:   http://localhost:5173/`. Kill the server (Ctrl+C). Do NOT keep dev server running in the task.

### Step 1.5: Gitignore web/node_modules

Append to repo-root `.gitignore`:
```
web/node_modules
web/dist
web/public/images
```

### Step 1.6: Commit

```bash
git add web/ .gitignore
git commit -m "feat(web): scaffold Vite + React 19 + TS project + install deps"
```

(Note: `web/node_modules` won't be staged thanks to gitignore.)

---

## Task 2 — Configure Tailwind v4 + HeroUI + token CSS

### Step 2.1: Configure Vite for Tailwind v4

Edit `web/vite.config.ts` to add the Tailwind plugin:

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
});
```

### Step 2.2: Create CSS token file

Create `web/src/styles/tokens.css`:

```css
@import "tailwindcss";

:root {
  /* Background */
  --bg: #F4F3EF;
  --paper: #ECEAE4;
  --white: #FAFAF7;

  /* Ink */
  --ink: #000000;
  --ink-2: #1A1917;
  --ink-3: #4A4845;

  /* Primary green */
  --g: #1B5740;
  --g-2: #2A7055;
  --g-light: #C4DDCF;
  --g-pale: #EAF1EE;

  /* Amber */
  --au: #8C6018;
  --au-pale: #F4EFE8;

  /* Orange */
  --or: #D97706;
  --or-pale: #FDF1E2;

  /* Red */
  --rd: #8C2A1E;
  --rd-pale: #F4EAE9;

  /* Rules */
  --rule: #D0CEC6;
  --rule-strong: #B5B2A8;
}

body {
  background-color: var(--bg);
  color: var(--ink-2);
  font-family: 'DM Sans', 'PingFang SC', 'Helvetica Neue', sans-serif;
  font-size: 13px;
  line-height: 1.78;
  -webkit-font-smoothing: antialiased;
}

/* Font for editorial headings */
.font-serif {
  font-family: 'Libre Baskerville', Georgia, serif;
}
```

### Step 2.3: Replace default Vite styles

Delete `web/src/App.css` and `web/src/index.css` (if they exist), then in `web/src/main.tsx` change the CSS import:

```typescript
import './styles/tokens.css';
```

### Step 2.4: Add Google Fonts link to index.html

Edit `web/index.html` `<head>` to add (before existing styles):

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500;700&display=swap" rel="stylesheet">
```

### Step 2.5: Wire HeroUI provider

Edit `web/src/main.tsx`:

```typescript
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { HeroUIProvider } from '@heroui/react';
import './styles/tokens.css';
import App from './App.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HeroUIProvider>
      <App />
    </HeroUIProvider>
  </StrictMode>,
);
```

### Step 2.6: Smoke test renders correctly

Replace `web/src/App.tsx` with a smoke-test component:

```typescript
import { Button } from '@heroui/react';

function App() {
  return (
    <div className="p-8">
      <h1 className="font-serif" style={{ fontSize: '32px', color: 'var(--g)' }}>
        MuseumPass MA
      </h1>
      <p style={{ color: 'var(--ink-3)' }}>Visual smoke test</p>
      <Button color="primary" className="mt-4">HeroUI button</Button>
    </div>
  );
}

export default App;
```

Run `pnpm run dev`, manually open `http://localhost:5173/`, verify:
- "MuseumPass MA" renders in serif font, dark green
- Background is warm off-white (#F4F3EF)
- HeroUI button renders without errors
- Browser console has 0 errors

Kill dev server.

### Step 2.7: Commit

```bash
git add web/
git commit -m "feat(web): configure Tailwind v4 + HeroUI + visual tokens"
```

---

## Task 3 — Data loading + TypeScript types

### Step 3.1: Define TS types

Create `web/src/data/types.ts`:

```typescript
export interface LibraryAddress {
  street: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
}

export interface Geo {
  lat: number;
  lon: number;
}

export interface Library {
  id: string;
  name: string;
  town: string;
  network: string;
  platform: string;
  card_page: string;
  eligibility: string;
  supports_availability: boolean;
  address: LibraryAddress | null;
  geo: Geo | null;
}

export interface OriginalPrice {
  adult: number | null;
  child: number | null;
  senior: number | null;
  student: number | null;
  family: number | null;
  free_under_age: number | null;
  notes: string | null;
  source_url: string | null;
}

export interface HeroImage {
  og_image_url: string | null;
  local_path: string | null;
}

export interface Attraction {
  slug: string;
  museum_name: string;
  address: string;
  website: string;
  categories: string[];
  sources: string[];
  original_price: OriginalPrice | null;
  hero_image: HeroImage | null;
  geo: Geo | null;
}

export type PassTypeKind = 'digital' | 'physical-coupon' | 'loan-card' | 'unknown';
export type DiscountClass = 'free' | 'half' | 'percent-off' | 'dollar-off' | 'price' | 'discount' | 'unknown';

export interface Discount {
  class: DiscountClass;
  label: string;
  raw: string;
}

export interface Pass {
  library_id: string;
  attraction_slug: string;
  pass_type: PassTypeKind;
  pass_type_raw: string;
  discount: Discount;
  source_url: string;
  availability: Record<string, string> | null;
}

export interface LibrariesJson {
  _meta: { built_at: string; n_libraries: number; n_with_address: number; n_with_geo: number };
  libraries: Library[];
}

export interface AttractionsJson {
  _meta: {
    built_at: string;
    n_attractions: number;
    n_with_price: number;
    n_with_image: number;
    n_with_geo: number;
  };
  attractions: Attraction[];
}

export interface PassesJson {
  _meta: { built_at: string; n_passes: number; n_with_availability: number };
  passes: Pass[];
}
```

### Step 3.2: Create the data loader

Create `web/src/data/load.ts`:

```typescript
import librariesJson from '../../../data/structured/libraries.json';
import attractionsJson from '../../../data/structured/attractions.json';
import passesJson from '../../../data/structured/passes.json';
import type { LibrariesJson, AttractionsJson, PassesJson, Library, Attraction, Pass } from './types';

const _libraries = librariesJson as LibrariesJson;
const _attractions = attractionsJson as AttractionsJson;
const _passes = passesJson as PassesJson;

export function getLibraries(): Library[] {
  return _libraries.libraries;
}

export function getLibraryById(id: string): Library | undefined {
  return _libraries.libraries.find(l => l.id === id);
}

export function getAttractions(): Attraction[] {
  return _attractions.attractions;
}

export function getAttractionBySlug(slug: string): Attraction | undefined {
  return _attractions.attractions.find(a => a.slug === slug);
}

export function getPasses(): Pass[] {
  return _passes.passes;
}

export function getPassesForAttraction(slug: string): Pass[] {
  return _passes.passes.filter(p => p.attraction_slug === slug);
}

export function getPassesForLibrary(libId: string): Pass[] {
  return _passes.passes.filter(p => p.library_id === libId);
}
```

### Step 3.3: Enable JSON imports in tsconfig

Edit `web/tsconfig.json` `compilerOptions` — add (or verify present):

```json
"resolveJsonModule": true,
"esModuleInterop": true,
```

If `tsconfig.app.json` exists (Vite splits config in newer templates), add there too.

### Step 3.4: Test the loader

Create `web/src/data/load.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import {
  getLibraries, getLibraryById, getAttractions, getAttractionBySlug,
  getPasses, getPassesForAttraction, getPassesForLibrary,
} from './load';

describe('data loader', () => {
  it('loads ≥40 libraries', () => {
    expect(getLibraries().length).toBeGreaterThanOrEqual(40);
  });

  it('loads ≥80 attractions', () => {
    expect(getAttractions().length).toBeGreaterThanOrEqual(80);
  });

  it('loads ≥500 passes', () => {
    expect(getPasses().length).toBeGreaterThanOrEqual(500);
  });

  it('looks up library by id', () => {
    const w = getLibraryById('wakefield');
    expect(w).toBeDefined();
    expect(w!.town).toBe('Wakefield');
  });

  it('looks up attraction by slug', () => {
    const mos = getAttractionBySlug('museum-of-science');
    expect(mos).toBeDefined();
    expect(mos!.museum_name.toLowerCase()).toContain('museum of science');
  });

  it('filters passes by attraction slug', () => {
    const mosPasses = getPassesForAttraction('museum-of-science');
    expect(mosPasses.length).toBeGreaterThan(0);
  });

  it('filters passes by library id', () => {
    const wakPasses = getPassesForLibrary('wakefield');
    expect(wakPasses.length).toBeGreaterThan(0);
  });
});
```

### Step 3.5: Vitest config

Create `web/vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
  },
});
```

Add npm script in `web/package.json` under `"scripts"`:

```json
"test": "vitest run",
"test:watch": "vitest"
```

### Step 3.6: Run tests

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm test
```

Expected: 7 passed.

### Step 3.7: Commit

```bash
git add web/
git commit -m "feat(web): data loader + TS types + vitest setup"
```

---

## Task 4 — Mock auth (Zustand store + 3 hardcoded users)

### Step 4.1: Create users.json

Create `web/src/auth/users.json`:

```json
{
  "users": [
    {
      "username": "alex",
      "password": "alex",
      "displayName": "Alex",
      "persona": "heavy"
    },
    {
      "username": "rbt",
      "password": "rbt",
      "displayName": "rbt",
      "persona": "light"
    },
    {
      "username": "admin",
      "password": "admin",
      "displayName": "admin",
      "persona": "empty"
    }
  ]
}
```

### Step 4.2: Create localStorage wrappers

Create `web/src/lib/localStorage.ts`:

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
  } catch {
    // quota / privacy mode — swallow
  }
}

export function lsRemove(key: string): void {
  try {
    localStorage.removeItem(`${PREFIX}.${key}`);
  } catch {
    // swallow
  }
}
```

### Step 4.3: Create auth store

Create `web/src/auth/store.ts`:

```typescript
import { create } from 'zustand';
import users from './users.json';
import { lsGet, lsSet, lsRemove } from '../lib/localStorage';

export interface User {
  username: string;
  displayName: string;
  persona: 'heavy' | 'light' | 'empty';
}

interface AuthState {
  currentUser: User | null;
  signIn: (username: string, password: string) => { ok: true } | { ok: false; error: string };
  signOut: () => void;
  loadFromStorage: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  currentUser: null,

  signIn: (username, password) => {
    const found = users.users.find(
      u => u.username === username && u.password === password
    );
    if (!found) {
      return { ok: false, error: 'Invalid username or password' };
    }
    const user: User = {
      username: found.username,
      displayName: found.displayName,
      persona: found.persona as User['persona'],
    };
    lsSet('session', user);
    set({ currentUser: user });
    return { ok: true };
  },

  signOut: () => {
    lsRemove('session');
    set({ currentUser: null });
  },

  loadFromStorage: () => {
    const session = lsGet<User | null>('session', null);
    if (session) set({ currentUser: session });
  },
}));
```

### Step 4.4: Test the auth store

Create `web/src/auth/store.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useAuth } from './store';

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear();
    useAuth.setState({ currentUser: null });
  });

  it('rejects unknown username', () => {
    const result = useAuth.getState().signIn('nobody', 'wrong');
    expect(result.ok).toBe(false);
    expect(useAuth.getState().currentUser).toBeNull();
  });

  it('rejects wrong password', () => {
    const result = useAuth.getState().signIn('alex', 'wrong');
    expect(result.ok).toBe(false);
  });

  it('signs in alex with persona=heavy', () => {
    const result = useAuth.getState().signIn('alex', 'alex');
    expect(result.ok).toBe(true);
    const user = useAuth.getState().currentUser;
    expect(user?.username).toBe('alex');
    expect(user?.persona).toBe('heavy');
  });

  it('signs in rbt with persona=light', () => {
    useAuth.getState().signIn('rbt', 'rbt');
    expect(useAuth.getState().currentUser?.persona).toBe('light');
  });

  it('signs in admin with persona=empty', () => {
    useAuth.getState().signIn('admin', 'admin');
    expect(useAuth.getState().currentUser?.persona).toBe('empty');
  });

  it('persists session to localStorage', () => {
    useAuth.getState().signIn('alex', 'alex');
    expect(localStorage.getItem('museumpass-ma.session')).toBeTruthy();
  });

  it('loadFromStorage restores session', () => {
    useAuth.getState().signIn('alex', 'alex');
    useAuth.setState({ currentUser: null });  // simulate page reload
    useAuth.getState().loadFromStorage();
    expect(useAuth.getState().currentUser?.username).toBe('alex');
  });

  it('signOut clears state and localStorage', () => {
    useAuth.getState().signIn('alex', 'alex');
    useAuth.getState().signOut();
    expect(useAuth.getState().currentUser).toBeNull();
    expect(localStorage.getItem('museumpass-ma.session')).toBeNull();
  });
});
```

### Step 4.5: Run tests

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm test
```

Expected: 15 passed (7 from Task 3 + 8 new).

### Step 4.6: Commit

```bash
git add web/
git commit -m "feat(web): mock auth store + 3 hardcoded users + localStorage session"
```

---

## Task 5 — Routing + page stubs + TopBar + SignInModal

### Step 5.1: Add react-router config

Replace `web/src/App.tsx`:

```typescript
import { BrowserRouter, Routes, Route, Link } from 'react-router';
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
      <main className="max-w-6xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<AttractionsList />} />
          <Route path="/attractions/:slug" element={<AttractionDetail />} />
          <Route path="/settings/passes" element={<MyPasses />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;
```

### Step 5.2: TopBar component

Create `web/src/components/TopBar.tsx`:

```typescript
import { useState } from 'react';
import { Link } from 'react-router';
import { Button, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from '@heroui/react';
import { useAuth } from '../auth/store';
import { SignInModal } from './SignInModal';

export function TopBar() {
  const user = useAuth(s => s.currentUser);
  const signOut = useAuth(s => s.signOut);
  const [signInOpen, setSignInOpen] = useState(false);

  return (
    <header style={{
      borderBottom: '1px solid var(--rule)',
      background: 'var(--white)',
      padding: '12px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}>
      <Link to="/" className="font-serif" style={{ fontSize: '20px', color: 'var(--g)' }}>
        MuseumPass MA
      </Link>
      {user ? (
        <Dropdown>
          <DropdownTrigger>
            <Button variant="light" size="sm">{user.displayName}</Button>
          </DropdownTrigger>
          <DropdownMenu aria-label="user menu">
            <DropdownItem key="passes" href="/settings/passes">My passes</DropdownItem>
            <DropdownItem key="signout" onClick={signOut} className="text-danger">
              Sign out
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>
      ) : (
        <Button size="sm" color="primary" onClick={() => setSignInOpen(true)}>
          Sign in
        </Button>
      )}
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
    </header>
  );
}
```

### Step 5.3: SignInModal component

Create `web/src/components/SignInModal.tsx`:

```typescript
import { useState } from 'react';
import {
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter,
  Button, Input,
} from '@heroui/react';
import { useAuth } from '../auth/store';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function SignInModal({ isOpen, onClose }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const signIn = useAuth(s => s.signIn);

  const handleSubmit = () => {
    const result = signIn(username, password);
    if (result.ok) {
      setUsername('');
      setPassword('');
      setError(null);
      onClose();
    } else {
      setError(result.error);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalContent>
        <ModalHeader>Sign in to MuseumPass MA</ModalHeader>
        <ModalBody>
          {error && <p style={{ color: 'var(--rd)' }}>{error}</p>}
          <Input
            label="Username"
            value={username}
            onValueChange={setUsername}
            autoFocus
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onValueChange={setPassword}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
          />
          <p style={{ fontSize: '11px', color: 'var(--ink-3)' }}>
            Demo accounts: alex / rbt / admin (password = username)
          </p>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={onClose}>Cancel</Button>
          <Button color="primary" onClick={handleSubmit}>Sign in</Button>
          <Button disabled title="Sign-up coming soon">Sign up</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
```

### Step 5.4: Page stubs

Create each stub file. Each one is a minimal placeholder that proves routing + data loading work.

`web/src/pages/AttractionsList.tsx`:

```typescript
import { getAttractions } from '../data/load';

export function AttractionsList() {
  const attractions = getAttractions();
  return (
    <div>
      <h1 className="font-serif" style={{ fontSize: '24px', marginBottom: '12px' }}>
        Attractions
      </h1>
      <p style={{ color: 'var(--ink-3)', marginBottom: '12px' }}>
        Loaded {attractions.length} attractions. (List UI lands in plan-4.)
      </p>
      <ul>
        {attractions.slice(0, 10).map(a => (
          <li key={a.slug} style={{ padding: '4px 0' }}>
            <a href={`/attractions/${a.slug}`} style={{ color: 'var(--g)' }}>
              {a.museum_name}
            </a>
            <span style={{ color: 'var(--ink-3)', marginLeft: '8px' }}>
              · {a.sources.length} libraries
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

`web/src/pages/AttractionDetail.tsx`:

```typescript
import { useParams } from 'react-router';
import { getAttractionBySlug, getPassesForAttraction } from '../data/load';

export function AttractionDetail() {
  const { slug } = useParams<{ slug: string }>();
  if (!slug) return <p>Missing slug.</p>;
  const attraction = getAttractionBySlug(slug);
  if (!attraction) return <p>Attraction "{slug}" not found.</p>;
  const passes = getPassesForAttraction(slug);

  return (
    <div>
      <h1 className="font-serif" style={{ fontSize: '24px', marginBottom: '8px' }}>
        {attraction.museum_name}
      </h1>
      <p style={{ color: 'var(--ink-3)', marginBottom: '12px' }}>
        {attraction.address} · {passes.length} passes available
      </p>
      <pre style={{
        background: 'var(--paper)', padding: '12px', fontSize: '11px',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      }}>
        {JSON.stringify(attraction, null, 2)}
      </pre>
    </div>
  );
}
```

`web/src/pages/MyPasses.tsx`:

```typescript
import { useAuth } from '../auth/store';
import { getLibraries } from '../data/load';

export function MyPasses() {
  const user = useAuth(s => s.currentUser);
  if (!user) {
    return <p>Sign in to manage your passes.</p>;
  }
  return (
    <div>
      <h1 className="font-serif" style={{ fontSize: '24px', marginBottom: '8px' }}>
        My passes
      </h1>
      <p style={{ color: 'var(--ink-3)' }}>
        Signed in as <b>{user.displayName}</b> ({user.persona}).
        Full settings UI lands in plan-4.
      </p>
      <p style={{ color: 'var(--ink-3)', fontSize: '11px', marginTop: '8px' }}>
        {getLibraries().length} libraries available.
      </p>
    </div>
  );
}
```

`web/src/pages/NotFound.tsx`:

```typescript
export function NotFound() {
  return (
    <div>
      <h1 className="font-serif" style={{ fontSize: '24px' }}>404</h1>
      <p style={{ color: 'var(--ink-3)' }}>This page doesn't exist.</p>
    </div>
  );
}
```

### Step 5.5: Dev server visual smoke test

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm run dev
```

Manually open http://localhost:5173/ and verify:
- Top bar shows "MuseumPass MA" + "Sign in" button
- Main page lists 10 attractions with names
- Click an attraction link → goes to `/attractions/<slug>` → shows JSON
- Click "Sign in" → modal opens → enter `alex` / `alex` → modal closes, top bar shows "Alex" dropdown
- Dropdown → "My passes" → goes to `/settings/passes` page
- Dropdown → "Sign out" → top bar goes back to "Sign in"
- 0 console errors

Kill dev server.

### Step 5.6: Commit

```bash
git add web/
git commit -m "feat(web): routing + page stubs + TopBar + SignInModal"
```

---

## Task 6 — Static image symlink/copy + final verification

### Step 6.1: Symlink hero images into public/

PowerShell on Windows can create directory junctions (admin not required if `developer mode` is enabled), but it's safer to just copy:

```bash
cd "F:/pj/NorthShore Kids Events/web/public"
# Create images/ and placeholders/ symlinks (Windows: use mklink /D from cmd, or fall back to copy)
```

Actually for cross-platform simplicity, just copy:

```powershell
cd "F:/pj/NorthShore Kids Events/web/public"
robocopy "..\..\data\static\images" "images" /MIR /NFL /NDL /NJH /NJS /NC /NS
robocopy "..\..\data\static\placeholders" "placeholders" /MIR /NFL /NDL /NJH /NJS /NC /NS
```

(`/MIR` mirrors recursively. The `/NFL /NDL /...` flags suppress per-file logging.)

After: confirm `web/public/images/` has ~47 files and `web/public/placeholders/` has 9 SVGs.

### Step 6.2: Add a small script for re-copy

Append to `web/package.json` scripts:

```json
"copy:assets": "powershell -Command \"robocopy '../data/static/images' 'public/images' /MIR /NFL /NDL /NJH /NJS /NC /NS; robocopy '../data/static/placeholders' 'public/placeholders' /MIR /NFL /NDL /NJH /NJS /NC /NS; exit 0\""
```

(robocopy's exit code is non-zero on success; `exit 0` swallows it.)

### Step 6.3: Final dev server check

Restart `pnpm run dev`. Verify:
- Open http://localhost:5173/placeholders/family.svg directly — should render the SVG
- Open http://localhost:5173/images/<a real slug>.jpg if any exists

### Step 6.4: Run all tests

```bash
cd "F:/pj/NorthShore Kids Events/web"
pnpm test
```

Expected: 15 passed.

Also run Python tests from repo root:
```bash
cd "F:/pj/NorthShore Kids Events"
python -m pytest tests/ 2>&1 | tail -3
```

Expected: still 114 passed.

### Step 6.5: Commit

```bash
git add web/package.json web/public/.gitkeep
git commit -m "feat(web): asset copy script for hero images + placeholders"
```

(Note: actual binary images in `web/public/images/` are gitignored.)

### Step 6.6: Update CLAUDE.md

Append to Repository Layout under root:

```
├── web/                       # 前端 (React + Vite + TS + HeroUI),plan-3 scaffold,plan-4 实现 UI
│   ├── src/{pages,components,data,auth,lib,styles}/
│   └── public/{images,placeholders}/   # 拷贝自 data/static/(gitignored 二进制)
```

And in `How to Run`:

```bash
# Frontend dev server
cd web && pnpm install && pnpm run dev
```

Commit:
```bash
git add CLAUDE.md
git commit -m "docs: reflect plan-3 web/ scaffold in repo layout"
```

---

## Verification Summary

After all 6 tasks:

| Artifact | Result |
|---|---|
| `web/` Vite project | ✅ scaffolded with React 19 + TS |
| HeroUI + Tailwind v4 wired | ✅ token CSS variables active |
| 3 JSON files imported as typed objects | ✅ ~50 libs / ~104 attrs / ~962 passes |
| Mock auth | ✅ 3 hardcoded users, localStorage session |
| Routes | ✅ `/`, `/attractions/:slug`, `/settings/passes`, 404 |
| TopBar + SignInModal | ✅ functional |
| Page stubs | ✅ data loads, routing works |
| Hero image / placeholder assets served | ✅ via public/ |
| Tests | ✅ 15 frontend (Vitest) + 114 backend (pytest) |
| Commits | ~6-7 new |

After this, plan-4 (frontend features: real list page UI + tag algorithm + detail page + my passes setup) can begin.
