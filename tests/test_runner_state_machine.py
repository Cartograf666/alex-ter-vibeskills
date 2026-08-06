import unittest
from vibeskills_runner.state_machine import check_transition, get_allowed_next_states
from vibeskills_runner.errors import StateMachineError


class TestRunnerStateMachine(unittest.TestCase):
    def test_valid_transitions(self) -> None:
        # All sequential happy path transitions should succeed
        check_transition("START", "DISCOVER")
        check_transition("DISCOVER", "SPECIFY")
        check_transition("SPECIFY", "PLAN")
        check_transition("PLAN", "TEST_DESIGN")
        check_transition("TEST_DESIGN", "IMPLEMENT")
        check_transition("IMPLEMENT", "VERIFY")
        check_transition("VERIFY", "REVIEW")
        check_transition("REVIEW", "ACCEPT")
        check_transition("ACCEPT", "COMPLETE")

    def test_repair_cycles(self) -> None:
        check_transition("VERIFY", "REPAIR")
        check_transition("REPAIR", "IMPLEMENT")
        check_transition("REVIEW", "REPAIR")

    def test_escalate_transitions(self) -> None:
        check_transition("DISCOVER", "ESCALATE")
        check_transition("SPECIFY", "ESCALATE")
        check_transition("PLAN", "ESCALATE")
        check_transition("IMPLEMENT", "ESCALATE")
        check_transition("VERIFY", "ESCALATE")
        check_transition("REPAIR", "ESCALATE")
        check_transition("REVIEW", "ESCALATE")
        check_transition("ESCALATE", "COMPLETE")

    def test_invalid_transitions(self) -> None:
        with self.assertRaises(StateMachineError):
            check_transition("START", "PLAN")  # skip DISCOVER/SPECIFY
        with self.assertRaises(StateMachineError):
            check_transition("COMPLETE", "DISCOVER")  # transition out of COMPLETE
        with self.assertRaises(StateMachineError):
            check_transition("DISCOVER", "IMPLEMENT")  # skip SPECIFY/PLAN
        with self.assertRaises(StateMachineError):
            check_transition("PLAN", "IMPLEMENT")  # bypassed TEST_DESIGN
        with self.assertRaises(StateMachineError):
            check_transition("REPAIR", "VERIFY")  # bypassed IMPLEMENT
        with self.assertRaises(StateMachineError):
            check_transition("ACCEPT", "ESCALATE")  # cannot escalate from ACCEPT

    def test_unknown_states(self) -> None:
        with self.assertRaises(StateMachineError):
            check_transition("UNKNOWN", "DISCOVER")
        with self.assertRaises(StateMachineError):
            check_transition("START", "UNKNOWN")

    def test_get_allowed_next_states(self) -> None:
        self.assertEqual(get_allowed_next_states("START"), {"DISCOVER"})
        self.assertEqual(get_allowed_next_states("ACCEPT"), {"COMPLETE"})
        self.assertEqual(get_allowed_next_states("PLAN"), {"TEST_DESIGN", "ESCALATE"})
        with self.assertRaises(StateMachineError):
            get_allowed_next_states("INVALID_STATE")
