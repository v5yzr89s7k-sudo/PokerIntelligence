"""
V0.17 regression:
Hero's preflop action physically begins before the FLOP boundary,
but quantitative stack settlement completes after the boundary.

Ground truth:
    BTN raises to 2 BB
    SB folds
    Hero BB calls

The delayed quantitative settlement remains PREFLOP-owned because
independent pre-boundary physical provenance proves the action began
before the FLOP appeared.

This must NOT weaken the generic rule that truly post-boundary
quantitative evidence cannot rewrite the prior street.
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "btn",
        "position": "BTN",
        "name": "BTN",
        "stack_bb": 30.0,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 100.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "BB",
        "name": "Hero",
        "stack_bb": 46.43,
        "dealt_in": True,
        "is_hero": True,
    },
]


def quantitative(frame, value):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "resolved": True,
        "resolved_value": value,
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "btn",
            "sb",
            "hero",
        ],
        small_blind_seat="sb",
        big_blind_seat="hero",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "btn": 30.0,
            "sb": 100.0,
            "hero": 46.43,
        },
        opponent_seats=[
            "btn",
            "sb",
        ],
        quantitative_seats=[
            "btn",
            "sb",
            "hero",
        ],
        hero_seat="hero",
        hand_id="hero-preboundary-call-delayed-settlement",
    )

    # Establish the real preflop semantic position directly:
    #
    # BTN raises to 2
    # SB folds
    # Hero BB is now facing 1 additional BB.
    #
    # We deliberately use HandEngine authority for the setup so this
    # regression isolates boundary/provenance ownership rather than
    # retesting unrelated BTN/SB perception.
    assert observer.hand.next_actor == "btn"

    assert (
        observer.hand.observe_stack_commitment(
            "btn",
            2.0,
        )
        == "RAISE"
    )

    assert observer.hand.next_actor == "sb"

    assert (
        observer.hand.observe_fold("sb")
        == "FOLD"
    )

    assert observer.hand.next_actor == "hero"
    assert observer.hand.street == "PREFLOP"
    assert observer.hand.current_price_bb == 2.0

    # Physical Hero stack motion begins BEFORE the physical flop.
    #
    # This is independent physical provenance. OCR has not settled yet.
    observer.pre_boundary_stack_motion["hero"] = {
        "frame": 10,
        "boundary_frame": 13,
        "street": "PREFLOP",
    }

    # FLOP physically appears while Hero's stack text is still settling.
    boundary = {
        "frame": 13,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
    }

    result = observer.admit_street_boundary(
        boundary,
        action_order=[
            "sb",
            "hero",
            "btn",
        ],
        board=[
            "As",
            "Kd",
            "7c",
        ],
        complete_pending=False,
    )

    assert result == ()
    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "hero"
    assert observer.pending_street_boundaries

    # OCR settles AFTER the boundary.
    #
    # Hero began at 46.43 BB with the 1 BB blind already represented
    # semantically. A physical decrease of 1 BB completes the call to 2.
    emitted = observer.admit_quantitative_observation(
        quantitative(
            16,
            45.43,
        )
    )

    actions = observer.hand.semantic_actions()

    hero_preflop = [
        row
        for row in actions
        if (
            row["street"] == "PREFLOP"
            and row["seat"] == "hero"
            and row["action"]
            not in {
                "POST_BIG_BLIND",
                "POST_SMALL_BLIND",
            }
        )
    ]

    print()
    print("emitted =", emitted)
    print("hero_preflop =", hero_preflop)
    print("street =", observer.hand.street)
    print("next_actor =", observer.hand.next_actor)
    print(
        "pre_boundary_motion =",
        observer.pre_boundary_stack_motion.get("hero"),
    )
    print()

    assert len(hero_preflop) == 1, (
        "RED: delayed Hero settlement did not resolve "
        "the pre-boundary PREFLOP action"
    )

    assert hero_preflop[0]["action"] == "CALL", (
        "RED: Hero pre-boundary action was not classified CALL"
    )

    # The delayed CALL closes PREFLOP and immediately releases the
    # already-retained FLOP boundary. Hero may therefore legitimately
    # become the first actor on FLOP.
    assert observer.hand.street == "FLOP", (
        "delayed Hero CALL did not release retained FLOP boundary"
    )

    assert observer.hand.next_actor == "hero", (
        "unexpected FLOP action frontier after delayed Hero CALL"
    )

    assert not [
        row
        for row in observer.pending_quantitative_evidence
        if (
            row.get("seat") == "hero"
            and row.get("frame") == 16
        )
    ], (
        "RED: pre-boundary-owned Hero settlement was "
        "incorrectly retained as post-boundary evidence"
    )

    print(
        "HERO PRE-BOUNDARY CALL + DELAYED SETTLEMENT: PASS"
    )


if __name__ == "__main__":
    main()
