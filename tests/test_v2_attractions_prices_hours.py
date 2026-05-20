from pathlib import Path
from malibbene.sources_v2.attractions.prices import enqueue as enq_prices
from malibbene.sources_v2.attractions.hours import enqueue as enq_hours

def test_prices_request(tmp_path):
    (tmp_path/"mfa.html").write_text("<html/>")
    p = enq_prices("mfa", tmp_path/"mfa.html", tmp_path)
    assert "prices" in str(p) and p.exists()

def test_hours_request(tmp_path):
    (tmp_path/"mfa.html").write_text("<html/>")
    p = enq_hours("mfa", tmp_path/"mfa.html", tmp_path)
    assert "hours" in str(p) and p.exists()
