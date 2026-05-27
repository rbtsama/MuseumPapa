from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class CardEligibility(str, Enum):
    MA_RESIDENT = "ma_resident"
    TOWN_RESIDENT = "town_resident"
    TOWN_OR_WORKS = "town_or_works"
    NETWORK = "network"
    NONE = "none"
    UNKNOWN = "unknown"

class PassPickupPolicy(str, Enum):
    SAME_AS_CARD = "same_as_card"
    MA_RESIDENT = "ma_resident"
    TOWN_RESIDENT = "town_resident"
    TOWN_CARDHOLDER_ONLY = "town_cardholder_only"
    NETWORK = "network"
    WALKIN_FOR_NONRESIDENTS = "walkin_for_nonresidents"
    NONE = "none"
    UNKNOWN = "unknown"

@dataclass
class Address:
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

@dataclass
class Geo:
    lat: float
    lon: float

@dataclass
class Library:
    id: str
    name: str
    town: str
    network: str
    platform: str
    card_eligibility: CardEligibility
    pass_pickup_default: PassPickupPolicy
    address: Optional[Address] = None
    geo: Optional[Geo] = None
    card_page: Optional[str] = None
    pass_page: Optional[str] = None
    hours: Optional[dict] = None
    branch_ids: list[str] = field(default_factory=list)
    resident_zips: list[str] = field(default_factory=list)
    consortium_label: Optional[str] = None
    card_issuance_group: Optional[str] = None
    card_issuance_groups: list[str] = field(default_factory=list)
    card_auth_groups: list[str] = field(default_factory=list)
    eligibility_source_phrase: Optional[str] = None
    pickup_source_phrase: Optional[str] = None
