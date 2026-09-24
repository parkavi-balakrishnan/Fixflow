"""Unit tests for src/engine/ordering.py."""
import pytest

from src.engine.ordering import (
    get_action_priority,
    is_disruptive_action,
    order_actions,
    order_goal,
    order_response,
)
from src.schema import (
    Action,
    ContextDeeplinkResponse,
    Deeplink,
    Goal,
    StepGroup,
    actionCategory,
)


def _make_action(name: str, category: actionCategory, steps=None) -> Action:
    return Action(
        actionName=name,
        description="It will configure device settings safely",
        category=category,
        stepGroups=[
            StepGroup(
                steps=steps or ["Tap Settings."],
                actionableDeeplink=Deeplink(
                    deeplink="bixby://masked/act/aa73a35e8d",
                    description="Opens settings",
                )
                if category == actionCategory.auto
                else None,
            )
        ],
    )


def test_basic_ordering_auto_manual_critical():
    a_crit = _make_action("Critical Operation", actionCategory.critical)
    a_man = _make_action("Clean Charging Port", actionCategory.manual)
    a_auto = _make_action("Adjust Display Brightness", actionCategory.auto)

    # Initial order: critical, manual, auto
    ordered = order_actions([a_crit, a_man, a_auto])

    assert len(ordered) == 3
    assert ordered[0].actionName == "Adjust Display Brightness"
    assert ordered[1].actionName == "Clean Charging Port"
    assert ordered[2].actionName == "Critical Operation"


def test_stable_sort_preserves_relative_order_within_tier():
    a1 = _make_action("Auto Action 1", actionCategory.auto)
    a2 = _make_action("Auto Action 2", actionCategory.auto)
    a3 = _make_action("Auto Action 3", actionCategory.auto)
    m1 = _make_action("Manual Action 1", actionCategory.manual)
    m2 = _make_action("Manual Action 2", actionCategory.manual)

    mixed = [m1, a1, a2, m2, a3]
    ordered = order_actions(mixed)

    # All autos must precede manuals, preserving relative internal order
    assert [a.actionName for a in ordered] == [
        "Auto Action 1",
        "Auto Action 2",
        "Auto Action 3",
        "Manual Action 1",
        "Manual Action 2",
    ]


def test_detects_disruptive_action_in_name():
    # Marked as manual, but name is Factory Reset
    reset_action = _make_action("Perform Factory Reset", actionCategory.manual)
    normal_action = _make_action("Inspect Screen Protector", actionCategory.manual)

    assert is_disruptive_action(reset_action) is True
    assert is_disruptive_action(normal_action) is False

    ordered = order_actions([reset_action, normal_action])
    assert ordered[0].actionName == "Inspect Screen Protector"
    assert ordered[1].actionName == "Perform Factory Reset"
    assert ordered[1].category == actionCategory.critical


def test_detects_disruptive_action_in_steps():
    # Marked as manual, name is innocent, but steps say restart
    reboot_action = _make_action(
        "Apply System Changes",
        actionCategory.manual,
        steps=["Hold power button to restart phone."],
    )
    safe_action = _make_action("Check Volume Keys", actionCategory.manual)

    ordered = order_actions([reboot_action, safe_action])
    assert ordered[0].actionName == "Check Volume Keys"
    assert ordered[1].actionName == "Apply System Changes"


def test_order_goal_and_response():
    goal = Goal(
        goal="Follow these steps to perform this Display Troubleshooting",
        title="Screen flicker fix",
        score=0.9,
        actions=[
            _make_action("Safe Mode Reboot", actionCategory.critical),
            _make_action("Toggle Auto Brightness", actionCategory.auto),
        ],
    )
    resp = ContextDeeplinkResponse(contexts=[goal])

    ordered_resp = order_response(resp)
    assert ordered_resp.contexts[0].actions[0].actionName == "Toggle Auto Brightness"
    assert ordered_resp.contexts[0].actions[1].actionName == "Safe Mode Reboot"


def test_empty_actions():
    assert order_actions([]) == []
