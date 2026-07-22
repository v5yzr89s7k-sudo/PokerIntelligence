import unittest

from src.api.stack_transition_validator import (
    ACCEPT,
    REJECT,
    RETRY,
    validate_stack_transition,
)


class StackTransitionValidatorTests(unittest.TestCase):
    def test_known_decimal_collapse_is_not_accepted(self):
        result = validate_stack_transition(
            20.12,
            2.00,
            confidence=0.95,
            votes=2,
            phase="FLOP",
            has_commitment_evidence=False,
        )

        self.assertEqual(result.decision, RETRY)
        self.assertEqual(
            result.reason,
            "large_commitment_without_evidence",
        )
        self.assertAlmostEqual(result.delta_bb, 18.12)
        self.assertTrue(result.large_commitment)

    def test_normal_commitment_is_accepted(self):
        result = validate_stack_transition(
            20.12,
            17.12,
            confidence=0.98,
            votes=2,
            phase="PREFLOP",
            has_commitment_evidence=False,
        )

        self.assertEqual(result.decision, ACCEPT)
        self.assertAlmostEqual(result.delta_bb, 3.00)
        self.assertFalse(result.large_commitment)

    def test_large_commitment_with_independent_evidence_is_accepted(self):
        result = validate_stack_transition(
            20.12,
            2.00,
            confidence=0.98,
            votes=3,
            phase="FLOP",
            has_commitment_evidence=True,
        )

        self.assertEqual(result.decision, ACCEPT)
        self.assertTrue(result.large_commitment)

    def test_stack_increase_is_rejected(self):
        result = validate_stack_transition(
            17.12,
            20.12,
            confidence=0.99,
            votes=3,
            phase="FLOP",
            has_commitment_evidence=True,
        )

        self.assertEqual(result.decision, REJECT)
        self.assertEqual(result.reason, "stack_increase")

    def test_zero_requires_all_in_confirmation(self):
        result = validate_stack_transition(
            8.00,
            0.00,
            confidence=0.99,
            votes=3,
            phase="TURN",
            has_commitment_evidence=True,
            all_in_confirmed=False,
        )

        self.assertEqual(result.decision, RETRY)
        self.assertEqual(
            result.reason,
            "zero_without_all_in_confirmation",
        )

    def test_confirmed_all_in_zero_is_accepted(self):
        result = validate_stack_transition(
            8.00,
            0.00,
            confidence=0.99,
            votes=3,
            phase="TURN",
            has_commitment_evidence=True,
            all_in_confirmed=True,
        )

        self.assertEqual(result.decision, ACCEPT)


if __name__ == "__main__":
    unittest.main()
