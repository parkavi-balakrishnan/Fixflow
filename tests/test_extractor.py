"""Unit tests for src/engine/extractor.py."""
import json
import pytest

from src.engine.deeplink_matcher import DeeplinkMatcher
from src.engine.extractor import SIISExtractor, format_description, format_goal, format_title
from src.engine.validator import validate_response


@pytest.fixture(scope="module")
def extractor():
    matcher = DeeplinkMatcher()
    return SIISExtractor(matcher)


def test_format_helpers():
    assert format_goal("Screen Damage") == "Follow these steps to perform this Screen Damage Troubleshooting"
    
    t = format_title("Email server not responding on phone")
    assert 2 <= len(t.split()) <= 3

    d = format_description("Back Up Data")
    assert d.startswith("It will")
    assert 5 <= len(d.split()) <= 7


def test_extract_from_siis_sample_1(extractor):
    with open("data/siis_responses.json") as f:
        data = json.load(f)

    row = data["responses"][0]
    query = row["original_query"]
    siis_payload = row["siis_response"]

    result_resp = extractor.extract(query, siis_payload)
    assert len(result_resp.contexts) > 0

    # Must pass all validator gates
    val_result = validate_response(result_resp)
    assert val_result.is_valid is True, f"Validation failed: {val_result.errors}"


def test_extract_all_20_siis_responses_pass_validator(extractor):
    with open("data/siis_responses.json") as f:
        data = json.load(f)

    for i, row in enumerate(data["responses"]):
        query = row["original_query"]
        siis_payload = row["siis_response"]

        resp = extractor.extract(query, siis_payload)
        val_res = validate_response(resp)
        assert val_res.is_valid is True, f"Failed on row {i+1} ({row['id']}): {val_res.errors}"
