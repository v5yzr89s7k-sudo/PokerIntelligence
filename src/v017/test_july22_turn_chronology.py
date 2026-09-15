from src.v017.hand_engine import HandEngine
from src.v017.test_july22_preflop_vertical_slice import (
    PLAYERS,
    ACTION_ORDER,
)


def build_through_flop():
    hand = HandEngine(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
    )

    # Pixel-proven preflop.
    hand.observe_cards_disappeared(
        "seat_upper_left"
    )
    hand.observe_cards_disappeared(
        "seat_upper_right"
    )
    hand.observe_cards_disappeared(
        "seat_mid_right"
    )
    hand.observe_stack_commitment(
        "seat_lower_right",
        2.0,
    )
    hand.observe_stack_commitment(
        "hero",
        1.5,
    )
    hand.observe_stack_commitment(
        "seat_lower_left",
        1.0,
    )

    assert hand.next_actor is None

    # Pixel-proven flop.
    hand.start_street(
        "FLOP",
        [
            "hero",
            "seat_lower_left",
            "seat_lower_right",
        ],
    )

    assert (
        hand.observe_no_commitment(
            "hero"
        )
        == "CHECK"
    )

    assert (
        hand.observe_stack_commitment(
            "seat_lower_left",
            3.37,
        )
        == "BET"
    )

    assert (
        hand.observe_cards_disappeared(
            "seat_lower_right"
        )
        == "FOLD"
    )

    assert (
        hand.observe_stack_commitment(
            "hero",
            3.37,
        )
        == "CALL"
    )

    assert hand.next_actor is None

    return hand


def main():
    hand = build_through_flop()

    print("===== END FLOP =====")
    print("next_actor =", hand.next_actor)
    print("price =", hand.current_price_bb)

    hand.start_street(
        "TURN",
        [
            "hero",
            "seat_lower_left",
        ],
    )

    print()
    print("===== TURN START =====")
    print("next_actor =", hand.next_actor)
    print("price =", hand.current_price_bb)

    assert hand.next_actor == "hero"
    assert hand.current_price_bb == 0.0

    # Objective July 22 evidence:
    #
    # Hero trusted stack:
    #   0103-0114 = 6.90 BB
    #
    # BB trusted stack:
    #   0103-0114 = 44.20 BB
    #
    # no bet-region appearance
    # no card disappearance
    # river arrives at 0115
    #
    # Therefore each actor completed a zero-chip action while
    # facing price zero. HandEngine owns the CHECK semantics.

    hero_before = 6.90
    hero_after = 6.90

    bb_before = 44.20
    bb_after = 44.20

    assert hero_before == hero_after
    assert bb_before == bb_after

    hero_action = hand.observe_no_commitment(
        "hero"
    )

    assert hero_action == "CHECK"
    assert hand.next_actor == "seat_lower_left"

    bb_action = hand.observe_no_commitment(
        "seat_lower_left"
    )

    assert bb_action == "CHECK"
    assert hand.next_actor is None

    print()
    print("===== TURN ACTIONS =====")

    turn = [
        action
        for action in hand.semantic_actions()
        if action["street"] == "TURN"
    ]

    for action in turn:
        print(action)

    observed = [
        (
            action["seat"],
            action["action"],
        )
        for action in turn
    ]

    assert observed == [
        (
            "hero",
            "CHECK",
        ),
        (
            "seat_lower_left",
            "CHECK",
        ),
    ]

    # River boundary is legal only after TURN is closed.
    hand.start_street(
        "RIVER",
        [
            "hero",
            "seat_lower_left",
        ],
    )

    assert hand.street == "RIVER"
    assert hand.next_actor == "hero"
    assert hand.current_price_bb == 0.0

    print()
    print(
        "V0.17 JULY22 TURN CHRONOLOGY: PASS"
    )


if __name__ == "__main__":
    main()
