"""Unit tests for src/engine/deeplink_matcher.py."""
import pytest

from src.engine.deeplink_matcher import DeeplinkMatcher


@pytest.fixture(scope="module")
def matcher():
    return DeeplinkMatcher()


def test_matcher_loads_catalog(matcher):
    assert len(matcher.entries) >= 500
    assert matcher.vectorizer is not None
    assert matcher.tfidf_matrix is not None


def test_match_back_up_data(matcher):
    act_dl, val_dl, score = matcher.find_best_match("Back up data to Samsung Cloud")
    assert act_dl is not None
    assert act_dl.deeplink.startswith("bixby://masked/act/")
    assert score > 0.3
    # Check that validation deeplink is populated
    assert val_dl is not None
    assert val_dl.deeplink.startswith("bixby://masked/val/")


def test_match_time_format(matcher):
    act_dl, val_dl, score = matcher.find_best_match("Switch 24 hour time format style")
    assert act_dl is not None
    assert act_dl.deeplink == "bixby://masked/act/aa73a35e8d"
    assert val_dl is not None
    assert val_dl.deeplink == "bixby://masked/val/ef6814259a"


def test_fallback_on_unrelated_nonsense(matcher):
    act_dl, val_dl, score = matcher.find_best_match("xyzqwertynonsense1234567890", threshold=0.9)
    assert act_dl.deeplink == "bixby://dummy_positive"
    assert val_dl is None
