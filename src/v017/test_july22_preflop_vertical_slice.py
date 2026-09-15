from src.v017.hand_engine import HandEngine


PLAYERS = [
    {
        "seat": "seat_lower_left",
        "position": "BB",
        "name": "Birkam",
        "stack_bb": 48.57,
    },
    {
        "seat": "seat_lower_right",
        "position": "BTN",
        "name": "AllinMatt31",
        "stack_bb": 58.55,
    },
    {
        "seat": "seat_mid_right",
        "position": "CO",
        "name": "Pablopg",
        "stack_bb": 136.01,
    },
    {
        "seat": "seat_upper_right",
        "position": "HJ",
        "name": "Twib101",
        "stack_bb": 106.7,
    },
    {
        "seat": "seat_upper_left",
        "position": "LJ",
        "name": "Slayer1950",
        "stack_bb": 59.08,
    },
    {
        "seat": "hero",
        "position": "SB",
        "name": "poker5068",
        "stack_bb": 11.78,
    },
    {
        "seat": "seat_mid_left",
        "position": "UTG",
        "name": "Fartsenia",
        "stack_bb": 17.85,
    },
]


# July 22 observer acquisition begins after UTG.
#
# The engine therefore owns only the observed chronology frontier:
#
# LJ -> HJ -> CO -> BTN -> SB -> BB
#
# We do not manufacture an UTG action that was never observed.
ACTION_ORDER = [
    "seat_upper_left",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
]


def main():
    hand = HandEngine(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
    )

    print()
    print("===== START =====")
    print(
        "next_actor =",
        hand.next_actor,
    )
    print(
        "price =",
        hand.current_price_bb,
    )

    # Objective observations from July 22.
    hand.observe_cards_disappeared(
        "seat_upper_left"
    )

    hand.observe_cards_disappeared(
        "seat_upper_right"
    )

    hand.observe_cards_disappeared(
        "seat_mid_right"
    )

    btn_action = (
        hand.observe_stack_commitment(
            "seat_lower_right",
            2.0,
        )
    )

    hero_action = (
        hand.observe_stack_commitment(
            "hero",
            1.5,
        )
    )

    print()
    print("===== ACTIONS =====")

    for action in hand.semantic_actions():
        print(action)

    print()
    print("===== FINAL STATE =====")

    print(
        "BTN action =",
        btn_action,
    )

    print(
        "Hero action =",
        hero_action,
    )

    print(
        "price =",
        hand.current_price_bb,
    )

    print(
        "next_actor =",
        hand.next_actor,
    )

    voluntary = [
        item
        for item in hand.semantic_actions()
        if item["action"]
        not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    expected = [
        (
            "seat_upper_left",
            "FOLD",
            None,
            None,
        ),
        (
            "seat_upper_right",
            "FOLD",
            None,
            None,
        ),
        (
            "seat_mid_right",
            "FOLD",
            None,
            None,
        ),
        (
            "seat_lower_right",
            "RAISE",
            None,
            2.0,
        ),
        (
            "hero",
            "CALL",
            1.5,
            None,
        ),
    ]

    observed = [
        (
            item["seat"],
            item["action"],
            item["amount_bb"],
            item["raise_to_bb"],
        )
        for item in voluntary
    ]

    assert observed == expected, (
        "\nEXPECTED:\n"
        f"{expected}\n"
        "\nOBSERVED:\n"
        f"{observed}"
    )

    assert (
        hand.current_price_bb
        == 2.0
    )

    assert (
        hand.players[
            "hero"
        ].street_commitment_bb
        == 2.0
    )

    assert (
        hand.players[
            "seat_lower_right"
        ].street_commitment_bb
        == 2.0
    )

    assert (
        hand.next_actor
        == "seat_lower_left"
    )

    print()
    print(
        "V0.17 JULY22 PREFLOP "
        "VERTICAL SLICE: PASS"
    )


if __name__ == "__main__":
    main()
