from src.v017.hand_engine import HandEngine


def main():
    players = [
        {
            "seat": "hero",
            "position": "SB",
            "name": "Hero",
            "stack_bb": 10.0,
        },
        {
            "seat": "bb",
            "position": "BB",
            "name": "BB",
            "stack_bb": 20.0,
        },
    ]

    hand = HandEngine(
        players=players,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    result = hand.observe_fold(
        "hero"
    )

    assert result == "FOLD"
    assert hand.players["hero"].folded is True
    assert hand.next_actor == "bb"

    action = hand.semantic_actions()[-1]

    assert action["seat"] == "hero"
    assert action["action"] == "FOLD"

    print(
        "V0.17 GENERAL FOLD SEMANTIC: PASS"
    )


if __name__ == "__main__":
    main()
