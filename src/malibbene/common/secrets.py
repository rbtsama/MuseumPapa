"""Load owned-card barcodes from the repo-root ``.env`` file.

``.env`` format is plain ``KEY=VALUE`` per line, ``#`` for comments. No
third-party dependency (no python-dotenv). Card barcodes are read on demand —
scrapers don't need them, only the booking-helper layer does.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = REPO_ROOT / ".env"


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def owned_cards() -> dict[str, str]:
    """Return ``{library_id: barcode}`` for cards declared in ``.env``."""
    env = load_env()
    out: dict[str, str] = {}
    for k, v in env.items():
        if k.endswith("_BARCODE") and v:
            lib_id = k[: -len("_BARCODE")].lower().replace("_", "-")
            out[lib_id] = v
    return out
