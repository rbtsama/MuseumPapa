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
    prices: list[AudiencePrice] = field(default_factory=list)
    visitor_eligibility: Optional[VisitorEligibility] = None
    reservation: Optional[Reservation] = None
    sources: list[str] = field(default_factory=list)
