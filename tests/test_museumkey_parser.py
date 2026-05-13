"""Parser-level tests for ``malibbene.sources.museumkey.index_page``.

MuseumKey has two themes that put ``musID`` in different positions relative
to the museum name — these tests pin both branches."""

from malibbene.sources.museumkey import index_page
from malibbene.common import http


V1_FIXTURE = """
<html><body>
<a href="?musID=101"><span class="museumButtonName">Boston Children's Museum</span></a>
<div class="row collapse" id="detail101">
  <p>Pass admits 4 visitors at $12 admission per person. Must be returned to the library.</p>
</div>
<a href="?musID=202"><span class="museumButtonName">Free Park Pass</span></a>
<div class="row collapse" id="detail202">
  <p>Free admission for up to 5 people. Coupon — does not need to be returned.</p>
</div>
</body></html>
"""

MK2_FIXTURE = """
<html><body>
<div class="mk2ButtonName"><p>Museum of Science</p></div>
<a href="?musID=303">Check Dates</a>
<div class="row collapse" id="detail303">
  <p>Pass admits 2 adults at $5 each. Pass is returnable.</p>
</div>
</body></html>
"""


def test_v1_theme_parses_two_museums(monkeypatch):
    monkeypatch.setattr(http, "fetch", lambda url, **kw: V1_FIXTURE)
    _, data = index_page.scrape_library(
        "fake_lib", "code", 1, {"boston children's museum": "boston-childrens-museum"}
    )
    slugs = [p["slug"] for p in data["passes"]]
    assert "boston-childrens-museum" in slugs
    assert "free-park-pass" in slugs  # derived from name (no map entry)
    bcm = next(p for p in data["passes"] if p["slug"] == "boston-childrens-museum")
    assert bcm["label"] == "$12"
    assert bcm["pass_type"] == "physical-circ"


def test_v1_theme_disposable_classifies_as_coupon(monkeypatch):
    monkeypatch.setattr(http, "fetch", lambda url, **kw: V1_FIXTURE)
    _, data = index_page.scrape_library("fake_lib", "code", 1, {})
    park = next(p for p in data["passes"] if p["slug"] == "free-park-pass")
    assert park["pass_type"] == "physical-coupon"
    assert park["label"] == "Free"


def test_mk2_theme_finds_forward_musid(monkeypatch):
    monkeypatch.setattr(http, "fetch", lambda url, **kw: MK2_FIXTURE)
    _, data = index_page.scrape_library("fake_lib", "code", 1, {})
    assert len(data["passes"]) == 1
    mos = data["passes"][0]
    assert mos["museum_name"] == "Museum of Science"
    assert mos["musid"] == "303"
    assert mos["label"] == "$5"


def test_fetch_failure_returned_as_failed_status(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("network down")
    monkeypatch.setattr(http, "fetch", boom)
    _, data = index_page.scrape_library("fake_lib", "code", 1, {})
    assert data["meta"]["fetch_status"].startswith("failed:")
    assert data["passes"] == []
