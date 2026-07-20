from src.observer.action_inference_engine import (
    InferredAction,
    BET_OR_RAISE,
    CALL_OR_RAISE,
    CALL,
)
from src.state.betting_round_tracker import BettingRoundTracker
from src.state.canonical_hand import CanonicalHand


def inferred(
    episode_id,
    seat,
    action,
    *,
    street="PREFLOP",
    delta_bb=None,
):
    measurements = {}

    if delta_bb is not None:
        measurements = {
            "stack_change": {
                "delta_bb": delta_bb,
            }
        }

    return InferredAction(
        episode_id=episode_id,
        seat=seat,
        street=street,
        action=action,
        confidence=0.9,
        evidence=[],
        reason="test",
        measurements=measurements,
    )


def make_hand():
    positions = {
        "seat_top": "UTG",
        "seat_upper_right": "HJ",
        "hero": "BTN",
        "seat_mid_left": "SB",
        "seat_upper_left": "BB",
    }

    players = [
        {
            "seat": seat,
            "name": position,
            "stack_bb": 50,
            "is_hero": seat == "hero",
        }
        for seat, position in positions.items()
    ]

    return CanonicalHand().start_hand(
        hand_id="response-queue",
        players=players,
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions=positions,
        started_ts=1000.0,
    )


def test_opening_raise_builds_cyclic_response_queue():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(
            1,
            "seat_upper_right",
            BET_OR_RAISE,
            delta_bb=2.5,
        )
    )

    assert result is not None
    assert result.action == "BET"

    state = tracker.commitment_tracker._state("PREFLOP")

    assert state.needs_response_from == [
        "hero",
        "seat_mid_left",
        "seat_upper_left",
    ]


def test_call_consumes_one_response():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    tracker.ingest(
        inferred(
            1,
            "seat_upper_right",
            BET_OR_RAISE,
            delta_bb=2.5,
        )
    )

    result = tracker.ingest(
        inferred(
            2,
            "hero",
            CALL,
            delta_bb=2.5,
        )
    )

    assert result is not None
    assert result.action == "CALL"

    state = tracker.commitment_tracker._state("PREFLOP")

    assert state.needs_response_from == [
        "seat_mid_left",
        "seat_upper_left",
    ]


def test_reraise_reopens_response_queue_in_cyclic_order():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    tracker.ingest(
        inferred(
            1,
            "seat_upper_right",
            BET_OR_RAISE,
            delta_bb=2.5,
        )
    )

    tracker.ingest(
        inferred(
            2,
            "hero",
            CALL,
            delta_bb=2.5,
        )
    )

    result = tracker.ingest(
        inferred(
            3,
            "seat_upper_left",
            CALL_OR_RAISE,
            delta_bb=7.5,
        )
    )

    assert result is not None
    assert result.action == "RAISE"

    state = tracker.commitment_tracker._state("PREFLOP")

    # BB raised. Action wraps to UTG/HJ/BTN/SB, excluding the BB.
    # UTG was passively inferred folded before HJ's opening action.
    assert state.needs_response_from == [
        "seat_upper_right",
        "hero",
        "seat_mid_left",
    ]


def test_folded_and_all_in_players_are_excluded():
    hand = make_hand()

    hand.players["hero"].folded = True
    hand.players["hero"].active = False
    hand.players["seat_mid_left"].all_in = True

    tracker = BettingRoundTracker(hand)

    tracker.ingest(
        inferred(
            1,
            "seat_upper_right",
            BET_OR_RAISE,
            delta_bb=2.5,
        )
    )

    state = tracker.commitment_tracker._state("PREFLOP")

    assert state.needs_response_from == [
        "seat_upper_left",
    ]


def test_unresolved_commitment_does_not_open_response_queue():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(
            1,
            "seat_upper_right",
            BET_OR_RAISE,
            delta_bb=None,
        )
    )

    assert result is not None
    assert result.action == BET_OR_RAISE

    state = tracker.commitment_tracker._state("PREFLOP")

    assert state.needs_response_from == []


if __name__ == "__main__":
    test_opening_raise_builds_cyclic_response_queue()
    test_call_consumes_one_response()
    test_reraise_reopens_response_queue_in_cyclic_order()
    test_folded_and_all_in_players_are_excluded()
    test_unresolved_commitment_does_not_open_response_queue()

    print("Response queue regression tests passed.")
