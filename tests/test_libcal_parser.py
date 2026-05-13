"""Parser-level tests for ``malibbene.sources.libcal.index_page``. No network."""

from malibbene.sources.libcal.index_page import (
    classify_pass_type,
    list_passes,
    parse_detail,
)
from malibbene.common import http


BPL_DETAIL_FIXTURE = """
<html><body>
<div id="s-lc-public-pd">
  <div class="col-sm-8">
    <h1 id="s-lc-public-pt">Boston Children's Museum (e-coupon)</h1>
    <p class="s-lc-pass-address">308 Congress St, Boston, MA 02210 <a href="/x"></a></p>
    <p>Pass admits up to 4 visitors at $12 admission per person.</p>
    <p>Pass is downloadable via email.</p>
    <a href="https://www.bostonkids.org/" class="s-lc-museum-link">site</a>
  </div>
  <div class="s-lc-avail-content"></div>
</div>
<script>var springyPage = {museum: '247124590599', other: 1};</script>
</body></html>
"""

CAMBRIDGE_PHYSICAL_FIXTURE = """
<html><body>
<h1 id="s-lc-public-pt">Museum of Fine Arts (physical pass)</h1>
<p>Pass admits 2 adults for free admission. Pass must be returned to the library.</p>
<script>var springyPage = {museum: 'a169525fe2d3'};</script>
</body></html>
"""

LISTING_FIXTURE = """
<html><body>
<a href="/passes/247124590599" class="pass-link">Boston Children's Museum (e-coupon)</a>
<a href="/passes/5478304b3d42">New England Aquarium (physical)</a>
<a href="/passes/passes">ignore-self</a>
<a href="/passes/247124590599">duplicate</a>
</body></html>
"""


def test_parse_detail_extracts_title_and_museum_name():
    rec = parse_detail("247124590599", "http://x/passes/247124590599", BPL_DETAIL_FIXTURE)
    assert rec["title_raw"] == "Boston Children's Museum (e-coupon)"
    assert rec["museum_name"] == "Boston Children's Museum"


def test_parse_detail_extracts_museum_hex_from_springypage():
    rec = parse_detail("ANY", "http://x/passes/ANY", BPL_DETAIL_FIXTURE)
    assert rec["museum_hex"] == "247124590599"


def test_parse_detail_e_coupon_classified_digital():
    rec = parse_detail("ANY", "http://x", BPL_DETAIL_FIXTURE)
    assert rec["pass_type"] == "digital"


def test_parse_detail_physical_returnable_classified_circ():
    rec = parse_detail("ANY", "http://x", CAMBRIDGE_PHYSICAL_FIXTURE)
    assert rec["pass_type"] == "physical-circ"


def test_parse_detail_runs_normalize():
    rec = parse_detail("ANY", "http://x", BPL_DETAIL_FIXTURE)
    assert rec["label"] == "$12"
    assert rec["label_class"] == "price"


def test_parse_detail_status_ok_when_complete():
    rec = parse_detail("ANY", "http://x", BPL_DETAIL_FIXTURE)
    assert rec["status"] == "ok"


def test_parse_detail_status_failed_when_no_title():
    rec = parse_detail("ANY", "http://x", "<p>nothing</p>")
    assert rec["status"].startswith("failed:")


def test_classify_e_coupon_suffix_wins_over_body():
    """Title suffix should outrank ambiguous body text."""
    pt, raw = classify_pass_type("X (e-coupon)", "Pass must be returned to the library")
    assert pt == "digital"


def test_classify_physical_returnable_body_when_no_suffix():
    pt, raw = classify_pass_type("X", "Pass is returnable to the circulation desk")
    assert pt == "physical-circ"


def test_classify_digital_body_when_no_suffix():
    pt, raw = classify_pass_type("X", "Promo code will be emailed to you (downloadable via email)")
    assert pt == "digital"


def test_list_passes_dedupes_and_skips_self_link(monkeypatch):
    monkeypatch.setattr(http, "fetch", lambda url, **kw: LISTING_FIXTURE)
    pairs, st = list_passes("example.libcal.com")
    pids = [p for p, _ in pairs]
    assert "passes" not in pids
    assert pids.count("247124590599") == 1
    assert st == "ok"
