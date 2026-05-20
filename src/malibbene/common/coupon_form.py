"""Coupon form classifier. Priority: BOGO > free > %off > $off > per-person > generic discount."""
from __future__ import annotations
import re
from malibbene.schema.pass_ import CouponForm

_BOGO    = re.compile(r"\b(2[ -]?for[ -]?1|two[ -]?for[ -]?one|buy one get one)\b", re.I)
_FREE    = re.compile(r"\bfree\s+admission\b|\bfree\s+entry\b|\bcomplimentary\b", re.I)
_PCT     = re.compile(r"(\d{1,3})\s*%\s*off", re.I)
_DOLLAR  = re.compile(r"\$\s*\d+(\.\d+)?\s*off", re.I)
_PERPERS = re.compile(r"\$\s*\d+(\.\d+)?\s*per\s*person", re.I)
_DISC    = re.compile(r"discount", re.I)


def classify_coupon_form(text: str) -> CouponForm:
    if not text:
        return CouponForm.DISCOUNT
    if _BOGO.search(text):
        return CouponForm.BOGO
    if _FREE.search(text):
        return CouponForm.FREE
    if _PCT.search(text):
        return CouponForm.PERCENT_OFF
    if _DOLLAR.search(text):
        return CouponForm.DOLLAR_OFF
    if _PERPERS.search(text):
        return CouponForm.PER_PERSON_PRICE
    if _DISC.search(text):
        return CouponForm.DISCOUNT
    return CouponForm.DISCOUNT
