import unittest
from vibeskills_runner.state_machine import check_transition
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
        check_transition("REPAIR", "VERIFY")
        check_transition("REVIEW", "REPAIR")

    def test_escalate_transitions(self) -> None:
        check_transition("DISCOVER", "ESCALATE")
        check_transition("SPECIFY", "ESCALATE")
        check_transition("PLAN", "ESCALATE")
        check_transition("IMPLEMENT", "ESCALATE")
        check_transition("VERIFY", "ESCALATE")
        check_transition("REPAIR", "ESCALATE")
        check_transition("REVIEW", "ESCALATE")
        check_transition("ACCEPT", "ESCALATE")
        check_transition("ESCALATE", "COMPLETE")

    def test_invalid_transitions(self) -> None:
        with self.assertRaises(StateMachineError):
            check_transition("START", "PLAN")  # skip DISCOVER/SPECIFY
        with self.assertRaises(StateMachineError):
            check_transition("COMPLETE", "DISCOVER")  # transition out of COMPLETE
        with self.assertRaises(StateMachineError):
            check_transition("DISCOVER", "IMPLEMENT")  # skip SPECIFY/PLAN

    def test_unknown_states(self) -> None:
        with self.assertRaises(StateMachineError):
            check_transition("UNKNOWN", "DISCOVER")
        with self.assertRaises(StateMachineError):
            check_transition("START", "UNKNOWN")
