"""Lexical regression coverage for ``malibbene.common.normalize``."""
import pytest

from malibbene.common.normalize import TEST_CASES, normalize


@pytest.mark.parametrize("raw,expected_label,expected_class", TEST_CASES)
def test_normalize_cases(raw, expected_label, expected_class):
    label, label_class = normalize(raw)
    assert (label, label_class) == (expected_label, expected_class)


def test_empty_returns_unknown():
    assert normalize("") == ("", "unknown")
    assert normalize(None) == ("", "unknown")  # type: ignore[arg-type]


def test_kid_free_alongside_adult_price_does_not_misclassify():
    """Adult price wins over 'children free' wording — regression for the
    common 'children under 6 free; adults $10' phrasing in Assabet pages."""
    label, cls = normalize(
        "Children 6 and under are admitted free. Pass admits 2 adults at $10 per person."
    )
    assert (label, cls) == ("$10", "price")
