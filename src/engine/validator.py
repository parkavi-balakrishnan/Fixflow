r"""Deterministic Rule and Schema Validator for FixFlow.

Enforces Samsung PRISM Theme 2 constraints:
- Pydantic schema validation against official schema.py
- Gate G5: Zero URL / external link leakage detection
- Format rules (A1):
    - Goal format: ^Follow these steps to perform this .+ (Troubleshooting|Configuration)\.?$
    - Title: Exactly 2–3 words
    - Description: Exactly 5–7 words and must start with "It will"
    - Score: Float between 0.0 and 1.0
    - Non-empty actions and imperative steps
- Deeplink validity & consistency (A2):
    - Auto actions MUST have an actionable deeplink
    - Deeplinks must exist in the 578 catalog or equal mandated fallback bixby://dummy_positive
    - Validation deeplinks must exist in catalog validation entries
    - No invented or modified URIs
"""
from dataclasses import dataclass, field
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import ValidationError

from src.schema import Action, ContextDeeplinkResponse, Goal, actionCategory

# Official Goal regex requirement
GOAL_REGEX = re.compile(
    r"^Follow these steps to perform this .+ (Troubleshooting|Configuration)\.?$",
    re.IGNORECASE,
)

# URL / link leakage patterns (Gate G5)
# Designed to detect actual URLs, domains, and markup links while avoiding
# false positives on Android package namespaces (e.g. com.android.settings)
# and internal bixby:// deeplinks.
URL_LEAK_PATTERNS = [
    # Explicit web schemes
    r"\b(?:https?|ftp)://[^\s<>'\"]+",
    # www. prefixed hostnames
    r"\bwww\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s<>'\"]*)?",
    # Common external web domains (excluding reverse-DNS Android packages like com.android.*)
    r"(?<![a-zA-Z0-9_.])(?!(?:com|org|net)\.[a-zA-Z0-9_]+\.)[a-zA-Z0-9-]+\.(?:com|org|net|io|edu|gov|co\.kr|co\.uk)(?:/[^\s<>'\"]*)?",
    # Markdown links: [text](url)
    r"\[[^\]]+\]\((?!(?:bixby)://)[^\)]+\)",
    # Markdown images: ![alt](url)
    r"!\[[^\]]*\]\([^\)]+\)",
    # HTML anchor tags: <a href="...">
    r"<\s*a\b[^>]*href=[^>]*>",
]

_COMPILED_URL_REGEX = re.compile("|".join(URL_LEAK_PATTERNS), re.IGNORECASE)

DEFAULT_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "deeplinks.json",
)


