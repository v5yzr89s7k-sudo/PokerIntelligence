import unittest

from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)


class StreetCommitmentTrackerCompletionTests(unittest.TestCase):
    def setUp(self):
        self.tracker = StreetCommitmentTracker()
        self.street = "FLOP"
        self.order = [
            "seat_a",
            "seat_b",
            "seat_c",
        ]

        self.tracker.initialize_street_order(
            self.street,
            self.order,
        )

    def test_unopened_round_is_incomplete_while_queue_remains(self):
        self.tracker.sync_queue(
            self.street,
            ["seat_b", "seat_c"],
        )

        self.assertEqual(
            self.tracker.players_owing_action(self.street),
            ["seat_b", "seat_c"],
        )
        self.assertFalse(
            self.tracker.is_round_complete(self.street)
        )

        status = self.tracker.round_status(self.street)

        self.assertFalse(status["complete"])
        self.assertIn(
            "remain in the street action queue",
            status["reason"],
        )

    def test_check_around_completes_when_queue_is_empty(self):
        self.tracker.sync_queue(self.street, [])

        self.assertTrue(
            self.tracker.is_round_complete(self.street)
        )

        status = self.tracker.round_status(self.street)

        self.assertTrue(status["complete"])
        self.assertEqual(
            status["reason"],
            "street action queue is complete",
        )

    def test_open_bet_requires_every_response(self):
        self.tracker.open_response_queue(
            self.street,
            aggressor="seat_a",
            eligible_seats=self.order,
        )
        self.tracker.record_action(
            self.street,
            "seat_a",
            current_price=4.0,
            last_aggressor="seat_a",
            betting_open=True,
        )

        self.assertEqual(
            self.tracker.players_owing_action(self.street),
            ["seat_b", "seat_c"],
        )
        self.assertFalse(
            self.tracker.is_round_complete(self.street)
        )

        self.tracker.record_response(
            self.street,
            "seat_b",
        )

        self.assertEqual(
            self.tracker.players_owing_action(self.street),
            ["seat_c"],
        )
        self.assertFalse(
            self.tracker.is_round_complete(self.street)
        )

        self.tracker.record_response(
            self.street,
            "seat_c",
        )

        self.assertEqual(
            self.tracker.players_owing_action(self.street),
            [],
        )
        self.assertTrue(
            self.tracker.is_round_complete(self.street)
        )

    def test_raise_rebuilds_response_obligations(self):
        self.tracker.open_response_queue(
            self.street,
            aggressor="seat_a",
            eligible_seats=self.order,
        )
        self.tracker.record_action(
            self.street,
            "seat_a",
            current_price=3.0,
            last_aggressor="seat_a",
            betting_open=True,
        )

        self.tracker.record_response(
            self.street,
            "seat_b",
        )

        # seat_c raises, reopening action for seat_a and seat_b.
        reopened = self.tracker.open_response_queue(
            self.street,
            aggressor="seat_c",
            eligible_seats=self.order,
        )
        self.tracker.record_action(
            self.street,
            "seat_c",
            current_price=8.0,
            last_aggressor="seat_c",
            betting_open=True,
        )

        self.assertEqual(
            reopened,
            ["seat_a", "seat_b"],
        )
        self.assertEqual(
            self.tracker.players_owing_action(self.street),
            ["seat_a", "seat_b"],
        )
        self.assertFalse(
            self.tracker.is_round_complete(self.street)
        )

    def test_uninitialized_street_is_not_complete(self):
        tracker = StreetCommitmentTracker()

        self.assertFalse(
            tracker.is_round_complete("TURN")
        )

        status = tracker.round_status("TURN")

        self.assertFalse(status["complete"])
        self.assertEqual(
            status["reason"],
            "street action order is not initialized",
        )

    def test_status_is_exposed_in_serialized_state(self):
        self.tracker.sync_queue(
            self.street,
            ["seat_c"],
        )

        payload = self.tracker.to_dict()[self.street]

        self.assertFalse(payload["round_complete"])
        self.assertEqual(
            payload["players_owing_action"],
            ["seat_c"],
        )
        self.assertEqual(
            payload["round_status"]["street"],
            self.street,
        )


if __name__ == "__main__":
    unittest.main()
