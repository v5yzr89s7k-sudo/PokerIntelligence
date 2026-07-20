from src.observer.action_inference_engine import (
    InferredAction,
    BET_OR_RAISE,
)
from src.state.betting_round_tracker import BettingRoundTracker
from src.state.canonical_hand import CanonicalHand


def inferred(
    episode_id,
    seat,
    action,
    street="PREFLOP",
):
    return InferredAction(
        episode_id=episode_id,
        seat=seat,
        street=street,
        action=action,
        confidence=0.9,
        evidence=[],
        reason="test",
        measurements={},
    )


def make_hand():
    return CanonicalHand().start_hand(
        hand_id="street-order-test",
        players=[
            {
                "seat": "seat_top",
                "name": "UTG",
                "stack_bb": 30,
            },
            {
                "seat": "seat_upper_right",
                "name": "HJ",
                "stack_bb": 30,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 30,
                "is_hero": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions={
            "seat_top": "UTG",
            "seat_upper_right": "HJ",
            "hero": "BTN",
        },
        started_ts=1000.0,
    )


def test_preflop_street_order_survives_queue_consumption():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    state = tracker.commitment_tracker._state("PREFLOP")

    assert state.street_order == [
        "seat_top",
        "seat_upper_right",
        "hero",
    ]

    tracker.ingest(
        inferred(
            1,
            "seat_upper_right",
            BET_OR_RAISE,
        )
    )

    assert hand.players_to_act == [
        "hero",
    ]

    assert state.pending_to_act == [
        "hero",
    ]

    assert state.street_order == [
        "seat_top",
        "seat_upper_right",
        "hero",
    ]


def test_street_order_initializes_once():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    state = tracker.commitment_tracker._state("PREFLOP")
    original = list(state.street_order)

    tracker.commitment_tracker.initialize_street_order(
        "PREFLOP",
        ["different", "order"],
    )

    assert state.street_order == original


def test_postflop_street_order_uses_new_canonical_queue():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    hand.set_board(["Ah", "7c", "2d"])

    expected = list(hand.players_to_act)

    tracker.ingest(
        inferred(
            1,
            expected[0],
            BET_OR_RAISE,
            street="FLOP",
        )
    )

    state = tracker.commitment_tracker._state("FLOP")

    assert state.street_order == expected
    assert state.pending_to_act == hand.players_to_act


if __name__ == "__main__":
    test_preflop_street_order_survives_queue_consumption()
    test_street_order_initializes_once()
    test_postflop_street_order_uses_new_canonical_queue()

    print("Street order regression tests passed.")
