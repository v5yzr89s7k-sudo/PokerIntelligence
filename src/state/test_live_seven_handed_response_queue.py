import unittest

from src.observer.action_inference_engine import (
    InferredAction,
    BET_OR_RAISE,
)
from src.state.betting_round_tracker import BettingRoundTracker
from src.state.canonical_hand import CanonicalHand


class LiveSevenHandedResponseQueueTests(unittest.TestCase):
    def test_lj_raise_keeps_hj_co_btn_sb_bb_owing_action(self):
        positions = {
            "seat_lower_right": "UTG",
            "hero": "LJ",
            "seat_lower_left": "HJ",
            "seat_mid_left": "CO",
            "seat_upper_left": "BTN",
            "seat_top": "SB",
            "seat_upper_right": "BB",
        }

        players = [
            {
                "seat": seat,
                "name": position,
                "stack_bb": 100.0,
                "is_hero": seat == "hero",
                "is_active": True,
            }
            for seat, position in positions.items()
        ]

        hand = CanonicalHand().start_hand(
            hand_id="seven-handed-live-shape",
            players=players,
            hero_cards=["Qh", "Kc"],
            hero_position="LJ",
            positions=positions,
            started_ts=1000.0,
        )

        tracker = BettingRoundTracker(hand)

        action = InferredAction(
            episode_id=1,
            seat="hero",
            street="PREFLOP",
            action=BET_OR_RAISE,
            confidence=0.98,
            evidence=["live_shape_regression"],
            reason="hero stack decreased by 2 BB",
            measurements={
                "stack_change": {
                    "delta_bb": 2.0,
                }
            },
        )

        result = tracker.ingest(action)

        self.assertIsNotNone(result)
        self.assertEqual(result.action, "BET")

        # UTG was skipped before Hero and is inferred folded.
        self.assertTrue(
            hand.players["seat_lower_right"].folded
        )

        state = tracker.commitment_tracker._state("PREFLOP")

        self.assertEqual(
            state.street_order,
            [
                "seat_lower_right",
                "hero",
                "seat_lower_left",
                "seat_mid_left",
                "seat_upper_left",
                "seat_top",
                "seat_upper_right",
            ],
        )

        self.assertEqual(
            state.needs_response_from,
            [
                "seat_lower_left",
                "seat_mid_left",
                "seat_upper_left",
                "seat_top",
                "seat_upper_right",
            ],
        )

        self.assertEqual(
            tracker.commitment_tracker.players_owing_action(
                "PREFLOP"
            ),
            [
                "seat_lower_left",
                "seat_mid_left",
                "seat_upper_left",
                "seat_top",
                "seat_upper_right",
            ],
        )


if __name__ == "__main__":
    unittest.main()
