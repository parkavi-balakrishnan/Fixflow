"""Deterministic Action Ordering Engine for FixFlow.

Enforces Samsung's disruptive-impact ordering hierarchy:
1. Least disruptive (auto / Settings configuration) first
2. Non-automated (manual / physical interventions) next
3. Highly disruptive / safety-critical operations (restart, reset, safe mode) LAST

Preserves relative ordering within the same category (stable sort).
"""
import re
from typing import List, Sequence

from src.schema import Action, ContextDeeplinkResponse, Goal, actionCategory

# Regex patterns matching disruptive or irreversible device operations
DISRUPTIVE_ACTION_PATTERNS = [
    r"\bfactory\s+reset\b",
    r"\bmaster\s+reset\b",
    r"\bhard\s+reset\b",
    r"\bwipe\s+(data|cache)\b",
    r"\brestart\b",
    r"\breboot\b",
    r"\bsafe\s+mode\b",
    r"\breset\s+(all\s+settings|network\s+settings)\b",
    r"\bfirmware\s+update\b",
    r"\bsoftware\s+update\b",
]

_COMPILED_DISRUPTIVE_REGEX = re.compile(
    "|".join(DISRUPTIVE_ACTION_PATTERNS), re.IGNORECASE
)

# Priority weights (lower number = earlier in execution order)
PRIORITY_AUTO = 10
PRIORITY_MANUAL = 20
PRIORITY_CRITICAL = 30


def is_disruptive_action(action: Action) -> bool:
    """Checks whether an action represents a disruptive or safety-critical operation."""
    if action.category == actionCategory.critical:
        return True

    text_to_scan = [action.actionName, action.description]
    for sg in action.stepGroups:
        text_to_scan.extend(sg.steps)

    combined_text = " ".join(text_to_scan)
    return bool(_COMPILED_DISRUPTIVE_REGEX.search(combined_text))


def get_action_priority(action: Action) -> int:
    """Returns the sorting priority weight for an action.
    
    Guarantees:
    - Auto (non-critical): 10
    - Manual (non-critical): 20
    - Critical (explicit or detected disruptive): 30
    """
    if is_disruptive_action(action):
        return PRIORITY_CRITICAL

    if action.category == actionCategory.auto:
        return PRIORITY_AUTO

    return PRIORITY_MANUAL


def order_actions(actions: Sequence[Action]) -> List[Action]:
    """Sorts actions deterministically from least disruptive to most disruptive.
    
    Order:
      1. Auto actions (Settings configuration)
      2. Manual actions (Physical interventions, external steps)
      3. Critical actions (Restart, safe mode, factory reset, etc.)
      
    Guarantees:
      - Uses Python's stable sort (Timsort) to preserve original relative order
        among actions with equal priority.
      - Discovered disruptive actions have their category marked as critical.
    """
    if not actions:
        return []

    def _sort_key(item: Action) -> int:
        priority = get_action_priority(item)
        if priority == PRIORITY_CRITICAL and item.category != actionCategory.critical:
            # Upgrade category to critical if detected as disruptive
            item.category = actionCategory.critical
        return priority

    return sorted(actions, key=_sort_key)


def order_goal(goal: Goal) -> Goal:
    """Orders the actions within a single Goal in-place and returns the Goal."""
    goal.actions = order_actions(goal.actions)
    return goal


def order_response(response: ContextDeeplinkResponse) -> ContextDeeplinkResponse:
    """Orders the actions within all Goals of a ContextDeeplinkResponse."""
    for goal in response.contexts:
        goal.actions = order_actions(goal.actions)
    return response
