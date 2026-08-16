"""Task lifecycle policy tests."""

import unittest

from alfred.domain.constants import CompletionStatus, LifecyclePhase, RunStatus, TaskStatus
from alfred.domain.state_machine import (
    COMPLETION_RUN_STATUS,
    COMPLETION_TASK_STATUS,
    TransitionError,
    can_transition,
    can_transition_phase,
    normalize_completion_status,
    require_transition,
)


class StateMachineTests(unittest.TestCase):
    def test_same_status_is_idempotent(self) -> None:
        self.assertTrue(can_transition(TaskStatus.PENDING, TaskStatus.PENDING))

    def test_valid_review_flow(self) -> None:
        self.assertTrue(can_transition(TaskStatus.RUNNING, TaskStatus.IN_REVIEW))
        self.assertTrue(can_transition(TaskStatus.IN_REVIEW, TaskStatus.COMPLETED))

    def test_terminal_status_cannot_reopen_implicitly(self) -> None:
        with self.assertRaisesRegex(TransitionError, "cannot transition"):
            require_transition(TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS)

    def test_phase_flow_is_explicit(self) -> None:
        self.assertTrue(
            can_transition_phase(LifecyclePhase.ACTIVE, LifecyclePhase.TESTING_DEPLOYMENT)
        )
        self.assertFalse(can_transition_phase(LifecyclePhase.ACTIVE, LifecyclePhase.ARCHIVED))

    def test_completion_status_has_one_canonical_mapping(self) -> None:
        self.assertEqual(normalize_completion_status("failure"), CompletionStatus.FAILED)
        self.assertEqual(COMPLETION_TASK_STATUS[CompletionStatus.FAILED], TaskStatus.IN_PROGRESS)
        self.assertEqual(COMPLETION_RUN_STATUS[CompletionStatus.FAILED], RunStatus.FAILED)
        self.assertEqual(COMPLETION_TASK_STATUS[CompletionStatus.BLOCKED], TaskStatus.BLOCKED)


if __name__ == "__main__":
    unittest.main()
