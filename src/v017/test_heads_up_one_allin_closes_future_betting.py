"""
Betting-actionability contract.

Heads-up:
    one player all-in + one player with chips
    -> no future betting action is possible.

Multiway:
    one player all-in + two players with chips
    -> the two chip-bearing players remain actionable.
"""

from src.v017.hand_engine import HandEngine


def heads_up():
    hand = HandEngine(
        players=[
            {
                "seat": "allin",
                "position": "LJ",
                "name": "AllIn",
                "stack_bb": 10.0,
                "dealt_in": True,
            },
            {
                "seat": "deep",
                "position": "SB",
                "name": "Deep",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
        ],
        action_order=["allin", "deep"],
        small_blind_seat="deep",
        big_blind_seat="allin",
    )

    # Preflop betting is already closed.
    hand.players["allin"].all_in = True
    hand.pending_to_act = []

    hand.start_street(
        "FLOP",
        ["allin", "deep"],
        board=["2c", "7d", "9h"],
    )

    assert hand.pending_to_act == [], (
        "RED: sole chip-bearing player was given "
        "meaningless heads-up betting action"
    )
    assert hand.next_actor is None

    hand.start_street(
        "TURN",
        ["allin", "deep"],
        board=["2c", "7d", "9h", "Qs"],
    )

    assert hand.pending_to_act == []
    assert hand.next_actor is None

    hand.start_street(
        "RIVER",
        ["allin", "deep"],
        board=["2c", "7d", "9h", "Qs", "3c"],
    )

    assert hand.pending_to_act == []
    assert hand.next_actor is None

    print(
        "HEADS-UP ONE-ALL-IN -> AUTOMATIC RUNOUT: PASS"
    )


def multiway():
    hand = HandEngine(
        players=[
            {
                "seat": "allin",
                "position": "UTG",
                "name": "AllIn",
                "stack_bb": 10.0,
                "dealt_in": True,
            },
            {
                "seat": "deep1",
                "position": "BTN",
                "name": "Deep1",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
            {
                "seat": "deep2",
                "position": "BB",
                "name": "Deep2",
                "stack_bb": 60.0,
                "dealt_in": True,
            },
        ],
        action_order=["allin", "deep1", "deep2"],
        small_blind_seat="deep1",
        big_blind_seat="deep2",
    )

    hand.players["allin"].all_in = True
    hand.pending_to_act = []

    hand.start_street(
        "FLOP",
        ["allin", "deep1", "deep2"],
        board=["2c", "7d", "9h"],
    )

    assert hand.pending_to_act == [
        "deep1",
        "deep2",
    ], (
        "multiway betting was incorrectly closed "
        f"pending={hand.pending_to_act}"
    )

    assert hand.next_actor == "deep1"

    print(
        "MULTIWAY ONE-ALL-IN -> NORMAL BETTING: PASS"
    )


def main():
    heads_up()
    multiway()


if __name__ == "__main__":
    main()
