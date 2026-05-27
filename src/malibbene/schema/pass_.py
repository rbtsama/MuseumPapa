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
    # Verbatim policy text for a periodic booking cap (e.g. "1 booking per
    # month"). Only some popular/expensive museums set one, but it's important
    # — surfaced to the user as a warning. None when not stated.
    booking_frequency_limit: Optional[str] = None
    # Verbatim late-return penalty text for circulating (Pik&Rtn) passes
    # (e.g. "$5/day late fee"). None when not stated. The UI also shows a
    # blanket "check return policy" reminder for ALL physical_circ passes
    # regardless of this field (we can't compute the user's pickup/return dates).
    late_return_penalty: Optional[str] = None


class ResidencyRestricted(str, Enum):
    YES = "yes"          # confirmed resident-restricted (text or booking probe)
    NO = "no"            # confirmed open to non-residents
    UNKNOWN = "unknown"  # not stated in catalog text and not yet probed


class ResidencyScope(str, Enum):
    TOWN = "town"        # only residents of the issuing library's town (match home ZIP vs library.resident_zips)
    MA = "ma"            # any Massachusetts resident (match home ZIP vs MA ZIP set)


@dataclass
class ResidencyRestriction:
    """Whether a (library x attraction) pass may only be reserved by residents.

    This is the REAL booking filter (the platform enforces it at reservation
    time against the ZIP recorded on the card — see docs). It is mostly NOT
    written in catalog benefit text, so ``restricted`` defaults to ``unknown``
    and is filled either from an explicit textual statement or from an empirical
    booking probe.
    """
    restricted: ResidencyRestricted = ResidencyRestricted.UNKNOWN
    scope: Optional[ResidencyScope] = None      # only meaningful when restricted == yes
    source: Optional[str] = None                 # "catalog_text" | "booking_probe"
    evidence: Optional[str] = None               # verbatim phrase, or probe result detail


class BookingAccessVerdict(str, Enum):
    OWN_CARD_ONLY = "own_card_only"
    NETWORK_OPEN = "network_open"
    AMBIGUOUS = "ambiguous"
    NOT_VERIFIED = "not_verified"


@dataclass
class BookingAccessProbe:
    verdict: BookingAccessVerdict = BookingAccessVerdict.NOT_VERIFIED
    source: Optional[str] = None
    evidence: Optional[str] = None
    prober_card: Optional[str] = None
    probed_date: Optional[str] = None

@dataclass
class Pass:
    library_id: str
    attraction_slug: str
    pass_form: PassForm
    coupon: Optional[Coupon] = None
    available_at_branches: Union[str, list[str]] = "all"
    eligibility_override: Optional[EligibilityOverride] = None
    restrictions: Optional[Restrictions] = None
    residency_restriction: Optional[ResidencyRestriction] = None
    # True when this library's OWN card is required to book (a same-network
    # sibling card is rejected at card-validation). Card-ownership, NOT residency
    # — the card is obtainable by any MA resident. From the booking probe.
    requires_own_card: bool = False
    own_card_evidence: Optional[str] = None
    booking_access_probe: Optional[BookingAccessProbe] = None
    source_url: Optional[str] = None
