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
    target: str
    status: AuditStatus
    corrected_value: Optional[Any] = None
    note: Optional[str] = None
    audited_at: Optional[datetime] = None
    audited_by: Optional[str] = None
