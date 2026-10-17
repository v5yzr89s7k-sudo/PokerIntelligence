"""
Regression: once betting is closed by all-in action, stale quantitative
settlement ownership must not block physical board runout chronology.
"""

from src.v017.hand_engine import HandEngine


def main():
    hand = HandEngine(
        players=[
            {
                "seat": "hero",
                "position": "SB",
                "name": "Hero",
                "stack_bb": 5.0,
                "dealt_in": True,
            },
            {
                "seat": "villain",
                "position": "BB",
                "name": "Villain",
                "stack_bb": 5.0,
                "dealt_in": True,
            },
        ],
        action_order=["hero", "villain"],
        small_blind_seat="hero",
        big_blind_seat="villain",
    )

    assert hand.observe_stack_commitment(
        "hero",
        4.5,
        all_in_confirmed=True,
    ) == "RAISE"

    assert hand.observe_stack_commitment(
        "villain",
        4.0,
        all_in_confirmed=True,
    ) == "CALL"

    assert hand.next_actor is None
    assert hand.pending_to_act == []

    # This is the key production invariant.
    # No player can perform another betting action, therefore old
    # quantitative settlement ownership cannot own future streets.
    actionable = [
        seat
        for seat in ("hero", "villain")
        if not hand.players[seat].folded
        and not hand.players[seat].all_in
    ]

    assert actionable == []

    hand.start_street(
        "FLOP",
        ["hero", "villain"],
        board=["3s", "3c", "8c"],
    )

    assert hand.next_actor is None

    hand.start_street(
        "TURN",
        ["hero", "villain"],
        board=["3s", "3c", "8c", "Qh"],
    )

    assert hand.street == "TURN"
    assert hand.next_actor is None

    hand.start_street(
        "RIVER",
        ["hero", "villain"],
        board=["3s", "3c", "8c", "Qh", "Ks"],
    )

    assert hand.street == "RIVER"
    assert hand.next_actor is None

    print(
        "ALL-IN CLOSED BETTING -> "
        "UNBLOCKED BOARD RUNOUT: PASS"
    )


if __name__ == "__main__":
    main()
