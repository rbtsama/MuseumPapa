"""Offline classifier tests for the LibCal card-scope probe.

Pure-function tests against synthetic response bodies. No network. Real
calibration data should land under ``tests/fixtures/libcal_probe/`` once
we capture live responses — those fixture-based tests would augment, not
replace, these synthetic baselines.
"""
from malibbene.sources_v2.libcal.booking_probe import classify_response


def test_advanced_to_step_2_is_accepted():
    body = '<div class="s-lc-pass-cal">...</div>'
    assert classify_response(body) == "accepted"


def test_advanced_reserver_form_is_accepted():
    body = '<form><input name="reserver_email" /></form>'
    assert classify_response(body) == "accepted"


def test_invalid_barcode_is_rejected_invalid():
    body = "Sorry, your barcode was not found in our records."
    assert classify_response(body) == "rejected_invalid"


def test_expired_card_is_rejected_invalid():
    body = "Your card number is expired."
    assert classify_response(body) == "rejected_invalid"


def test_residency_block_is_rejected_resident():
    body = "This pass is restricted to residents only."
    assert classify_response(body) == "rejected_resident"


def test_not_eligible_is_rejected_resident():
    body = "Patrons of Boston Public Library only."
    assert classify_response(body) == "rejected_resident"


def test_empty_barcode_is_format_error():
    body = "Please enter your library card number."
    assert classify_response(body) == "format_error"


def test_finalized_booking_is_flagged_loud():
    # A confirmation-looking response from a card-only POST must NEVER
    # silently return 'accepted' — we surface 'booked_unexpectedly'.
    body = "Your reservation is complete. Confirmation code 12345."
    assert classify_response(body) == "booked_unexpectedly"


def test_advanced_marker_wins_over_residency_boilerplate():
    # If the page advanced AND also shows a residency reminder, the advance
    # is the load-bearing signal.
    body = (
        '<div class="s-lc-pass-cal">date picker</div>'
        '<p>Note: this pass is available to residents only.</p>'
    )
    assert classify_response(body) == "accepted"


def test_unknown_response_is_unknown():
    body = "<html><body>some unrelated page</body></html>"
    assert classify_response(body) == "unknown"
