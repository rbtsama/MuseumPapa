"""Schema roundtrip validation for data/structured/*.json.

Loads each structured JSON file and constructs the matching dataclass for every
item. Catches:
  - field rename / removal that the build pipeline forgot to follow
  - enum value drift (new value added to seed but missing from enum)
  - type mismatches (e.g. address as string instead of Address dict)

Strict mode: unknown fields fail unless explicitly whitelisted in
``_KNOWN_EXTRAS`` per dataclass. The whitelist exists for legitimate build-
pipeline metadata that is intentionally not part of the canonical schema.
"""
from __future__ import annotations

import dataclasses
import json
import typing
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import pytest

from malibbene.schema.attraction import (
    Attraction,
    AudiencePrice,
    PassHolderPath,
    Reservation,
    ReservationRequired,
    VisitorEligibility,
    VisitorResidency,
)
from malibbene.schema.branch import Branch
from malibbene.schema.library import (
    Address,
    CardEligibility,
    Geo,
    Library,
    PassPickupPolicy,
)
from malibbene.schema.pass_ import (
    AudiencePolicy,
    Capacity,
    CapacityKind,
    Coupon,
    CouponForm,
    EligibilityOverride,
    Pass,
    PassForm,
    Restrictions,
)

REPO = Path(__file__).resolve().parents[1]
STRUCTURED = REPO / "data" / "structured"

# Fields that the build pipeline emits but are not declared in the schema.
# Keep this list tight — adding to it weakens the contract.
_KNOWN_EXTRAS: dict[type, set[str]] = {
    Library: {"domain", "non_resident_policy_initial"},
    Pass: {"source_phrases", "availability", "attraction_rawslug"},
    Attraction: set(),
    Branch: {"code"},
    Address: set(),
    Geo: set(),
    Reservation: set(),
    VisitorEligibility: set(),
    AudiencePrice: set(),
    Capacity: set(),
    AudiencePolicy: set(),
    Coupon: set(),
    EligibilityOverride: set(),
    Restrictions: set(),
}


def _unwrap_optional(tp: Any) -> Any:
    """Return the inner type of Optional[X] / Union[X, None]; pass through otherwise."""
    if get_origin(tp) is Union:
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0]
        # Union[str, list[str]] etc. — leave as-is.
        return tp
    return tp


def _convert_value(tp: Any, value: Any) -> Any:
    """Convert a JSON-loaded value into the type declared by ``tp``."""
    if value is None:
        return None

    tp = _unwrap_optional(tp)
    origin = get_origin(tp)

    # Plain dataclass nested object.
    if dataclasses.is_dataclass(tp) and isinstance(value, dict):
        return _dict_to_dataclass(tp, value)

    # Enum.
    if isinstance(tp, type) and issubclass(tp, Enum):
        # Will raise ValueError if value is not a valid enum member.
        return tp(value)

    # list[X]
    if origin in (list, typing.List):
        (inner,) = get_args(tp) or (Any,)
        return [_convert_value(inner, v) for v in value]

    # dict[K, V] — leave as-is (we don't introspect dict[str, Any] values).
    if origin in (dict, typing.Dict):
        return value

    # Union (e.g. Union[str, list[str]]) — return as-is.
    if origin is Union:
        return value

    # Primitive — return as-is.
    return value


def _dict_to_dataclass(cls: type, data: dict) -> Any:
    """Recursively build dataclass ``cls`` from JSON dict ``data`` (strict)."""
    assert dataclasses.is_dataclass(cls), f"{cls!r} is not a dataclass"
    declared = {f.name: f for f in dataclasses.fields(cls)}
    allowed_extra = _KNOWN_EXTRAS.get(cls, set())

    unknown = set(data) - set(declared) - allowed_extra
    if unknown:
        raise AssertionError(
            f"{cls.__name__}: unknown fields {sorted(unknown)} "
            f"(declared={sorted(declared)}, allowed_extra={sorted(allowed_extra)})"
        )

    # Use get_type_hints so forward refs resolve (from __future__ annotations).
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for name, fld in declared.items():
        if name not in data:
            continue  # use dataclass default
        tp = hints.get(name, fld.type)
        kwargs[name] = _convert_value(tp, data[name])
    return cls(**kwargs)


