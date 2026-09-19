"""
V0.17 uncontested uncalled-return accounting contract.

A stack increase is never generically a poker action.

Only after authoritative UNCONTESTED completion may an independently
observed winner stack increase be admitted as UNCALLED_RETURN, and only
when it exactly matches HandEngine's unmatched current-street
commitment.
"""

from src.v017.hand_engine import (
    HandEngine,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "CO",
        "name": "Hero",
        "stack_bb": 50.0,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
    },
]


def build_terminal_hand():
    hand = HandEngine(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    # Close preflop.
    hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    hand.observe_no_commitment(
        "bb"
    )

    hand.start_street(
        "FLOP",
        [
            "bb",
            "hero",
        ],
        board=[
            "Jd",
            "9s",
            "Tc",
        ],
    )

    # BB checks, Hero bets 2.12, BB folds.
    hand.observe_no_commitment(
        "bb"
    )

    hand.observe_stack_commitment(
        "hero",
        2.12,
    )

    hand.observe_fold(
        "bb"
    )

    return hand


def expect_rejected(
    label,
    fn,
):
    try:
        fn()
    except ValueError as exc:
        print(
            label,
            "->",
            str(exc),
        )
        return

    raise AssertionError(
        f"{label}: expected ValueError"
    )


def main():
    hand = build_terminal_hand()

    assert hand.hand_complete
    assert (
        hand.completion_reason
        == "UNCONTESTED"
    )
    assert hand.winner_seats == [
        "hero"
    ]

    assert (
        hand.unmatched_commitment_bb(
            "hero"
        )
        == 2.12
    )

    actions_before = list(
        hand.semantic_actions()
    )

    returned = (
        hand.observe_uncalled_return(
            "hero",
            2.12,
        )
    )

    assert returned == 2.12

    assert (
        hand.players[
            "hero"
        ].street_commitment_bb
        == 0.0
    )

    # Terminal accounting is not a betting action.
    assert (
        hand.semantic_actions()
        == actions_before
    )

    assert hand.hand_complete
    assert hand.winner_seats == [
        "hero"
    ]

    # ------------------------------------------------------------
    # SAFETY CONTRACTS
    # ------------------------------------------------------------

    wrong_amount = build_terminal_hand()

    expect_rejected(
        "wrong amount",
        lambda:
            wrong_amount
            .observe_uncalled_return(
                "hero",
                1.50,
            ),
    )

    wrong_seat = build_terminal_hand()

    expect_rejected(
        "wrong seat",
        lambda:
            wrong_seat
            .observe_uncalled_return(
                "bb",
                2.12,
            ),
    )

    incomplete = HandEngine(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    expect_rejected(
        "incomplete hand",
        lambda:
            incomplete
            .observe_uncalled_return(
                "hero",
                0.5,
            ),
    )

    print()
    print(
        "UNMATCHED COMMITMENT = 2.12 BB: PASS"
    )
    print(
        "EXACT RETURN ADMITTED: PASS"
    )
    print(
        "SEMANTIC ACTION APPENDED: NO"
    )
    print(
        "WRONG AMOUNT REJECTED: PASS"
    )
    print(
        "WRONG SEAT REJECTED: PASS"
    )
    print(
        "INCOMPLETE HAND REJECTED: PASS"
    )
    print()
    print(
        "V0.17 UNCALLED RETURN ACCOUNTING: PASS"
    )


if __name__ == "__main__":
    main()
