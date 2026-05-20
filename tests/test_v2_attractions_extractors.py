from pathlib import Path
from malibbene.sources_v2.attractions.visitor_eligibility import enqueue as enq_visitor
from malibbene.sources_v2.attractions.reservation import enqueue as enq_reserv

def test_enqueue_visitor_writes_request(tmp_path):
    html_path = tmp_path/"mfa.html"; html_path.write_text("<html>about</html>")
    out = enq_visitor(slug="mfa", html_path=html_path, raw_root=tmp_path)
    assert out.exists()

def test_enqueue_reservation_uses_distinct_kind(tmp_path):
    html_path = tmp_path/"mfa.html"; html_path.write_text("<html>visit</html>")
    out = enq_reserv(slug="mfa", html_path=html_path, raw_root=tmp_path)
    assert "reservation" in str(out)
