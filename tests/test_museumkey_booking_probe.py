"""Offline classifier tests for the MuseumKey card-scope probe."""
from malibbene.sources_v2.museumkey.booking_probe import (
    _extract_hidden_fields,
    classify_response,
)


def test_redirect_to_bymuseum_is_accepted():
    body = '<a href="/ui/byMuseum/?code=cohasset">Select a Museum</a>'
    assert classify_response(body) == "accepted"


def test_dashboard_is_accepted():
    body = '<title>Welcome to your Patron Dashboard</title>'
    assert classify_response(body) == "accepted"


def test_invalid_card_is_rejected_invalid():
    body = "Invalid library card number."
    assert classify_response(body) == "rejected_invalid"


def test_wrong_pin_is_rejected_invalid():
    body = "Incorrect password."
    assert classify_response(body) == "rejected_invalid"


def test_account_blocked_is_rejected_resident():
    body = "Account is blocked. Please contact your library."
    assert classify_response(body) == "rejected_resident"


def test_empty_field_is_format_error():
    body = "Please enter a valid library card."
    assert classify_response(body) == "format_error"


def test_confirmation_is_flagged_loud():
    body = "Your pass has been booked. Confirmation code MK-12345."
    assert classify_response(body) == "booked_unexpectedly"


def test_unknown_response_is_unknown():
    assert classify_response("<html>nope</html>") == "unknown"


def test_extract_hidden_fields_roundtrips_viewstate():
    html = (
        '<form><input type="hidden" name="__VIEWSTATE" value="abcDEF==" />'
        '<input type="hidden" name="__EVENTVALIDATION" value="xyz" />'
        '<input type="text" name="barcode" />'
        '</form>'
    )
    got = _extract_hidden_fields(html)
    assert got == {"__VIEWSTATE": "abcDEF==", "__EVENTVALIDATION": "xyz"}


def test_extract_hidden_fields_empty_when_no_hidden_inputs():
    assert _extract_hidden_fields("<form></form>") == {}
