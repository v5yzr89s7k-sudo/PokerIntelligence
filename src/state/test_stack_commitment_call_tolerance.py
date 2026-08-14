from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker
from src.observer.action_inference_engine import CALL_OR_RAISE


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="stack-call-tolerance",
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
                "name": "HJ",
                "stack_bb": 100.0,
                "is_hero": False,
                "is_active": True,
            },
            {
                "seat": "seat_mid_right",
                "name": "BB",
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
            "seat_mid_right": "BB",
        },
        started_ts=1.0,
    )

    # Build real canonical live-price history:
    #
    # BB establishes 1.00.
    # HJ raises from 1.00 to 3.15.
    #
    # Therefore the last full raise increment is:
    #
    #     3.15 - 1.00 = 2.15
    #
    # and the next full raise must reach at least:
    #
    #     3.15 + 2.15 = 5.30
    hand.add_action(
        seat="seat_mid_right",
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        confidence=1.0,
        source="test",
    )

    hand.add_action(
        seat="seat_mid_left",
        action="RAISE",
        raise_to_bb=3.15,
        confidence=1.0,
        source="test",
    )

    # Hero has already committed 1.00 BB before the measured response.
    hand.players["hero"].committed_by_street[
        "PREFLOP"
    ] = 1.00

    return hand


def inferred(
    *,
    episode_id,
    delta_bb,
    current_stack_bb=79.70,
):
    return {
        "episode_id": episode_id,
        "seat": "hero",
        "street": "PREFLOP",
        "action": CALL_OR_RAISE,
        "confidence": 0.80,
        "evidence": ["stack_changed"],
        "measurements": {
            "stack_change": {
                "previous_stack_bb": (
                    current_stack_bb
                    + delta_bb
                ),
                "current_stack_bb": current_stack_bb,
                "delta_bb": delta_bb,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "independent_confirmed",
            },
        },
    }


def test_stack_target_below_minimum_raise_resolves_call():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(
            episode_id=1,
            delta_bb=2.50,
        )
    )

    assert result is not None, result
    assert result.action == "CALL", result
    assert round(
        float(result.amount_bb or 0.0),
        2,
    ) == 2.50, result

    print(
        "PASS stack-derived call: "
        "1.00 + 2.50 = 3.50 facing 3.15 "
        "is below minimum full raise-to 5.30"
    )


def test_stack_target_reaching_minimum_raise_remains_raise():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(
            episode_id=2,
            delta_bb=5.00,
            current_stack_bb=75.00,
        )
    )

    assert result is not None, result
    assert result.action == "RAISE", result
    assert round(
        float(result.raise_to_bb or 0.0),
        2,
    ) == 6.00, result

    print(
        "PASS full raise safety: "
        "1.00 + 5.00 = 6.00 facing 3.15 "
        "exceeds minimum full raise-to 5.30"
    )


def main():
    test_stack_target_below_minimum_raise_resolves_call()
    test_stack_target_reaching_minimum_raise_remains_raise()

    print()
    print(
        "PASS stack commitment minimum-raise contract"
    )


if __name__ == "__main__":
    main()
