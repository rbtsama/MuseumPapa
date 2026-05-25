# Admin Panel v2 — Plan 1: Persistence Foundation + Build Round-Trip

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single shared `data/overrides/audit_overrides.json` store the admin panel reads/writes (locally via `serve_admin.py`, on Vercel via a serverless function) that round-trips into the Python build — including fixing the pass slug mismatch so pass corrections actually apply.

**Architecture:** Extend the existing `audit_overrides.py` to (a) load a consolidated `{target: record}` file in addition to the legacy directory tree, and (b) expose a pure `merge_override`/`remove_override` upsert helper used by both writers. A local `scripts/serve_admin.py` hosts the static panel + repo data and exposes `/api/overrides` (GET list / POST upsert). A Vercel `api/overrides.js` serverless function does the same against the GitHub Contents API using a server-side token. The build's `passes.py` emits `attraction_rawslug` so panel-written pass overrides key correctly.

**Tech Stack:** Python 3.11+ (stdlib `http.server`, `pytest>=7`), Node serverless (Vercel default runtime), GitHub Contents API.

This plan covers spec sections 8.3 (record shape via loader), 9 (persistence), and 10 (pass slug fix). The UI (spec §3–8) is Plans 2 and 3.

---

### Task 1: Consolidated overrides loader

The panel writes one `data/overrides/audit_overrides.json` file shaped `{ "<target>": {record}, ... }`. `load_overrides` must read it on top of the legacy per-field directory tree (consolidated file wins on conflict), so the build picks up panel edits with no other change.

**Files:**
- Modify: `src/malibbene/common/audit_overrides.py`
- Test: `tests/test_audit_overrides.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_audit_overrides.py`:

```python
def test_load_overrides_reads_consolidated_file(tmp_path):
    # legacy dir-tree record
    _write(tmp_path / "libraries/wakefield/card_eligibility.json",
           {"status":"corrected","corrected_value":"ma_resident"})
    # consolidated file the panel writes
    (tmp_path / "audit_overrides.json").write_text(json.dumps({
        "attraction:mfa:visitor_eligibility": {
            "target":"attraction:mfa:visitor_eligibility","kind":"attraction",
            "id":"mfa","field":"visitor_eligibility","status":"corrected",
            "corrected_value":{"residency":"ma_resident"},
            "correction_kind":"value_wrong","root_cause":"extraction_error",
            "note":"","audited_at":"2026-05-25T00:00:00Z"},
    }))
    by_target = load_overrides(tmp_path)
    assert "library:wakefield:card_eligibility" in by_target          # dir tree still works
    assert "attraction:mfa:visitor_eligibility" in by_target          # consolidated loaded
    assert by_target["attraction:mfa:visitor_eligibility"]["corrected_value"] == {"residency":"ma_resident"}

def test_consolidated_file_wins_over_dir_tree(tmp_path):
    _write(tmp_path / "libraries/wakefield/card_eligibility.json",
           {"status":"corrected","corrected_value":"town_resident"})
    (tmp_path / "audit_overrides.json").write_text(json.dumps({
        "library:wakefield:card_eligibility": {
            "status":"corrected","corrected_value":"ma_resident"},
    }))
    by_target = load_overrides(tmp_path)
    assert by_target["library:wakefield:card_eligibility"]["corrected_value"] == "ma_resident"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_audit_overrides.py::test_load_overrides_reads_consolidated_file tests/test_audit_overrides.py::test_consolidated_file_wins_over_dir_tree -v`
Expected: FAIL — the consolidated key is missing from `by_target` (loader ignores the top-level file).

- [ ] **Step 3: Write minimal implementation**

In `src/malibbene/common/audit_overrides.py`, add a module constant and extend `load_overrides` just before its `return by_target`:

```python
CONSOLIDATED_FILE = "audit_overrides.json"
```

```python
    # Consolidated file written by the admin panel ({target: record}); overlays
    # (wins over) the legacy per-field directory tree above.
    consolidated = overrides_root / CONSOLIDATED_FILE
    if consolidated.exists():
        for target, record in json.loads(consolidated.read_text()).items():
            by_target[target] = record
    return by_target
```

