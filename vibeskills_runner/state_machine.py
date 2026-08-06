from typing import Set, Dict
from .errors import StateMachineError

STATES = {
    "START", "DISCOVER", "SPECIFY", "PLAN", "TEST_DESIGN", "IMPLEMENT",
    "VERIFY", "REPAIR", "REVIEW", "ACCEPT", "ESCALATE", "COMPLETE"
}

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "START": {"DISCOVER"},
    "DISCOVER": {"SPECIFY", "ESCALATE"},
    "SPECIFY": {"PLAN", "ESCALATE"},
    "PLAN": {"TEST_DESIGN", "ESCALATE"},
    "TEST_DESIGN": {"IMPLEMENT", "ESCALATE"},
    "IMPLEMENT": {"VERIFY", "ESCALATE"},
    "VERIFY": {"REPAIR", "REVIEW", "ESCALATE"},
    "REPAIR": {"IMPLEMENT", "ESCALATE"},
    "REVIEW": {"REPAIR", "ACCEPT", "ESCALATE"},
    "ACCEPT": {"COMPLETE"},
    "ESCALATE": {"COMPLETE"},
}


def check_transition(from_state: str, to_state: str) -> None:
    """Validate if a transition from from_state to to_state is permissible.

    Raises StateMachineError if the transition is invalid.
    """
    if from_state not in STATES:
        raise StateMachineError(f"Unknown state: '{from_state}'")
    if to_state not in STATES:
        raise StateMachineError(f"Unknown state: '{to_state}'")
    if from_state == "COMPLETE":
        raise StateMachineError("Cannot transition out of COMPLETE state.")

    allowed = ALLOWED_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise StateMachineError(
            f"State transition '{from_state}' -> '{to_state}' is not allowed."
        )


def get_allowed_next_states(state: str) -> Set[str]:
    """Retrieve the set of states that can be transitioned to from the given state."""
    if state not in STATES:
        raise StateMachineError(f"Unknown state: '{state}'")
    return ALLOWED_TRANSITIONS.get(state, set())
