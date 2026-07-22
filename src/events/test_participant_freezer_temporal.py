import unittest

from src.events.participant_freezer import ParticipantFreezer


class ParticipantFreezerTemporalTests(unittest.TestCase):
    def test_stable_roster_requires_both_cards(self):
        freezer = ParticipantFreezer()

        seat = "seat_top"
        freezer.positive_frames[seat]["card_1"] = 4
        freezer.positive_frames[seat]["card_2"] = 0
        freezer.paired_positive_frames[seat] = 0

        stable = freezer.stable_dealt_in_seats()

        self.assertNotIn(seat, stable)
        self.assertIn("hero", stable)

    def test_stable_roster_requires_temporal_support(self):
        freezer = ParticipantFreezer()

        seat = "seat_top"
        freezer.positive_frames[seat]["card_1"] = 1
        freezer.positive_frames[seat]["card_2"] = 1
        freezer.paired_positive_frames[seat] = 1

        stable = freezer.stable_dealt_in_seats()

        self.assertNotIn(seat, stable)

    def test_stable_roster_accepts_repeated_two_card_evidence(self):
        freezer = ParticipantFreezer()

        seat = "seat_top"
        freezer.positive_frames[seat]["card_1"] = 3
        freezer.positive_frames[seat]["card_2"] = 2
        freezer.paired_positive_frames[seat] = 1

        stable = freezer.stable_dealt_in_seats()

        self.assertIn(seat, stable)

    def test_snapshot_contains_shadow_telemetry(self):
        freezer = ParticipantFreezer()
        freezer.positive_frames["seat_top"]["card_1"] = 2
        freezer.positive_frames["seat_top"]["card_2"] = 2
        freezer.paired_positive_frames["seat_top"] = 2

        snapshot = freezer.snapshot()

        self.assertIn("stable_dealt_in_seats", snapshot)
        self.assertIn("positive_frames", snapshot)
        self.assertIn("paired_positive_frames", snapshot)
        self.assertIn(
            "seat_top",
            snapshot["stable_dealt_in_seats"],
        )

    def test_restore_preserves_shadow_telemetry(self):
        original = ParticipantFreezer()
        original.frame_count = 7
        original.positive_frames["seat_top"]["card_1"] = 5
        original.positive_frames["seat_top"]["card_2"] = 4
        original.paired_positive_frames["seat_top"] = 3

        restored = ParticipantFreezer.from_evidence(
            original.snapshot()
        )

        self.assertEqual(restored.frame_count, 7)
        self.assertEqual(
            restored.positive_frames["seat_top"]["card_1"],
            5,
        )
        self.assertEqual(
            restored.positive_frames["seat_top"]["card_2"],
            4,
        )
        self.assertEqual(
            restored.paired_positive_frames["seat_top"],
            3,
        )


if __name__ == "__main__":
    unittest.main()