(Remove the old bare `return by_target` so the consolidated block runs first.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_audit_overrides.py -v`
Expected: PASS (all tests, including the 3 pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add src/malibbene/common/audit_overrides.py tests/test_audit_overrides.py
git commit -m "build: load consolidated audit_overrides.json on top of dir tree"
```

---

### Task 2: Pure upsert/remove helpers for writers

Both writers (local server, Vercel function) need identical logic: read the store, upsert or remove one record by its `target`, write it back. Extract the merge as a pure, tested function so the HTTP wrappers stay thin.

**Files:**
- Modify: `src/malibbene/common/audit_overrides.py`
- Test: `tests/test_audit_overrides.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_audit_overrides.py`:

```python
from malibbene.common.audit_overrides import merge_override, remove_override

def test_merge_override_upserts_by_target():
    store = {}
    rec = {"target":"library:x:card_eligibility","status":"corrected","corrected_value":"none"}
    merge_override(store, rec)
    assert store["library:x:card_eligibility"]["corrected_value"] == "none"
    # second write to same target replaces
    merge_override(store, {"target":"library:x:card_eligibility","status":"verified_ok"})
    assert store["library:x:card_eligibility"]["status"] == "verified_ok"

def test_merge_override_requires_target():
    import pytest
    with pytest.raises(ValueError):
        merge_override({}, {"status":"corrected"})

def test_remove_override_deletes_target():
    store = {"library:x:f": {"target":"library:x:f","status":"noted"}}
    remove_override(store, "library:x:f")
    assert "library:x:f" not in store
    remove_override(store, "missing:y:z")  # no error on missing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_audit_overrides.py -k "merge_override or remove_override" -v`
Expected: FAIL — `ImportError: cannot import name 'merge_override'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/malibbene/common/audit_overrides.py`:

```python
def merge_override(store: dict[str, dict], record: dict) -> dict[str, dict]:
    """Upsert one audit record into a {target: record} store. Mutates and returns store."""
    target = record.get("target")
    if not target:
        raise ValueError("override record missing 'target'")
    store[target] = record
    return store

def remove_override(store: dict[str, dict], target: str) -> dict[str, dict]:
    """Remove a record by target. No-op if absent. Mutates and returns store."""
    store.pop(target, None)
    return store
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_audit_overrides.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/malibbene/common/audit_overrides.py tests/test_audit_overrides.py
git commit -m "build: add merge_override/remove_override store helpers"
```

---

### Task 3: Pass slug round-trip fix

The build keys pass overrides as `pass:{lib}__{rawslug}` (passes.py:84-85) but emits only `attraction_slug=canonical(rawslug)` (passes.py:29). The panel only sees the canonical slug, so its override targets never match. Fix: emit `attraction_rawslug` in each row so the panel keys overrides with the exact value the build uses.

**Files:**
- Modify: `src/malibbene/build/passes.py:30-46` (the `row = {...}` dict)
- Test: `tests/test_build_passes_v2.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_build_passes_v2.py`:

```python
def test_build_passes_emits_rawslug_and_applies_pass_override(tmp_path):
    from malibbene.build.slug_canonical import canonical
    raw = tmp_path/"raw"
    # a suffixed catalog slug whose canonical form differs — the bug case
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"mfa-promo-code","title":"MFA"}]})
    # override keyed by the RAW slug (what the build uses), correcting pass_form
    _w(tmp_path/"overrides/passes/wakefield__mfa-promo-code/pass_form.json",
       {"status":"corrected","corrected_value":"digital_email"})

    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]

    assert p["attraction_slug"] == canonical("mfa-promo-code")  # canonical join key
    assert p["attraction_rawslug"] == "mfa-promo-code"          # NEW: panel keys overrides with this
    assert p["pass_form"] == "digital_email"                    # override actually applied
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_build_passes_v2.py::test_build_passes_emits_rawslug_and_applies_pass_override -v`
Expected: FAIL — `KeyError: 'attraction_rawslug'` (field not emitted).

- [ ] **Step 3: Write minimal implementation**

In `src/malibbene/build/passes.py`, add one line to the `row` dict (right after the `attraction_slug` line, ~line 31):

```python
                row = {
                    "library_id": lib, "attraction_slug": slug,
                    "attraction_rawslug": rawslug,  # build's override key; panel uses this for pass targets
                    "pass_form": "physical_coupon",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_build_passes_v2.py -v`
Expected: PASS (new test + the pre-existing one).

- [ ] **Step 5: Commit**

```bash
git add src/malibbene/build/passes.py tests/test_build_passes_v2.py
git commit -m "build: emit attraction_rawslug so panel pass overrides round-trip"
```

---

### Task 4: Local dev server (`serve_admin.py`)

Host the repo root statically (so `/admin/panel.html`, `/data/structured/*.json`, `/data/overrides/audit_overrides.json` all resolve) and expose `/api/overrides`: GET returns the store, POST upserts one record (or removes when the body is `{"revoke": "<target>"}`). Writes go straight to `data/overrides/audit_overrides.json` via the Task 2 helpers — so local audits persist across refresh.

**Files:**
- Create: `scripts/serve_admin.py`

- [ ] **Step 1: Write the server**

Create `scripts/serve_admin.py`:

```python
"""Local admin-panel host + audit write endpoint.

Run:  python scripts/serve_admin.py            (serves repo root on :8000)
Open: http://localhost:8000/admin/panel.html

GET  /api/overrides            -> {target: record, ...}
POST /api/overrides  {record}  -> upsert one record (must include "target")
POST /api/overrides  {"revoke": target} -> remove a record
All writes land in data/overrides/audit_overrides.json.
"""
from __future__ import annotations
import json, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORE = REPO / "data" / "overrides" / "audit_overrides.json"
sys.path.insert(0, str(REPO / "src"))
from malibbene.common.audit_overrides import merge_override, remove_override  # noqa: E402

def _load() -> dict:
    return json.loads(STORE.read_text()) if STORE.exists() else {}

def _save(store: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, indent=2, ensure_ascii=False))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(REPO), **k)

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/overrides":
            return self._json(200, _load())
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/overrides":
            return self._json(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})
        store = _load()
        if "revoke" in payload:
            remove_override(store, payload["revoke"])
        else:
            try:
                merge_override(store, payload)
            except ValueError as e:
                return self._json(400, {"error": str(e)})
        _save(store)
        return self._json(200, store)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"admin panel: http://localhost:{port}/admin/panel.html")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
```

- [ ] **Step 2: Verify manually (no unit test — thin HTTP wrapper over Task 2 helpers)**

Start it in the background, then exercise the API:

```bash
python scripts/serve_admin.py 8000 &
sleep 1
# upsert
curl -s -X POST http://localhost:8000/api/overrides \
  -H 'Content-Type: application/json' \
  -d '{"target":"library:wakefield:card_eligibility","kind":"library","id":"wakefield","field":"card_eligibility","status":"corrected","corrected_value":"ma_resident","audited_at":"2026-05-25T00:00:00Z"}'
# read back
curl -s http://localhost:8000/api/overrides
# static still served
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/admin/panel.html
```

Expected: POST and GET both return the store JSON containing `library:wakefield:card_eligibility`; the panel HTML returns `200`; `data/overrides/audit_overrides.json` now exists with that record. Stop the server (`kill %1`).

- [ ] **Step 3: Confirm the write round-trips into the build**

Run: `python -m pytest tests/test_audit_overrides.py -v` (the consolidated loader from Task 1 reads exactly the file `serve_admin.py` just wrote).
Expected: PASS. Then delete the scratch record so it isn't committed: remove `data/overrides/audit_overrides.json` if it only holds the curl test record.

- [ ] **Step 4: Commit**

```bash
git add scripts/serve_admin.py
git commit -m "admin: local dev server with /api/overrides write endpoint"
```

---

### Task 5: Vercel serverless write (`api/overrides.js`)

On Vercel the panel hits the same `/api/overrides` contract, but reads/writes the file on GitHub via the Contents API using a server-side token. This lets a remote auditor edit on the deployed platform with no token of their own; edits commit to `data/overrides/audit_overrides.json` in the repo (the shared source of truth).

**Files:**
- Create: `api/overrides.js`
- Modify: `web/vercel.json` (or create `vercel.json` at repo root if the admin panel deploys from root — see Step 4)

**Env vars (set in Vercel project settings → Environment Variables):**
- `GITHUB_TOKEN` — a fine-grained PAT with Contents read/write on this repo
- `GITHUB_REPO` — e.g. `rbtsama/MuseumPapa`
- `GITHUB_BRANCH` — e.g. `main`

- [ ] **Step 1: Write the serverless function**

Create `api/overrides.js`:

```js
// Vercel serverless: shared audit store backed by a GitHub file.
// GET  /api/overrides            -> {target: record, ...}
// POST /api/overrides {record}   -> upsert one (must include "target")
// POST /api/overrides {"revoke": target} -> remove one
const FILE = "data/overrides/audit_overrides.json";

function ghHeaders() {
  return {
    Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "museumpapa-admin",
  };
}
function api(path) {
  return `https://api.github.com/repos/${process.env.GITHUB_REPO}/contents/${path}`;
}

