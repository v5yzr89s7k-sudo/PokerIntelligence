import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand()

    hand.start_hand(
        hand_id="tracker-street-sync",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "seat_mid_left",
                "name": "Villain",
                "stack_bb": 100.0,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="UTG+1",
        positions={
            "hero": "UTG+1",
            "seat_mid_left": "HJ",
        },
        started_ts=1.0,
    )

    return hand


def reset_tracker_globals():
    sm._ACTIVE_TRACKER = None
    sm._ACTIVE_HAND_ID = None


def main():
    reset_tracker_globals()

    hand = make_hand()

    # Initialize persistent tracker on FLOP.
    hand.set_board(
        ["8d", "8h", "As"],
        ts=2.0,
    )

    tracker = sm.tracker_for_hand(hand)

    assert tracker.street == "FLOP", tracker.street

    flop_status = tracker.commitment_tracker.round_status(
        "FLOP"
    )

    assert flop_status["players_owing_action"], flop_status

    # Advance the same canonical hand to TURN.
    # Critically: ingest NO inferred action.
    hand.set_board(
        ["8d", "8h", "As", "Jh"],
        ts=3.0,
    )

    expected_turn_queue = list(
        hand.players_to_act
    )

    assert expected_turn_queue, (
        "CanonicalHand must initialize a non-empty TURN queue"
    )

    # Production reconnects the persistent tracker to the latest
    # CanonicalHand through tracker_for_hand().
    tracker = sm.tracker_for_hand(hand)

    turn_status = tracker.commitment_tracker.round_status(
        "TURN"
    )

    assert tracker.street == "TURN", (
        f"persistent tracker remained on {tracker.street}"
    )

    assert (
        turn_status["players_owing_action"]
        == expected_turn_queue
    ), (
        turn_status,
        expected_turn_queue,
    )

    print(
        "PASS tracker_for_hand street synchronization: "
        "same-hand FLOP->TURN advance initializes TURN obligations "
        "without requiring an inferred action"
    )


if __name__ == "__main__":
    main()
