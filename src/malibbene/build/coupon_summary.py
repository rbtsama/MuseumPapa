"""Generate mobile e-commerce style summary strings from Coupon structure."""
from __future__ import annotations


def _num(value):
    if value is None:
        return ""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _form_label(form: str, value) -> str:
    if form == "free":
        return "FREE"
    if form == "percent-off" and value is not None:
        return f"{_num(value)}% off"
    if form == "dollar-off" and value is not None:
        return f"${_num(value)} off"
    if form == "per-person-price" and value is not None:
        return f"${_num(value)}/person"
    if form == "discount":
        return "Special offer"
    return ""


def _audience_label(ap: dict) -> str:
    audience = ap["audience"]
    age = ap.get("age_range")
    if audience in ("Adult", "Senior", "Everyone", "Vehicle", "Single ticket"):
        return audience
    # Child / Youth get age suffix when range present
    if not age:
        return audience
    lo, hi = age.get("min"), age.get("max")
    if lo is None and hi is not None:
        return f"{audience} <{hi + 1}"
    if lo is not None and hi is None:
        return f"{audience} {lo}+"
    if lo is not None and hi is not None:
        return f"{audience} {lo}-{hi}"
    return audience


def _capacity_prefix(capacity: dict) -> str:
    kind, n = capacity.get("kind"), capacity.get("n")
    if kind == "people" and n is not None:
        return f"Up to {n} · "
    if kind == "vehicle":
        return "Per vehicle · "
    if kind == "ticket":
        return "1 ticket · "
    return ""


def format_summary(capacity: dict, audience_policies: list) -> str:
    if not audience_policies:
        return ""

    prefix = _capacity_prefix(capacity)

    # Bonus-tier special case
    if (len(audience_policies) == 2
            and audience_policies[0]["audience"] == "Everyone"
            and audience_policies[1]["audience"] == "Child"
            and audience_policies[1]["form"] == "free"
            and (audience_policies[1].get("age_range") or {}).get("max") is not None):
        primary = _form_label(audience_policies[0]["form"], audience_policies[0]["value"])
        ar = audience_policies[1]["age_range"]
        return f"{prefix}{primary} · Kids under {ar['max'] + 1} free"

    # Single policy
    if len(audience_policies) == 1:
        ap = audience_policies[0]
        label = _form_label(ap["form"], ap["value"])
        a = ap["audience"]
        if a == "Everyone":
            return f"{prefix}{label}"
        if a == "Adult":
            return f"{prefix}Adults only · {label}"
        if a in ("Vehicle", "Single ticket"):
            return f"{prefix}{label}"
        return f"{prefix}{_audience_label(ap)} · {label}"

    # Multi-policy: group by (form, value)
    groups = []
    seen = {}
    for ap in audience_policies:
        key = (ap["form"], ap["value"])
        if key in seen:
            seen[key][1].append(_audience_label(ap))
        else:
            entry = [_form_label(ap["form"], ap["value"]), [_audience_label(ap)]]
            seen[key] = entry
            groups.append(entry)

    parts = []
    for form_label, audiences in groups:
        parts.append(f"{form_label} ({', '.join(audiences)})")
    return prefix + " · ".join(parts)
