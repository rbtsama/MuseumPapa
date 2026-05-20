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
