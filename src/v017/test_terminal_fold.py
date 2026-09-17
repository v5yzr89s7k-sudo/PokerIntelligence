from src.v017.hand_engine import HandEngine


def build_heads_up():
    return HandEngine(
        players=[
            {
                "seat": "hero",
                "position": "SB",
                "name": "Hero",
                "stack_bb": 23.28,
            },
            {
                "seat": "villain",
                "position": "BB",
                "name": "Villain",
                "stack_bb": 27.47,
            },
        ],
        action_order=[
            "hero",
            "villain",
        ],
        small_blind_seat="hero",
        big_blind_seat="villain",
    )


def main():
    hand = build_heads_up()

    assert hand.next_actor == "hero"

    action = hand.observe_cards_disappeared(
        "hero"
    )

    assert action == "FOLD"
    assert hand.players["hero"].folded
    assert not hand.players["villain"].folded

    # Critical terminal contract.
    assert hand.pending_to_act == []
    assert hand.next_actor is None

    rows = hand.semantic_actions()

    assert rows[-1]["seat"] == "hero"
    assert rows[-1]["action"] == "FOLD"

    print(
        "V0.17 TERMINAL FOLD: PASS"
    )


if __name__ == "__main__":
    main()
