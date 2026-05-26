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

def _env_cards() -> dict:
    """Read <LIB>_BARCODE keys from .env -> {library_id: barcode}.

    Local source of truth for card numbers (sensitive). .env is gitignored;
    these values stay on this machine. Key WAKEFIELD_BARCODE -> lib 'wakefield'.
    """
    env = REPO / ".env"
    out: dict[str, str] = {}
    if not env.exists():
        return out
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k.endswith("_BARCODE"):
            v = v.strip().strip('"').strip("'")
            if v:
                out[k[:-len("_BARCODE")].lower()] = v
    return out

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
        path = self.path.split("?")[0]
        if path == "/api/overrides":
            return self._json(200, _load())
        if path == "/api/cards":
            return self._json(200, _env_cards())
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
