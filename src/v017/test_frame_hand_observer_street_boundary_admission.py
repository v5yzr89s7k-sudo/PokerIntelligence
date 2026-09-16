"""
G3.5B contract.

Physical street-boundary admission:
- cannot manufacture unresolved actions;
- requires prior semantic betting round closure;
- uses caller-supplied board identity and action order;
- rejects stale/duplicate/malformed evidence.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 20.0,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 40.0,
    },
    {
        "seat": "btn",
        "position": "BTN",
        "name": "BTN",
        "stack_bb": 60.0,
    },
]


def build_observer():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "btn",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={},
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="g3.5b-contract",
    )


def main():
    observer = build_observer()

    flop = {
        "frame": 52,
        "type":
            "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
    }

    # --------------------------------------------------------
    # Open prior street: physical boundary cannot manufacture
    # unresolved action semantics.
    # --------------------------------------------------------
    before_actions = list(
        observer.hand.semantic_actions()
    )
    before_events = list(
        observer.events
    )

    blocked = observer.admit_street_boundary(
        flop,
        action_order=[
            "hero",
            "bb",
            "btn",
        ],
        board=[
            "Jd",
            "9s",
            "Tc",
        ],
    )

    assert blocked == ()
    assert observer.hand.street == "PREFLOP"
    assert (
        observer.hand.semantic_actions()
        == before_actions
    )
    assert observer.events == before_events

    # --------------------------------------------------------
    # Close preflop through explicit semantic evidence.
    # --------------------------------------------------------
    assert (
        observer.hand
        .observe_cards_disappeared(
            "btn"
        )
        == "FOLD"
    )

    assert (
        observer.hand
        .observe_stack_commitment(
            "hero",
            0.5,
        )
        == "CALL"
    )

    assert (
        observer.hand
        .observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )

    assert observer.hand.next_actor is None

    # --------------------------------------------------------
    # Closed prior street: FLOP admission is authoritative.
    # --------------------------------------------------------
    emitted = observer.admit_street_boundary(
        flop,
        action_order=[
            "hero",
            "bb",
        ],
        board=[
            "Jd",
            "9s",
            "Tc",
        ],
    )

    assert len(emitted) == 1

    admitted = emitted[0]

    assert (
        admitted["type"]
        == "STREET_BOUNDARY_ADMITTED"
    )
    assert admitted["street"] == "FLOP"
    assert observer.hand.street == "FLOP"
    assert observer.hand.board == [
        "Jd",
        "9s",
        "Tc",
    ]
    assert observer.hand.next_actor == "hero"

    # --------------------------------------------------------
    # Duplicate physical boundary: no mutation.
    # --------------------------------------------------------
    before_actions = list(
        observer.hand.semantic_actions()
    )
    before_events = list(
        observer.events
    )

    duplicate = observer.admit_street_boundary(
        flop,
        action_order=[
            "hero",
            "bb",
        ],
        board=[
            "Jd",
            "9s",
            "Tc",
        ],
    )

    assert duplicate == ()
    assert (
        observer.hand.semantic_actions()
        == before_actions
    )
    assert observer.events == before_events

    # --------------------------------------------------------
    # Wrong board count: reject before mutation.
    # --------------------------------------------------------
    bad_turn = {
        "frame": 103,
        "type":
            "TURN_BOUNDARY_PHYSICAL",
        "board_count": 5,
    }

    try:
        observer.admit_street_boundary(
            bad_turn,
            action_order=[
                "hero",
                "bb",
            ],
            board=[
                "Jd",
                "9s",
                "Tc",
                "9h",
            ],
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "wrong TURN board_count admitted"
        )

    assert observer.hand.street == "FLOP"

    # --------------------------------------------------------
    # Open FLOP blocks TURN.
    # --------------------------------------------------------
    turn = {
        "frame": 103,
        "type":
            "TURN_BOUNDARY_PHYSICAL",
        "board_count": 4,
    }

    blocked_turn = (
        observer.admit_street_boundary(
            turn,
            action_order=[
                "hero",
                "bb",
            ],
            board=[
                "Jd",
                "9s",
                "Tc",
                "9h",
            ],
        )
    )

    assert blocked_turn == ()
    assert observer.hand.street == "FLOP"

    # Explicitly close FLOP.
    assert (
        observer.hand
        .observe_no_commitment(
            "hero"
        )
        == "CHECK"
    )
    assert (
        observer.hand
        .observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )
    assert observer.hand.next_actor is None

    emitted = observer.admit_street_boundary(
        turn,
        action_order=[
            "hero",
            "bb",
        ],
        board=[
            "Jd",
            "9s",
            "Tc",
            "9h",
        ],
    )

    assert len(emitted) == 1
    assert observer.hand.street == "TURN"
    assert observer.hand.board == [
        "Jd",
        "9s",
        "Tc",
        "9h",
    ]
    assert observer.hand.next_actor == "hero"

    print(
        "G3.5B FRAME STREET BOUNDARY "
        "ADMISSION: PASS"
    )
    print(
        "street:",
        observer.hand.street,
    )
    print(
        "board:",
        observer.hand.board,
    )
    print(
        "next_actor:",
        observer.hand.next_actor,
    )


if __name__ == "__main__":
    main()
