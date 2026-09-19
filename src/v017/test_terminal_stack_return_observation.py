"""
V0.17 physical terminal stack-return observation.

A post-terminal stack increase receives no generic quantitative
authority.

After UNCONTESTED completion, however, HandEngine determines one exact
permissible uncalled-return amount. A raw OCR candidate may confirm that
predetermined accounting value.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "CO",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]


def build_terminal_observer():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=["bb"],
        quantitative_seats=[
            "hero",
            "bb",
        ],
        hero_seat="hero",
        hand_id="terminal-return-observation",
    )

    observer.hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    observer.hand.observe_no_commitment(
        "bb"
    )

    observer.hand.start_street(
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

    observer.hand.observe_no_commitment(
        "bb"
    )

    observer.hand.observe_stack_commitment(
        "hero",
        2.12,
    )

    observer.trusted_stacks[
        "hero"
    ] = 46.88

    observer.hand.observe_fold(
        "bb"
    )

    return observer


def observation(
    value,
    *,
    seat="hero",
):
    return {
        "frame": 20,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "prior": 46.88,
        "reader_value": value,
        "resolved": False,
        "resolved_value": None,
        "raw": [
            {
                "variant":
                    "native_green_psm7",
                "raw":
                    f"{value:.2f} BB",
                "stack_bb": value,
            }
        ],
        "confidence": 0.8,
        "votes": 1,
        "mode": "native_green_fast",
    }


def main():
    observer = build_terminal_observer()

    assert observer.hand.hand_complete
    assert (
        observer.hand.completion_reason
        == "UNCONTESTED"
    )
    assert observer.hand.winner_seats == [
        "hero"
    ]

    assert (
        observer.hand
        .unmatched_commitment_bb(
            "hero"
        )
        == 2.12
    )

    actions_before = list(
        observer.hand.semantic_actions()
    )

    emitted = (
        observer
        .admit_terminal_stack_return(
            observation(
                49.00
            )
        )
    )

    assert len(emitted) == 1

    event = emitted[0]

    assert (
        event["type"]
        == "UNCALLED_RETURN_ADMITTED"
    )
    assert event["seat"] == "hero"
    assert event["amount_bb"] == 2.12
    assert event["prior"] == 46.88
    assert (
        event["resolved_value"]
        == 49.0
    )

    assert (
        observer.trusted_stacks[
            "hero"
        ]
        == 49.0
    )

    assert (
        observer.hand.semantic_actions()
        == actions_before
    )

    assert (
        observer.hand
        .unmatched_commitment_bb(
            "hero"
        )
        == 0.0
    )

    # Wrong observed value has no authority.
    wrong = build_terminal_observer()

    assert (
        wrong.admit_terminal_stack_return(
            observation(
                48.50
            )
        )
        == ()
    )

    assert (
        wrong.trusted_stacks[
            "hero"
        ]
        == 46.88
    )

    # Wrong seat has no authority.
    wrong_seat = build_terminal_observer()

    assert (
        wrong_seat
        .admit_terminal_stack_return(
            observation(
                52.12,
                seat="bb",
            )
        )
        == ()
    )

    print()
    print(
        "TERMINAL WINNER + UNMATCHED AMOUNT: PASS"
    )
    print(
        "RAW OCR EXACT EXPECTED VALUE: PASS"
    )
    print(
        "UNCALLED RETURN ADMITTED: PASS"
    )
    print(
        "TRUSTED STACK ADVANCED: PASS"
    )
    print(
        "BETTING ACTION APPENDED: NO"
    )
    print(
        "WRONG VALUE AUTHORITY: NO"
    )
    print(
        "WRONG SEAT AUTHORITY: NO"
    )
    print()
    print(
        "V0.17 TERMINAL STACK RETURN: PASS"
    )


if __name__ == "__main__":
    main()
