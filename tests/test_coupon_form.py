from malibbene.common.coupon_form import classify_coupon_form
from malibbene.schema.pass_ import CouponForm


def test_bogo_detected_from_two_for_one():
    assert classify_coupon_form("2-for-1 ferry fees") == CouponForm.BOGO


def test_bogo_from_buy_one_get_one():
    assert classify_coupon_form("buy one get one free") == CouponForm.BOGO


def test_free_form():
    assert classify_coupon_form("free admission for all") == CouponForm.FREE


def test_percent_off():
    assert classify_coupon_form("50% off general admission") == CouponForm.PERCENT_OFF


def test_dollar_off():
    assert classify_coupon_form("$5 off admission per person") == CouponForm.DOLLAR_OFF


def test_per_person_price():
    assert classify_coupon_form("admission $9 per person with pass") == CouponForm.PER_PERSON_PRICE


def test_vague_discount():
    assert classify_coupon_form("discount on tickets") == CouponForm.DISCOUNT
