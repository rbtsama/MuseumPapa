"""Per-record status wrapper used across all scrapers.

A scraper output always carries `meta.status_summary` at the top so downstream
code can distinguish "we tried but failed" from "no record exists" — see BRD §8.2
('抓取失败状态记录').
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


OK = "ok"
EMPTY = "empty"


def failed(reason: str) -> str:
    return f"failed:{reason}"


def is_failed(status: str) -> bool:
    return status.startswith("failed:")


@dataclass
class StatusSummary:
    ok: int = 0
    empty: int = 0
    failed: dict[str, int] = field(default_factory=dict)

    def add(self, status: str) -> None:
        if status == OK:
            self.ok += 1
        elif status == EMPTY:
            self.empty += 1
        elif is_failed(status):
            reason = status.split(":", 1)[1]
            self.failed[reason] = self.failed.get(reason, 0) + 1

    @property
    def total(self) -> int:
        return self.ok + self.empty + sum(self.failed.values())

    @property
    def ok_ratio(self) -> float:
        return self.ok / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "empty": self.empty,
            "failed": self.failed,
            "total": self.total,
            "ok_ratio": round(self.ok_ratio, 3),
        }
