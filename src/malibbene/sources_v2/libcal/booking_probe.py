"""Empirical card-scope probe for LibCal pass reservations.

WHY: which cards a LibCal-hosted pass actually accepts is enforced by the
library's authentication service at reservation time — the card_eligibility
text on the public page is loose or absent. Mirroring assabet's probe (see
``sources_v2/assabet/booking_probe``), we POST only the card-validation
step and classify the response. Acceptance / rejection feeds
``booking_access_probe`` on each pass.

SAFETY (critical): this probe submits ONLY the barcode validation step of
the LibCal reservation wizard. It does NOT submit date / time / personal
info — the wizard's subsequent steps are never reached. The classifier
aborts and reports ``booked_unexpectedly`` if the response ever matches a
confirmation pattern, so we never silently create a reservation.

PRIVACY: card barcodes (and PINs, when needed) flow in as parameters and
are NEVER written to disk or logs. The probe result records only the
card LABEL (e.g. ``"bpl"``, ``"somerville"``) and the verdict.

CALIBRATION STATUS: response signatures below are best-effort patterns
based on the LibCal "Schedule Pass" widget HTML observed on BPL and
Cambridge. Real verdicts may need additional regexes once we run live
probes — see ``tests/test_libcal_booking_probe.py`` fixtures dir for
where to drop captured response bodies for each verdict class.
"""
from __future__ import annotations

import http.cookiejar
import re
import urllib.parse
import urllib.request

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

# ── Response signatures ─────────────────────────────────────────────────
# LibCal's auth-step error surfaces in a few canonical phrases. Each
# library skins the wording slightly; the regexes are deliberately loose.

# Card barcode not recognized by the consortium auth backend (e.g. invalid
# barcode format, non-member library, expired card).
_REJECT_INVALID = re.compile(
    r"barcode (?:was )?not (?:found|recognized|valid)|"
    r"invalid (?:library )?card|"
    r"not a valid (?:patron|barcode)|"
    r"card (?:number )?(?:is )?(?:not valid|expired)",
    re.I,
)

# Card recognized but not in the residency / patron-type group the pass
# requires (e.g. non-resident barcode on a resident-only BPL pass, junior
# card on an adult-only pass).
_REJECT_RESIDENT = re.compile(
    r"not eligible|not authorized|patrons of [^.]{0,80} only|"
    r"restricted to|residents? only|"
    r"this pass is (?:not )?available to|"
    r"unable to (?:reserve|book)|cannot reserve",
    re.I,
)

# Card validated → wizard advanced to step 2 (date / time / reserver info).
# LibCal renders a date picker block with class ``s-lc-pass-cal`` or a
# review-and-confirm form keyed by ``confirm_booking``. Either of these
# appearing means the auth step passed.
_ADVANCED = re.compile(
    r's-lc-pass-cal|confirm_booking|'
    r'name="(?:reserver_first|reserver_last|reserver_email|booking_date)"',
    re.I,
)

# Format-level barcode reject (e.g. non-numeric, wrong length) — usually
# rendered by client-side validation but mirrored server-side.
_FORMAT_ERROR = re.compile(
    r"please enter (?:a |your )?(?:valid |library )?(?:card|barcode)|"
    r"required field",
    re.I,
)

# Wizard *completed* — must never happen from a card-only POST. If it
# does we surface ``booked_unexpectedly`` loudly instead of returning a
# clean verdict.
_BOOKED = re.compile(
    r"reservation (?:is )?(?:complete|confirmed)|"
    r"confirmation (?:number|code)|"
    r"your pass has been (?:booked|reserved)|"
    r"check your email for",
    re.I,
)


def probe_card(
    reservation_url: str,
    card_number: str,
    *,
    pin: str | None = None,
    timeout: int = 30,
) -> dict:
    """Submit ONLY the LibCal card-validation step and classify the response.

    Parameters
    ----------
    reservation_url
        The pass's public LibCal page, e.g.
        ``https://bpl.libcal.com/passes/<id>``.
    card_number
        Patron barcode. Pass the raw barcode string; the probe does not
        log or persist it.
    pin
        Some libcal-hosted libraries require a PIN alongside the barcode
        (LibCal's "Patron API" auth mode). Pass ``None`` for barcode-only.
    timeout
        Per-request socket timeout in seconds.

    Returns
    -------
    dict
        ``{"verdict": ..., "http_status": <int>}`` where verdict is one of:
          - ``"accepted"``             card validated, wizard advanced
          - ``"rejected_invalid"``     barcode unknown to auth backend
          - ``"rejected_resident"``    barcode known but not eligible for pass
          - ``"format_error"``         barcode format / required-field error
          - ``"booked_unexpectedly"``  response looks like a finalized booking
          - ``"unknown"``              none of the above matched

    Notes
    -----
    Network errors propagate to the caller (no retries here — the orchestrator
    decides whether to retry, since "transient HTTP 500" vs "library down for
    maintenance" needs context the probe doesn't have).
    """
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    # GET first to obtain the session cookie + CSRF token (LibCal's auth
    # form includes a hidden _token field on most installs).
    initial = opener.open(
        urllib.request.Request(reservation_url, headers={"User-Agent": _UA}),
        timeout=timeout,
    ).read().decode("utf-8", "replace")
    csrf = _extract_csrf(initial)

    payload = {"barcode": card_number}
    if pin:
        payload["pin"] = pin
    if csrf:
        payload["_token"] = csrf

    data = urllib.parse.urlencode(payload).encode()
    resp = opener.open(
        urllib.request.Request(
            reservation_url, data=data,
            headers={
                "User-Agent": _UA,
                "Referer": reservation_url,
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
            },
        ),
        timeout=timeout,
    )
    body = resp.read().decode("utf-8", "replace")
    status = getattr(resp, "status", 200)
    return {"verdict": classify_response(body), "http_status": status}


# ── Pure classification (no I/O) ────────────────────────────────────────
def classify_response(body: str) -> str:
    """Classify a LibCal reservation-step response body. Pure function so
    fixtures-based unit tests can run offline without touching the network.
    """
    # Order matters. The advanced/step-2 marker proves the card was accepted,
    # even if the page also renders some boilerplate that overlaps with
    # rejection patterns (e.g. a residency reminder under the date picker).
    if _ADVANCED.search(body):
        return "accepted"
    if _REJECT_INVALID.search(body):
        return "rejected_invalid"
    if _REJECT_RESIDENT.search(body):
        return "rejected_resident"
    if _FORMAT_ERROR.search(body):
        return "format_error"
    if _BOOKED.search(body):
        return "booked_unexpectedly"
    return "unknown"


_CSRF_RE = re.compile(
    r'name="_token"[^>]*value="([^"]+)"|'
    r'<meta\s+name="csrf-token"\s+content="([^"]+)"',
    re.I,
)


def _extract_csrf(html: str) -> str | None:
    m = _CSRF_RE.search(html)
    if not m:
        return None
    return m.group(1) or m.group(2)
