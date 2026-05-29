"""Empirical card-scope probe for MuseumKey pass reservations.

WHY: MuseumKey (Cohasset / Hingham) gates pass reservations behind a
library-card login, and which cards a given pass accepts is only knowable
by attempting auth. Mirrors the assabet + libcal probes.

SAFETY (critical): this probe submits ONLY the patron-login step at
``https://www2.museumkey.com/ui/patronLogin/``. It does NOT proceed past
the login redirect — the date / time / pass-selection screens are never
posted to. The classifier flags ``booked_unexpectedly`` if any response
ever matches a confirmation pattern.

PRIVACY: barcodes (and PINs) flow in as parameters; results only ever
store the card LABEL.

CALIBRATION STATUS: response signatures are based on the museum-key.com
login form's known error wording. Verdict regexes may need tuning after
live calibration against Cohasset / Hingham — drop captured response
bodies into ``tests/fixtures/museumkey_probe/<verdict>.html``.
"""
from __future__ import annotations

import http.cookiejar
import re
import urllib.parse
import urllib.request

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

# Login endpoint is shared across all MK libraries; ``code`` identifies
# the library subdomain (e.g. ``cohasset``, ``hinghampublic``).
_LOGIN_URL = "https://www2.museumkey.com/ui/patronLogin/"

# ── Response signatures ─────────────────────────────────────────────────

# Library card unknown to the consortium auth (wrong number, wrong library).
_REJECT_INVALID = re.compile(
    r"invalid (?:library )?card|"
    r"card (?:not |is not )(?:valid|found|recognized)|"
    r"barcode (?:not |is not )(?:valid|found|recognized)|"
    r"(?:incorrect|wrong) (?:barcode|card number|password|pin)",
    re.I,
)

# Card recognized but not authorized to book a pass (e.g. expired,
# restricted account, non-pass-eligible patron type).
_REJECT_RESIDENT = re.compile(
    r"not (?:authorized|eligible|allowed) to (?:reserve|book)|"
    r"account (?:is )?(?:blocked|suspended|expired|on hold)|"
    r"residents? only|patrons? of [^.]{0,80} only",
    re.I,
)

# Successful login → redirect to the byMuseum chooser or the patron
# dashboard. Either of these substrings appearing means the card auth
# step passed.
_ADVANCED = re.compile(
    r"/ui/byMuseum/|/ui/patronHome/|patronDashboard|"
    r'<title>[^<]*(?:Welcome|Select a Museum|Choose Museum)',
    re.I,
)

_FORMAT_ERROR = re.compile(
    r"please enter (?:a |your )?(?:valid )?(?:library card|barcode|pin)|"
    r"required field|field is required",
    re.I,
)

_BOOKED = re.compile(
    r"reservation (?:is )?(?:complete|confirmed)|"
    r"confirmation (?:number|code)|"
    r"your pass has been (?:booked|reserved)",
    re.I,
)


def probe_card(
    library_code: str,
    card_number: str,
    *,
    pin: str | None = None,
    timeout: int = 30,
) -> dict:
    """Submit ONLY the MuseumKey patron-login step and classify the response.

    Parameters
    ----------
    library_code
        The library's MuseumKey subdomain code (e.g. ``"cohasset"``,
        ``"hinghampublic"``). Passed to the login form via ``code``.
    card_number
        Patron barcode. Not logged or persisted.
    pin
        PIN / password. Most MK libraries require it; pass ``None`` and
        the probe will still execute (response will likely be
        ``rejected_invalid`` or ``format_error``, which is itself useful
        signal).
    timeout
        Per-request socket timeout in seconds.

    Returns
    -------
    dict
        ``{"verdict": ..., "http_status": <int>}``. Verdicts mirror the
        libcal probe: ``accepted`` / ``rejected_invalid`` /
        ``rejected_resident`` / ``format_error`` / ``booked_unexpectedly``
        / ``unknown``.
    """
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    # GET login form to capture the session cookie + any CSRF/__VIEWSTATE
    # tokens the legacy ASP-style form ships with.
    initial = opener.open(
        urllib.request.Request(_LOGIN_URL, headers={"User-Agent": _UA}),
        timeout=timeout,
    ).read().decode("utf-8", "replace")

    payload = {"code": library_code, "barcode": card_number}
    if pin:
        payload["password"] = pin
    payload.update(_extract_hidden_fields(initial))

    data = urllib.parse.urlencode(payload).encode()
    resp = opener.open(
        urllib.request.Request(
            _LOGIN_URL, data=data,
            headers={
                "User-Agent": _UA,
                "Referer": _LOGIN_URL,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        ),
        timeout=timeout,
    )
    body = resp.read().decode("utf-8", "replace")
    status = getattr(resp, "status", 200)
    return {"verdict": classify_response(body), "http_status": status}


def classify_response(body: str) -> str:
    """Pure classification — same verdict ladder as the libcal probe."""
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


_HIDDEN_RE = re.compile(
    r'<input[^>]+type="hidden"[^>]+name="([^"]+)"[^>]+value="([^"]*)"',
    re.I,
)


def _extract_hidden_fields(html: str) -> dict[str, str]:
    """Pull every <input type="hidden" name=.. value=..> from the login form.

    MuseumKey's legacy ASP login carries ``__VIEWSTATE`` / ``__EVENTVALIDATION``
    style hidden fields that must round-trip with the POST or the server
    rejects the form before even looking at the barcode.
    """
    return {name: value for name, value in _HIDDEN_RE.findall(html)}
