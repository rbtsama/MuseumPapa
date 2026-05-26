from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from .library import Geo, Address

class ReservationRequired(str, Enum):
    NONE = "none"
    TIMED_ENTRY = "timed_entry"
    WALK_IN_OK = "walk_in_ok"

class PassHolderPath(str, Enum):
    PROMO_CODE = "promo_code_in_general_checkout"
    DEDICATED_SKU = "dedicated_pass_sku"
    DEDICATED_URL = "dedicated_pass_holders_url"
    LIBRARY_ONLY = "library_only"
    UNKNOWN = "unknown"

class VisitorResidency(str, Enum):
    MA_RESIDENT = "ma_resident"
    TOWN_RESIDENT = "town_resident"
    NONE = "none"
    UNKNOWN = "unknown"

@dataclass
class VisitorEligibility:
    residency: VisitorResidency
    scope: Optional[str] = None
    locals_free: bool = False
    note: Optional[str] = None
    source_phrase: Optional[str] = None

@dataclass
class Reservation:
    required: ReservationRequired
    booking_url: Optional[str] = None
    lead_time_hours: Optional[int] = None
    pass_holder_path: PassHolderPath = PassHolderPath.UNKNOWN
    pass_holder_url: Optional[str] = None
    notes: Optional[str] = None
    source_phrase: Optional[str] = None

@dataclass
class AudiencePrice:
    audience: str
    price: Optional[float] = None
    age_range: Optional[dict] = None
    source_phrase: Optional[str] = None

@dataclass
class Attraction:
    slug: str
    name: str
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None
    geo: Optional[Geo] = None
    description: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    hero_image: Optional[str] = None
    hours: Optional[dict] = None
    # Weekly recurring closures derived from `hours` (e.g. ["monday","tuesday"]).
    # Recurring only — not holiday/seasonal closures.
    closed_days: list[str] = field(default_factory=list)
    prices: list[AudiencePrice] = field(default_factory=list)
    visitor_eligibility: Optional[VisitorEligibility] = None
    reservation: Optional[Reservation] = None
    # How a LIBRARY-PASS holder redeems (distinct from museum-wide reservation):
    # "promo_code" = library issues a code, patron books on the museum's own
    # site; "timed_entry"; "walk_in". booking_note is a one-sentence patron
    # instruction. Populated via overrides from verified per-museum research.
    booking_model: Optional[str] = None
    booking_note: Optional[str] = None
    sources: list[str] = field(default_factory=list)
