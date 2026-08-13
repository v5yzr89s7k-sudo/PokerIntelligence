from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


POSITIONS = {
    "seat_top": "BB",
    "seat_upper_right": "UTG",
    "seat_mid_right": "UTG+1",
    "seat_lower_right": "LJ",
    "hero": "HJ",
    "seat_lower_left": "CO",
    "seat_mid_left": "BTN",
    "seat_upper_left": "SB",
}


def inferred(
    episode_id,
    seat,
    action,
    *,
    delta_bb,
    ts,
):
    return {
        "episode_id": episode_id,
        "seat": seat,
        "street": "PREFLOP",
        "action": action,
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": delta_bb,
            },
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": ts,
    }


def make_hand():
    players = [
        {
            "seat": seat,
            "name": seat,
            "stack_bb": 100.0,
        }
        for seat in POSITIONS
    ]

    hand = CanonicalHand().start_hand(
        hand_id="replay-0002-preflop",
        players=players,
        hero_cards=["7h", "Jc"],
        hero_position="HJ",
        positions=POSITIONS,
    )

    hand.dealt_in_seats = list(POSITIONS)

    # 8-max tournament ante = 0.125 BB per player.
    for seat in POSITIONS:
        hand.add_action(
            seat=seat,
            action="POST_ANTE",
            amount_bb=0.125,
            confidence=1.0,
            source="replay_0002_seed",
        )

    hand.add_action(
        seat="seat_upper_left",
        action="POST_SMALL_BLIND",
        amount_bb=0.5,
        confidence=1.0,
        source="replay_0002_seed",
    )

    hand.add_action(
        seat="seat_top",
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        confidence=1.0,
        source="replay_0002_seed",
    )

    hand.current_bet_bb = 1.0

    hand.players_to_act = [
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
        "seat_top",
    ]

    return hand


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    # UTG folds implicitly when the observed actor skips to UTG+1.
    utg1 = tracker.ingest(
        inferred(
            1,
            "seat_mid_right",
            "BET_OR_RAISE",
            delta_bb=2.0,
            ts=1.0,
        )
    )

    print("===== UTG+1 =====")
    print(utg1)

    assert utg1 is not None
    assert utg1.position == "UTG+1"
    assert utg1.action == "RAISE"
    assert utg1.raise_to_bb == 2.0

    # LJ adds 7 BB from zero live preflop commitment.
    # With current price 2 BB, that should resolve as a raise to 7.
    lj = tracker.ingest(
        inferred(
            2,
            "seat_lower_right",
            "CALL_OR_RAISE",
            delta_bb=7.0,
            ts=2.0,
        )
    )

    print()
    print("===== LJ =====")
    print(lj)

    assert lj is not None
    assert lj.position == "LJ"
    assert lj.action == "RAISE"
    assert lj.raise_to_bb == 7.0

    # Hero adds exactly 7 BB facing a 7 BB live price.
    hero = tracker.ingest(
        inferred(
            3,
            "hero",
            "CALL_OR_RAISE",
            delta_bb=7.0,
            ts=3.0,
        )
    )

    print()
    print("===== HERO =====")
    print(hero)

    assert hero is not None
    assert hero.position == "HJ"
    assert hero.action == "CALL"
    assert hero.amount_bb == 7.0
    assert hero.raise_to_bb is None

    forced = {
        "POST_ANTE",
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
    }

    actual = [
        (
            action.position,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in hand.actions
        if action.street == "PREFLOP"
        and action.action not in forced
    ]

    expected = [
        ("UTG", "FOLD", None, None),
        ("UTG+1", "RAISE", None, 2.0),
        ("LJ", "RAISE", None, 7.0),
        ("HJ", "CALL", 7.0, None),
    ]

    print()
    print("===== REPLAY 0002 PREFLOP =====")

    for item in actual:
        print(item)

    assert actual == expected, (
        "\nACTUAL:\n"
        + "\n".join(map(str, actual))
        + "\n\nEXPECTED:\n"
        + "\n".join(map(str, expected))
    )

    print()
    print(
        "PASS Replay 0002 preflop semantics: "
        "UTG folds, UTG+1 raises to 2, "
        "LJ raises to 7, HJ Hero calls 7"
    )


if __name__ == "__main__":
    main()