def _load(name: str, key: str) -> list[dict]:
    path = STRUCTURED / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))[key]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_libraries_roundtrip() -> None:
    items = _load("libraries", "libraries")
    assert items, "libraries.json is empty"
    for raw in items:
        lib = _dict_to_dataclass(Library, raw)
        assert isinstance(lib, Library)
        assert lib.id and lib.name
        assert isinstance(lib.card_eligibility, CardEligibility)
        assert isinstance(lib.pass_pickup_default, PassPickupPolicy)
        if lib.address is not None:
            assert isinstance(lib.address, Address)
        if lib.geo is not None:
            assert isinstance(lib.geo, Geo)


def test_attractions_roundtrip() -> None:
    items = _load("attractions", "attractions")
    assert items, "attractions.json is empty"
    for raw in items:
        att = _dict_to_dataclass(Attraction, raw)
        assert isinstance(att, Attraction)
        assert att.slug and att.name
        for price in att.prices:
            assert isinstance(price, AudiencePrice)
        if att.visitor_eligibility is not None:
            assert isinstance(att.visitor_eligibility, VisitorEligibility)
            assert isinstance(att.visitor_eligibility.residency, VisitorResidency)
        if att.reservation is not None:
            assert isinstance(att.reservation, Reservation)
            assert isinstance(att.reservation.required, ReservationRequired)
            assert isinstance(att.reservation.pass_holder_path, PassHolderPath)


def test_passes_roundtrip() -> None:
    items = _load("passes", "passes")
    assert items, "passes.json is empty"
    for raw in items:
        p = _dict_to_dataclass(Pass, raw)
        assert isinstance(p, Pass)
        assert p.library_id and p.attraction_slug
        assert isinstance(p.pass_form, PassForm)
        if p.coupon is not None:
            assert isinstance(p.coupon, Coupon)
            assert isinstance(p.coupon.capacity, Capacity)
            assert isinstance(p.coupon.capacity.kind, CapacityKind)
            for ap in p.coupon.audience_policies:
                assert isinstance(ap, AudiencePolicy)
                assert isinstance(ap.form, CouponForm)
        if p.eligibility_override is not None:
            assert isinstance(p.eligibility_override, EligibilityOverride)
            assert isinstance(p.eligibility_override.residency, PassPickupPolicy)
        if p.restrictions is not None:
            assert isinstance(p.restrictions, Restrictions)


def test_branches_roundtrip() -> None:
    items = _load("branches", "branches")
    assert items, "branches.json is empty"
    for raw in items:
        b = _dict_to_dataclass(Branch, raw)
        assert isinstance(b, Branch)
        assert b.id and b.library_id and b.name
        if b.address is not None:
            assert isinstance(b.address, Address)
        if b.geo is not None:
            assert isinstance(b.geo, Geo)


@pytest.mark.parametrize(
    "name,key,enum_paths",
    [
        (
            "libraries",
            "libraries",
            [
                ("card_eligibility", CardEligibility),
                ("pass_pickup_default", PassPickupPolicy),
            ],
        ),
        (
            "attractions",
            "attractions",
            [
                ("visitor_eligibility.residency", VisitorResidency),
                ("reservation.required", ReservationRequired),
                ("reservation.pass_holder_path", PassHolderPath),
            ],
        ),
        (
            "passes",
            "passes",
            [
                ("pass_form", PassForm),
                ("coupon.capacity.kind", CapacityKind),
                ("eligibility_override.residency", PassPickupPolicy),
            ],
        ),
    ],
)
def test_enum_values_valid(name: str, key: str, enum_paths: list) -> None:
    items = _load(name, key)
    for raw in items:
        for path, enum_cls in enum_paths:
            cur: Any = raw
            for part in path.split("."):
                if not isinstance(cur, dict):
                    cur = None
                    break
                cur = cur.get(part)
                if cur is None:
                    break
            if cur is None:
                continue
            valid = {e.value for e in enum_cls}
            assert cur in valid, (
                f"{name}: {path}={cur!r} not in {enum_cls.__name__} {sorted(valid)}"
            )

    # Pass.coupon.audience_policies[*].form — list-valued enum path.
    if name == "passes":
        valid = {e.value for e in CouponForm}
        for raw in items:
            coupon = raw.get("coupon")
            if not coupon:
                continue
            for ap in coupon.get("audience_policies", []):
                form = ap.get("form")
                if form is None:
                    continue
                assert form in valid, (
                    f"passes: coupon.audience_policies[].form={form!r} "
                    f"not in CouponForm {sorted(valid)}"
                )
