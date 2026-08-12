from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


POSITIONS = {
    "seat_upper_left": "UTG",
    "seat_top": "UTG+1",
    "seat_mid_right": "HJ",
    "seat_lower_right": "CO",
    "hero": "BTN",
    "seat_lower_left": "SB",
    "seat_mid_left": "BB",
}


def main():
    players = [
        {
            "seat": seat,
            "name": seat,
            "stack_bb": 100,
        }
        for seat in POSITIONS
    ]

    hand = CanonicalHand().start_hand(
        hand_id="replay-0001-sizing",
        players=players,
        hero_cards=["6c", "8d"],
        hero_position="BTN",
        positions=POSITIONS,
    )

    hand.dealt_in_seats = list(POSITIONS)

    # Replay 0001 tournament level:
    # 0.125 BB ante, 0.5 BB SB, 1 BB BB.
    for seat in POSITIONS:
        hand.add_action(
            seat=seat,
            action="POST_ANTE",
            amount_bb=0.125,
            confidence=1.0,
            source="replay_0001_seed",
        )

    hand.add_action(
        seat="seat_lower_left",
        action="POST_SMALL_BLIND",
        amount_bb=0.5,
        confidence=1.0,
        source="replay_0001_seed",
    )

    hand.add_action(
        seat="seat_mid_left",
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        confidence=1.0,
        source="replay_0001_seed",
    )

    hand.current_bet_bb = 1.0

    hand.players_to_act = [
        "seat_upper_left",
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
    ]

    tracker = BettingRoundTracker(hand)

    hero_open = tracker.ingest({
        "episode_id": 1,
        "seat": "hero",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 3.5,
            },
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 1.0,
    })

    bb_three_bet = tracker.ingest({
        "episode_id": 2,
        "seat": "seat_mid_left",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                # BB already posted 1.0 and adds 9.0.
                "delta_bb": 9.0,
            },
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 2.0,
    })

    hero_call = tracker.ingest({
        "episode_id": 3,
        "seat": "hero",
        "street": "PREFLOP",
        "action": "CALL_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                # Hero already committed 3.5 and adds 6.5.
                "delta_bb": 6.5,
            },
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 3.0,
    })

    assert hand.ante_committed_bb(
        "hero",
        "PREFLOP",
    ) == 0.125

    assert hero_open is not None
    assert hero_open.action == "RAISE"
    assert hero_open.raise_to_bb == 3.5, hero_open

    assert bb_three_bet is not None
    assert bb_three_bet.action == "RAISE"
    assert bb_three_bet.raise_to_bb == 10.0, bb_three_bet

    assert hero_call is not None
    assert hero_call.action == "CALL"
    assert hero_call.amount_bb == 6.5, hero_call
    assert hero_call.raise_to_bb is None

    hero_total = (
        hand.players["hero"]
        .committed_by_street["PREFLOP"]
    )

    bb_total = (
        hand.players["seat_mid_left"]
        .committed_by_street["PREFLOP"]
    )

    assert hero_total == 10.125, hero_total
    assert bb_total == 10.125, bb_total

    print(
        "PASS Replay 0001 preflop sizing: "
        "BTN raises to 3.5, BB raises to 10, BTN calls 6.5"
    )


if __name__ == "__main__":
    main()