async function readFile() {
  const ref = process.env.GITHUB_BRANCH || "main";
  const res = await fetch(`${api(FILE)}?ref=${ref}`, { headers: ghHeaders() });
  if (res.status === 404) return { store: {}, sha: undefined };
  if (!res.ok) throw new Error(`github read ${res.status}`);
  const json = await res.json();
  const store = JSON.parse(Buffer.from(json.content, "base64").toString("utf-8"));
  return { store, sha: json.sha };
}

async function writeFile(store, sha) {
  const body = {
    message: "admin: audit override update",
    content: Buffer.from(JSON.stringify(store, null, 2)).toString("base64"),
    branch: process.env.GITHUB_BRANCH || "main",
    ...(sha ? { sha } : {}),
  };
  const res = await fetch(api(FILE), {
    method: "PUT", headers: ghHeaders(), body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`github write ${res.status}`);
}

export default async function handler(req, res) {
  try {
    if (req.method === "GET") {
      const { store } = await readFile();
      return res.status(200).json(store);
    }
    if (req.method === "POST") {
      const payload = typeof req.body === "string" ? JSON.parse(req.body) : req.body || {};
      const { store, sha } = await readFile();
      if ("revoke" in payload) {
        delete store[payload.revoke];
      } else if (payload.target) {
        store[payload.target] = payload;
      } else {
        return res.status(400).json({ error: "record missing 'target'" });
      }
      await writeFile(store, sha);
      return res.status(200).json(store);
    }
    return res.status(405).json({ error: "method not allowed" });
  } catch (e) {
    return res.status(500).json({ error: String(e.message || e) });
  }
}
```

- [ ] **Step 2: Decide deploy root and wire config**

The admin panel currently lives at repo-root `admin/`, while the consumer app deploys from `web/`. Vercel serverless functions in `api/` deploy from the **project root**. Confirm the admin panel's Vercel project uses the **repo root** as its root directory (so both `/admin/*` static files and `/api/overrides` resolve). Create `vercel.json` at repo root:

```json
{
  "buildCommand": null,
  "outputDirectory": ".",
  "rewrites": [{ "source": "/", "destination": "/admin/panel.html" }]
}
```

(If the admin panel instead deploys from a subdirectory, move `api/overrides.js` under that subdirectory's root and adjust `GITHUB_REPO` paths accordingly. Document the chosen root in the commit message.)

- [ ] **Step 3: Verify on a Vercel preview deploy**

Push to a branch, open the Vercel preview URL, then:

```bash
curl -s https://<preview-url>/api/overrides
curl -s -X POST https://<preview-url>/api/overrides \
  -H 'Content-Type: application/json' \
  -d '{"target":"library:test:card_eligibility","status":"noted","note":"deploy check","audited_at":"2026-05-25T00:00:00Z"}'
```

Expected: GET returns `{}` (or current store); POST returns the store including `library:test:card_eligibility`, and a new commit appears on the configured branch updating `data/overrides/audit_overrides.json`. Then revoke it: `-d '{"revoke":"library:test:card_eligibility"}'` and confirm it's gone.

- [ ] **Step 4: Commit**

```bash
git add api/overrides.js vercel.json
git commit -m "admin: Vercel serverless /api/overrides backed by GitHub file"
```

---

### Task 6: Full-suite green + plan-1 wrap

**Files:** none (verification only)

- [ ] **Step 1: Run the whole Python suite**

Run: `python -m pytest -q`
Expected: all pass (no regressions in the build/override tests).

- [ ] **Step 2: Confirm no scratch artifacts staged**

Run: `git status`
Expected: clean working tree; `data/overrides/audit_overrides.json` is NOT committed with scratch/test records (it will be created for real by the panel in Plans 2–3). If it holds only test records, delete it.

---

## Self-Review

**1. Spec coverage (this plan's scope = spec §8.3 record-shape load, §9 persistence, §10 slug fix):**
- §9 single-file store + read on load → Task 1 (loader) + Tasks 4/5 (GET endpoints). ✓
- §9 local write → Task 4 (`serve_admin.py` POST). ✓
- §9 Vercel serverless + token env → Task 5. ✓
- §9 build consumes the file → Task 1 (loader overlay; build's `load_overrides` call unchanged). ✓
- §8.3 record shape (correction_kind/root_cause/no audited_by) → loaded verbatim by Task 1; `apply_overrides` ignores the extra fields (only reads status + corrected_value), so no schema change needed. ✓
- §10 pass slug round-trip → Task 3. ✓
- UI sections §3–8 (matrix, filters, toggles, cards, audit UI, ⓘ) → **deferred to Plans 2 & 3** (out of scope here). Noted in header.

**2. Placeholder scan:** No TBD/TODO; every code step has complete code; manual-verify steps (4-5) give exact curl commands + expected output. Task 5 Step 2 leaves the deploy-root choice conditional, but states the default and the exact alternative — not a placeholder.

**3. Type consistency:** `merge_override(store, record)` / `remove_override(store, target)` signatures match between Task 2 (definition), Task 4 (`serve_admin.py` import), and the Task 5 JS reimplementation (`store[payload.target] = payload` / `delete store[payload.revoke]`). The `/api/overrides` contract (GET→store, POST record/`{revoke}`→store) is identical across Tasks 4 and 5. Override target format `kind:id:field` matches the existing `load_overrides`/`apply_overrides` convention. ✓
