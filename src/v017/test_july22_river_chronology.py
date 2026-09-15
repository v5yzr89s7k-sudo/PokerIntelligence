from src.v017.test_july22_turn_chronology import (
    build_through_flop,
)


def build_through_turn():
    hand = build_through_flop()

    hand.start_street(
        "TURN",
        [
            "hero",
            "seat_lower_left",
        ],
    )

    assert (
        hand.observe_no_commitment(
            "hero"
        )
        == "CHECK"
    )

    assert (
        hand.observe_no_commitment(
            "seat_lower_left"
        )
        == "CHECK"
    )

    assert hand.next_actor is None

    return hand


def main():
    hand = build_through_turn()

    hand.start_street(
        "RIVER",
        [
            "hero",
            "seat_lower_left",
        ],
    )

    assert hand.next_actor == "hero"
    assert hand.current_price_bb == 0.0

    print("===== RIVER START =====")
    print("Hero stack = 6.90")
    print("BB stack   = 44.20")

    # Hero remains 6.90 before BB's physical commitment.
    # A later BB action therefore proves Hero completed a zero-chip
    # action while facing zero price.
    hero_action = hand.observe_no_commitment(
        "hero"
    )

    assert hero_action == "CHECK"
    assert hand.next_actor == "seat_lower_left"

    # Real pixel transition:
    # 44.20 -> 37.45 at frame 0127.
    bb_delta = round(
        44.20 - 37.45,
        2,
    )

    assert bb_delta == 6.75

    bb_action = hand.observe_stack_commitment(
        "seat_lower_left",
        bb_delta,
    )

    assert bb_action == "BET"
    assert hand.current_price_bb == 6.75
    assert hand.next_actor == "hero"

    print()
    print("BB action =", bb_action)
    print("BB amount =", bb_delta)

    # Hero remains 6.90; buttons disappear at frame 0131.
    # Therefore Hero did not commit chips to the 6.75 price.
    #
    # This is a validated fold completion, not opponent-card
    # disappearance.
    hero_fold = hand.observe_fold(
        "hero"
    )

    assert hero_fold == "FOLD"
    assert hand.next_actor is None

    print()
    print("Hero action =", hero_fold)

    river = [
        action
        for action in hand.semantic_actions()
        if action["street"] == "RIVER"
    ]

    print()
    print("===== RIVER ACTIONS =====")

    for action in river:
        print(action)

    observed = [
        (
            action["seat"],
            action["action"],
            action["amount_bb"],
            action["raise_to_bb"],
        )
        for action in river
    ]

    expected = [
        (
            "hero",
            "CHECK",
            None,
            None,
        ),
        (
            "seat_lower_left",
            "BET",
            6.75,
            None,
        ),
        (
            "hero",
            "FOLD",
            None,
            None,
        ),
    ]

    assert observed == expected, observed

    assert hand.players["hero"].folded is True
    assert (
        hand.players["seat_lower_left"].folded
        is False
    )

    print()
    print(
        "V0.17 JULY22 RIVER CHRONOLOGY: PASS"
    )


if __name__ == "__main__":
    main()