@dataclass
class ValidationResult:
    """Structured report of response validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_response: Optional[ContextDeeplinkResponse] = None


class DeeplinkCatalogIndex:
    """In-memory index of official Samsung Settings deeplinks."""

    def __init__(self, catalog_path: str = DEFAULT_CATALOG_PATH):
        self.catalog_path = catalog_path
        self.actionable_uris: Set[str] = set()
        self.validation_uris: Set[str] = set()
        self.catalog_loaded = False
        self._load_catalog()

    def _load_catalog(self) -> None:
        if not os.path.exists(self.catalog_path):
            return

        with open(self.catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        deeplinks = data.get("deeplinks", [])
        for item in deeplinks:
            uri = item.get("deeplink")
            if uri:
                self.actionable_uris.add(uri)
            val = item.get("validation")
            if isinstance(val, dict) and val.get("deeplink"):
                self.validation_uris.add(val.get("deeplink"))

        # Official mandated fallback
        self.actionable_uris.add("bixby://dummy_positive")
        self.catalog_loaded = True

    def is_valid_actionable_uri(self, uri: str) -> bool:
        """Checks if actionable deeplink URI is in the official catalog or fallback."""
        if not self.catalog_loaded:
            # Fallback if catalog not present: ensure valid scheme
            return uri.startswith("bixby://")
        return uri in self.actionable_uris

    def is_valid_validation_uri(self, uri: str) -> bool:
        """Checks if validation deeplink URI is in the official catalog."""
        if not self.catalog_loaded:
            return uri.startswith("bixby://")
        return uri in self.validation_uris


# Default shared catalog index instance
_DEFAULT_CATALOG_INDEX: Optional[DeeplinkCatalogIndex] = None


def get_default_catalog_index() -> DeeplinkCatalogIndex:
    global _DEFAULT_CATALOG_INDEX
    if _DEFAULT_CATALOG_INDEX is None:
        _DEFAULT_CATALOG_INDEX = DeeplinkCatalogIndex()
    return _DEFAULT_CATALOG_INDEX


def detect_url_leakage(text: str) -> List[str]:
    """Finds any external URLs or link markups in the provided text.
    
    Ignores internal bixby:// URIs.
    """
    if not text:
        return []
    matches = _COMPILED_URL_REGEX.findall(text)
    # Filter out empty or whitespace matches
    return [m for m in matches if m.strip()]


class ResponseValidator:
    """Validates responses against all Samsung hackathon gates and rubric rules."""

    def __init__(self, catalog_index: Optional[DeeplinkCatalogIndex] = None):
        self.catalog = catalog_index or get_default_catalog_index()

    def validate(
        self, response: Union[Dict[str, Any], ContextDeeplinkResponse]
    ) -> ValidationResult:
        """Validates a raw response dict or ContextDeeplinkResponse object.
        
        Returns a ValidationResult with is_valid=True only if ALL gates and
        rules pass.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Pydantic Schema Validation
        model_obj: Optional[ContextDeeplinkResponse] = None
        if isinstance(response, ContextDeeplinkResponse):
            model_obj = response
        elif isinstance(response, dict):
            try:
                model_obj = ContextDeeplinkResponse.model_validate(response)
            except ValidationError as e:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Pydantic schema validation error: {str(e)}"],
                    warnings=[],
                    validated_response=None,
                )
            except Exception as e:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Unexpected error parsing response schema: {str(e)}"],
                    warnings=[],
                    validated_response=None,
                )
        else:
            return ValidationResult(
                is_valid=False,
                errors=[f"Expected dict or ContextDeeplinkResponse, got {type(response).__name__}"],
                warnings=[],
                validated_response=None,
            )

        # 2. Top-level contexts validation
        if not model_obj.contexts:
            errors.append("Response contexts list must not be empty.")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                validated_response=model_obj,
            )

        # 3. Deep inspection of Goals, Actions, and StepGroups
        for g_idx, goal in enumerate(model_obj.contexts):
            self._validate_goal(g_idx, goal, errors, warnings)

        return ValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            validated_response=model_obj,
        )

    def _validate_goal(
        self,
        g_idx: int,
        goal: Goal,
        errors: List[str],
        warnings: List[str],
    ) -> None:
        loc = f"Goal[{g_idx}]"

        # Goal format regex validation
        if not goal.goal or not GOAL_REGEX.match(goal.goal.strip()):
            errors.append(
                f"{loc}.goal '{goal.goal}' violates required format: "
                "Must match 'Follow these steps to perform this <Name> Troubleshooting' "
                "or 'Follow these steps to perform this <Name> Configuration'."
            )
        self._check_url_leaks(f"{loc}.goal", goal.goal, errors)

        # Title word count validation (2-3 words)
        title_words = goal.title.strip().split() if goal.title else []
        if len(title_words) < 2 or len(title_words) > 3:
            errors.append(
                f"{loc}.title '{goal.title}' has {len(title_words)} words; must be exactly 2–3 words."
            )
        self._check_url_leaks(f"{loc}.title", goal.title, errors)

        # Score validation (0.0 to 1.0)
        if goal.score is None or not (0.0 <= goal.score <= 1.0):
            errors.append(
                f"{loc}.score {goal.score} is out of valid range [0.0, 1.0]."
            )

        # Actions validation
        if not goal.actions:
            errors.append(f"{loc}.actions must contain at least one Action.")
            return

        for a_idx, action in enumerate(goal.actions):
            self._validate_action(g_idx, a_idx, action, errors, warnings)

    def _validate_action(
        self,
        g_idx: int,
        a_idx: int,
        action: Action,
        errors: List[str],
        warnings: List[str],
    ) -> None:
        loc = f"Goal[{g_idx}].Action[{a_idx}]"

        # ActionName validation
        if not action.actionName or not action.actionName.strip():
            errors.append(f"{loc}.actionName must not be empty.")
        self._check_url_leaks(f"{loc}.actionName", action.actionName, errors)

        # Description validation: exactly 5-7 words, starts with "It will"
        desc = action.description.strip() if action.description else ""
        if not desc.startswith("It will"):
            errors.append(
                f"{loc}.description '{desc}' must start with 'It will'."
            )
        desc_words = desc.split()
        if len(desc_words) < 5 or len(desc_words) > 7:
            errors.append(
                f"{loc}.description '{desc}' has {len(desc_words)} words; must be exactly 5–7 words."
            )
        self._check_url_leaks(f"{loc}.description", desc, errors)

        # Category and StepGroups validation
        if not action.stepGroups:
            errors.append(f"{loc}.stepGroups must contain at least one StepGroup.")
            return

        for sg_idx, sg in enumerate(action.stepGroups):
            sg_loc = f"{loc}.StepGroup[{sg_idx}]"

            # Steps validation: non-empty list of non-empty strings
            if not sg.steps:
                errors.append(f"{sg_loc}.steps must contain at least one step instruction.")
            else:
                for s_idx, step in enumerate(sg.steps):
                    if not step or not step.strip():
                        errors.append(f"{sg_loc}.steps[{s_idx}] is empty.")
                    self._check_url_leaks(f"{sg_loc}.steps[{s_idx}]", step, errors)

            # Actionable Deeplink validation
            act_dl = sg.actionableDeeplink
            if action.category == actionCategory.auto:
                if act_dl is None or not act_dl.deeplink:
                    errors.append(
                        f"{sg_loc}: Action is categorized as 'auto' but lacks an actionableDeeplink."
                    )
                else:
                    self._validate_actionable_deeplink(sg_loc, act_dl, errors)
            elif act_dl is not None:
                # If present on manual/critical, still validate URI integrity
                self._validate_actionable_deeplink(sg_loc, act_dl, errors)

            # Validation Deeplink validation
            val_dl = sg.validationDeeplink
            if val_dl is not None and val_dl.deeplink:
                self._validate_validation_deeplink(sg_loc, val_dl, errors)

    def _validate_actionable_deeplink(
        self, loc: str, dl: Any, errors: List[str]
    ) -> None:
        uri = dl.deeplink.strip() if getattr(dl, "deeplink", None) else ""
        if not uri:
            errors.append(f"{loc}.actionableDeeplink has empty URI.")
            return

        if not self.catalog.is_valid_actionable_uri(uri):
            errors.append(
                f"{loc}.actionableDeeplink.deeplink '{uri}' does not exist in catalog "
                "and is not the mandated fallback (bixby://dummy_positive)."
            )

        if getattr(dl, "description", None):
            self._check_url_leaks(f"{loc}.actionableDeeplink.description", dl.description, errors)
        if getattr(dl, "message", None):
            self._check_url_leaks(f"{loc}.actionableDeeplink.message", dl.message, errors)

    def _validate_validation_deeplink(
        self, loc: str, val_dl: Any, errors: List[str]
    ) -> None:
        uri = val_dl.deeplink.strip() if getattr(val_dl, "deeplink", None) else ""
        if not uri:
            errors.append(f"{loc}.validationDeeplink has empty URI.")
            return

        if not self.catalog.is_valid_validation_uri(uri):
            errors.append(
                f"{loc}.validationDeeplink.deeplink '{uri}' does not exist in catalog validation entries."
            )

        if getattr(val_dl, "key", None):
            self._check_url_leaks(f"{loc}.validationDeeplink.key", val_dl.key, errors)
        if getattr(val_dl, "value", None):
            self._check_url_leaks(f"{loc}.validationDeeplink.value", str(val_dl.value), errors)

    def _check_url_leaks(self, loc: str, text: Optional[str], errors: List[str]) -> None:
        if not text:
            return
        leaks = detect_url_leakage(text)
        if leaks:
            errors.append(
                f"Gate G5 violation at {loc}: detected URL/link leak: {leaks}"
            )


def validate_response(
    response: Union[Dict[str, Any], ContextDeeplinkResponse],
    catalog_path: Optional[str] = None,
) -> ValidationResult:
    """Convenience helper to validate a response dictionary or model instance."""
    catalog = DeeplinkCatalogIndex(catalog_path) if catalog_path else get_default_catalog_index()
    validator = ResponseValidator(catalog)
    return validator.validate(response)
