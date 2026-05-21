"""Empirical residency probe for Assabet pass reservations.

WHY: a pass's "Resident Only" restriction is enforced by the platform at
reservation time against the ZIP on the card — it is almost never written in
the catalog text. The only reliable way to learn it is to actually attempt a
reservation and read whether the card is accepted or rejected.

SAFETY (critical): this probe submits ONLY the first step of the reservation
wizard — the "Library Card Number" form (POST ``reservationlibrarycard`` +
``save=save``). That step VALIDATES the card; it does not finalize a booking
(the Assabet flow has subsequent review/confirm/email steps which we never
submit). The classifier additionally aborts and reports ``booked_unexpectedly``
if a response ever looks like a completed reservation, so we never silently
create one.

PRIVACY: card barcodes are passed in by the caller and are NEVER written to
output files or logs. Probe results record only the card LABEL (e.g.
"wakefield") and the verdict.
"""
from __future__ import annotations

import http.cookiejar
import re
import urllib.parse
import urllib.request

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

# Response signatures.
_REJECT_RESIDENT = re.compile(
    r"does not appear to be valid|blocked from making this type of reservation",
    re.I,
)
_FORMAT_ERROR = re.compile(r"please check the following", re.I)
# A FINISHED booking — must never happen from a card-only POST; if it does we
# flag it loudly instead of pretending the probe was clean.
_BOOKED = re.compile(
    r"reservation (?:is )?complete|confirmation number|your reservation has been|"
    r"check your email for|pass has been reserved",
    re.I,
)
# Advanced to the next wizard step (accepted): the card validated and the
# "Reserver Information" step rendered. We key on its personal-info inputs
# (reservationfirstname / reservationemail) — these only appear AFTER the card
# is accepted, and never on the card-entry step or the reject re-render.
_ADVANCED = re.compile(
    r'name="reservation(?:firstname|lastname|email)"|<legend[^>]*>\s*Reserver\s+Information',
    re.I,
)


def _date_path(base_url: str, slug: str, year_month: str, day: str) -> str:
    # base_url like https://<lib>.assabetinteractive.com
    return f"{base_url.rstrip('/')}/museum-passes/by-date/{year_month}/{day}/{slug}/"


def probe_card(reservation_url: str, card_number: str, timeout: int = 30) -> dict:
    """Submit ONLY the card-validation step and classify the response.

    Returns {verdict, http_status} where verdict is one of:
      - "rejected_resident"   card valid-format but not authorized (resident-only / blocked)
      - "accepted"            advanced to the next wizard step (NOT booked)
      - "format_error"        card number format rejected (inconclusive)
      - "booked_unexpectedly" response looks like a finalized booking — STOP
      - "unknown"             none of the above matched
    Never raises on classification; network errors propagate to the caller.
    """
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    # GET first to obtain session cookies (PHPSESSID etc.).
    opener.open(
        urllib.request.Request(reservation_url, headers={"User-Agent": _UA}),
        timeout=timeout,
    ).read()
    data = urllib.parse.urlencode(
        {"reservationlibrarycard": card_number, "save": "save"}
    ).encode()
    resp = opener.open(
        urllib.request.Request(
            reservation_url, data=data,
            headers={"User-Agent": _UA, "Referer": reservation_url,
                     "Content-Type": "application/x-www-form-urlencoded"},
        ),
        timeout=timeout,
    )
    body = resp.read().decode("utf-8", "replace")
    status = getattr(resp, "status", 200)

    if _BOOKED.search(body):
        verdict = "booked_unexpectedly"
    elif _REJECT_RESIDENT.search(body):
        verdict = "rejected_resident"
    elif _FORMAT_ERROR.search(body):
        verdict = "format_error"
    elif _ADVANCED.search(body):
        verdict = "accepted"
    else:
        verdict = "unknown"
    return {"verdict": verdict, "http_status": status}
