from pathlib import Path
from malibbene.sources_v2.assabet.policies import extract_policy_text
from malibbene.schema.library import CardEligibility

FIXT = Path(__file__).parent / "fixtures/assabet/wakefield_get_a_card.html"


def test_extract_policy_text_returns_blocks_with_classified_eligibility():
    out = extract_policy_text(FIXT.read_text(encoding="utf-8"))
    assert "policy_text" in out
    assert out["card_eligibility"] in {c.value for c in CardEligibility}
    assert len(out["policy_text"]) > 100
