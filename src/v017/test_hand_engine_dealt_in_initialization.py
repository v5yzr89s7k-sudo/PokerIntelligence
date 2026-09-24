from src.v017.hand_engine import HandEngine


def main():
    players = [
        {
            "seat": "hero",
            "position": "SB",
            "name": "Hero",
            "stack_bb": 20.0,
            "dealt_in": True,
        },
        {
            "seat": "bb",
            "position": "BB",
            "name": "BB",
            "stack_bb": 20.0,
            # Deliberately omitted: legacy/default contract is True.
        },
        {
            "seat": "utg",
            "position": "UTG",
            "name": "Sitting Out",
            "stack_bb": 20.0,
            "dealt_in": False,
        },
    ]

    hand = HandEngine(
        players=players,
        action_order=["hero", "bb"],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    assert hand.players["hero"].dealt_in is True
    assert hand.players["bb"].dealt_in is True
    assert hand.players["utg"].dealt_in is False

    print(
        "V0.17 HAND ENGINE DEALT_IN "
        "INITIALIZATION: PASS"
    )


if __name__ == "__main__":
    main()
