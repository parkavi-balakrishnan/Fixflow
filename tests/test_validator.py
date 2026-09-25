"""Unit tests for src/engine/validator.py."""
import pytest

from src.engine.validator import (
    DeeplinkCatalogIndex,
    ResponseValidator,
    detect_url_leakage,
    validate_response,
)
from src.schema import (
    Action,
    ContextDeeplinkResponse,
    Deeplink,
    Goal,
    StepGroup,
    ValidationDeepLink,
    actionCategory,
)


def _build_valid_response() -> ContextDeeplinkResponse:
    return ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow these steps to perform this Screen Damage Troubleshooting",
                title="Screen display damage",
                score=0.95,
                actions=[
                    Action(
                        actionName="Back Up Phone Data",
                        description="It will facilitate secure data transfer",
                        category=actionCategory.auto,
                        stepGroups=[
                            StepGroup(
                                steps=[
                                    "Navigate to and open Settings.",
                                    "Tap on Accounts and backup.",
                                    "Select Back up data to secure files.",
                                ],
                                actionableDeeplink=Deeplink(
                                    deeplink="bixby://masked/act/aa73a35e8d",
                                    description="Switches between 12-hour and 24-hour format.",
                                    message="Switch Time Format",
                                ),
                                validationDeeplink=ValidationDeepLink(
                                    deeplink="bixby://masked/val/ef6814259a",
                                    key="Use 24-hour format",
                                ),
                            )
                        ],
                    ),
                    Action(
                        actionName="Schedule Screen Repair Service",
                        description="It will assist locating service center",
                        category=actionCategory.manual,
                        stepGroups=[
                            StepGroup(
                                steps=[
                                    "Visit an authorized Samsung Service Center.",
                                    "Present device to customer support technician.",
                                ],
                                actionableDeeplink=None,
                                validationDeeplink=None,
                            )
                        ],
                    ),
                ],
            )
        ]
    )


# --- 1. Positive Validation ---

def test_valid_response_passes():
    resp = _build_valid_response()
    result = validate_response(resp)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_fallback_dummy_positive_allowed_on_auto():
    resp = _build_valid_response()
    resp.contexts[0].actions[0].stepGroups[0].actionableDeeplink = Deeplink(
        deeplink="bixby://dummy_positive",
        description="Opens relevant device screen safely",
    )
    result = validate_response(resp)
    assert result.is_valid is True


# --- 2. URL Leakage Detection (Gate G5) ---

def test_url_leakage_detection():
    # External URLs and domains must be detected
    assert len(detect_url_leakage("Visit https://support.samsung.com for help.")) > 0
    assert len(detect_url_leakage("Check www.samsung.com/support today.")) > 0
    assert len(detect_url_leakage("Go to google.com/search to read manuals.")) > 0
    assert len(detect_url_leakage("See [guide](http://example.com/guide).")) > 0
    assert len(detect_url_leakage("Click <a href='https://bad.link'>here</a>.")) > 0
    assert len(detect_url_leakage("Look at ![diagram](image.png).")) > 0

    # Internal bixby URIs and package names must NOT be flagged
    assert len(detect_url_leakage("Open bixby://masked/act/aa73a35e8d now.")) == 0
    assert len(detect_url_leakage("Use com.android.settings on your Galaxy.")) == 0
    assert len(detect_url_leakage("Navigate to Settings. Tap Display.")) == 0


def test_validator_fails_on_url_in_steps():
    resp = _build_valid_response()
    resp.contexts[0].actions[0].stepGroups[0].steps.append(
        "Visit https://samsung.com/support for more info."
    )
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("Gate G5 violation" in err for err in result.errors)


# --- 3. Format Rules (A1 Rubric) ---

def test_invalid_goal_format():
    resp = _build_valid_response()
    resp.contexts[0].goal = "How to troubleshoot screen damage on Samsung"
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("violates required format" in err for err in result.errors)


def test_invalid_title_word_count():
    resp = _build_valid_response()
    # 1 word (too short)
    resp.contexts[0].title = "Damage"
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("must be exactly 2–3 words" in err for err in result.errors)

    # 4 words (too long)
    resp.contexts[0].title = "Complete mobile screen damage"
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("must be exactly 2–3 words" in err for err in result.errors)


def test_invalid_description_prefix_and_length():
    resp = _build_valid_response()

    # Missing "It will" prefix
    resp.contexts[0].actions[0].description = "This helps back up your data"
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("must start with 'It will'" in err for err in result.errors)

    # Starts with "It will" but only 4 words (< 5)
    resp.contexts[0].actions[0].description = "It will help you"
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("must be exactly 5–7 words" in err for err in result.errors)

    # Starts with "It will" but 8 words (> 7)
    resp.contexts[0].actions[0].description = "It will help you back up all your data"
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("must be exactly 5–7 words" in err for err in result.errors)


def test_invalid_score_range():
    resp = _build_valid_response()
    resp.contexts[0].score = 1.2
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("out of valid range" in err for err in result.errors)


# --- 4. Deeplink & Category Validations (A2 Rubric) ---

def test_auto_action_lacking_deeplink_fails():
    resp = _build_valid_response()
    # Remove deeplink on auto action
    resp.contexts[0].actions[0].stepGroups[0].actionableDeeplink = None
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("lacks an actionableDeeplink" in err for err in result.errors)


def test_hallucinated_deeplink_fails():
    resp = _build_valid_response()
    resp.contexts[0].actions[0].stepGroups[0].actionableDeeplink = Deeplink(
        deeplink="bixby://masked/act/invented_hash_12345",
        description="Fake invented deeplink description here",
    )
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("does not exist in catalog" in err for err in result.errors)


def test_empty_contexts_or_steps_fails():
    resp = ContextDeeplinkResponse(contexts=[])
    result = validate_response(resp)
    assert result.is_valid is False
    assert any("contexts list must not be empty" in err for err in result.errors)
