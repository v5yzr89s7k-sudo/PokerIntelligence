from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def main():
    hand = CanonicalHand().start_hand(
        hand_id="live-call-price-normalization",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 10.28,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 44.20,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="SB",
        positions={
            "hero": "SB",
            "villain": "BB",
        },
        started_ts=1.0,
    )

    # Model the July 22 flop directly.
    hand.current_street = "FLOP"
    hand.current_bet_bb = 3.37
    hand.players_to_act = ["hero"]

    tracker = BettingRoundTracker(hand)

    result = tracker.ingest({
        "episode_id": 1,
        "seat": "hero",
        "street": "FLOP",
        "action": "CALL_OR_RAISE",
        "confidence": 0.98,
        "evidence": [
            "stack_changed",
        ],
        "measurements": {
            "stack_change": {
                "previous_stack_bb": 10.28,
                "current_stack_bb": 6.90,
                "delta_bb": 3.38,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "independent_confirmed",
            },
        },
        "ts": 2.0,
    })

    print("===== JULY 22 LIVE TRACKER NORMALIZATION =====")
    print("raw stack delta:", 3.38)
    print("prior live commitment:", 0.0)
    print("established price:", 3.37)
    print(
        "canonical action:",
        result.action if result else None,
    )
    print(
        "canonical amount:",
        result.amount_bb if result else None,
    )

    assert result is not None
    assert result.action == "CALL"
    assert abs(float(result.amount_bb) - 3.37) < 1e-9

    # Also prove partial live commitment is handled correctly:
    # 0.50 already live, price is 2.50, noisy delta reads 2.01.
    partial = CanonicalHand().start_hand(
        hand_id="partial-live-call-normalization",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 20.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 20.0,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="SB",
        positions={
            "hero": "SB",
            "villain": "BB",
        },
        started_ts=10.0,
    )

    partial.current_street = "FLOP"
    partial.current_bet_bb = 2.50
    partial.players_to_act = ["hero"]

    # Existing live commitment before the call.
    partial.players["hero"].committed_by_street["FLOP"] = 0.50

    partial_tracker = BettingRoundTracker(partial)

    partial_result = partial_tracker.ingest({
        "episode_id": 2,
        "seat": "hero",
        "street": "FLOP",
        "action": "CALL_OR_RAISE",
        "confidence": 0.98,
        "evidence": [
            "stack_changed",
        ],
        "measurements": {
            "stack_change": {
                "delta_bb": 2.01,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "independent_confirmed",
            },
        },
        "ts": 11.0,
    })

    print()
    print("===== PARTIAL LIVE COMMITMENT =====")
    print("raw stack delta:", 2.01)
    print("prior live commitment:", 0.50)
    print("established price:", 2.50)
    print(
        "canonical action:",
        partial_result.action
        if partial_result
        else None,
    )
    print(
        "canonical amount:",
        partial_result.amount_bb
        if partial_result
        else None,
    )

    assert partial_result is not None
    assert partial_result.action == "CALL"
    assert abs(
        float(partial_result.amount_bb) - 2.0
    ) < 1e-9

    print()
    print(
        "PASS: live tracker normalizes exact-price CALL "
        "to outstanding canonical price while preserving "
        "raw stack delta as evidence"
    )


if __name__ == "__main__":
    main()
