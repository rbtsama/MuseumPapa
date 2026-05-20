from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union
from .library import PassPickupPolicy

class PassForm(str, Enum):
    DIGITAL_EMAIL = "digital_email"
    PHYSICAL_CIRC = "physical_circ"
    PHYSICAL_COUPON = "physical_coupon"

class CapacityKind(str, Enum):
    PEOPLE = "people"
    VEHICLE = "vehicle"
    TICKET = "ticket"
    UNSPECIFIED = "unspecified"

class CouponForm(str, Enum):
    FREE = "free"
    PERCENT_OFF = "percent-off"
    DOLLAR_OFF = "dollar-off"
    PER_PERSON_PRICE = "per-person-price"
    BOGO = "bogo"
    DISCOUNT = "discount"

@dataclass
class Capacity:
    kind: CapacityKind
    n: Optional[int] = None

@dataclass
class AudiencePolicy:
    audience: str
    form: CouponForm
    value: Optional[float] = None
    age_range: Optional[dict] = None
    count: Optional[int] = None
    source_phrase: Optional[str] = None

@dataclass
class Coupon:
    capacity: Capacity
    audience_policies: list[AudiencePolicy]
    summary: Optional[str] = None
    source_phrase_block: Optional[str] = None

@dataclass
class EligibilityOverride:
    residency: PassPickupPolicy
    reason: Optional[str] = None
    source_phrase: Optional[str] = None

@dataclass
class Restrictions:
    blackout: list[dict] = field(default_factory=list)
    blackout_recurring: list[str] = field(default_factory=list)
    weekdays_only: bool = False
    seasonal: Optional[dict] = None
    advance_booking_required: bool = False
    advance_booking_hours: Optional[int] = None

@dataclass
class Pass:
    library_id: str
    attraction_slug: str
    pass_form: PassForm
    coupon: Optional[Coupon] = None
    available_at_branches: Union[str, list[str]] = "all"
    eligibility_override: Optional[EligibilityOverride] = None
    restrictions: Optional[Restrictions] = None
    source_url: Optional[str] = None
