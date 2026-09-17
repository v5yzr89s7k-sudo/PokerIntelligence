"""
V0.17 pending physical street-boundary ownership contract.

A physically proven FLOP boundary may arrive while semantic PREFLOP
chronology is still blocked.

The boundary may not skip unresolved action chronology, but it also
may not be destroyed. Once the retained quantitative action evidence
closes PREFLOP, the already-observed FLOP must activate without
requiring the physical board transition to occur again.
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "utg",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "HJ",
        "name": "HJ",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 40.0,
        "dealt_in": True,
    },
]


def quantitative(frame, seat, value):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "resolved": True,
        "resolved_value": value,
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "utg": 50.0,
            "hero": 50.0,
            "sb": 20.0,
            "bb": 40.0,
        },
        opponent_seats=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        hero_seat="hero",
        hand_id="pending-street-boundary",
    )

    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "utg"

    # HJ/Hero's physical commitment is already visible, but UTG is
    # still the unresolved predecessor.
    blocked = observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    assert blocked == ()
    assert observer.pending_quantitative_evidence

    # SB and BB physically fold while chronology is still blocked
    # behind UTG. These observations must survive without immediate
    # semantic authority.
    sb_fold = observer.admit_card_disappearance(
        "sb",
        frame_id=11,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert sb_fold is None

    bb_fold = observer.admit_card_disappearance(
        "bb",
        frame_id=12,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert bb_fold is None

    assert [
        row["seat"]
        for row in observer.pending_card_disappearances
    ] == [
        "sb",
        "bb",
    ]

    # The physical FLOP appears after all preflop physical actions
    # have occurred, but before semantic chronology has caught up.
    boundary = {
        "frame": 13,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
    }

    result = observer.admit_street_boundary(
        boundary,
        action_order=[
            "sb",
            "bb",
            "hero",
        ],
        board=[
            "As",
            "Kd",
            "7c",
        ],
        complete_pending=False,
    )

    # Physical evidence cannot skip unresolved PREFLOP chronology.
    assert not result
    assert observer.hand.street == "PREFLOP"

    # But it must survive.
    assert hasattr(
        observer,
        "pending_street_boundaries",
    ), (
        "MISSING ARCHITECTURE: blocked physical street "
        "boundary has no retained ownership"
    )

    assert observer.pending_street_boundaries, (
        "MISSING RETENTION: physical FLOP boundary was discarded"
    )

    # UTG now folds. Existing automatic quantitative reconciliation
    # should consume Hero/HJ's retained raise. The already-observed
    # FLOP must then activate without another physical board event.
    observer.admit_card_disappearance(
        "utg",
        frame_id=14,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert observer.hand.street == "FLOP", (
        "MISSING AUTOMATIC STREET RECONCILIATION: "
        f"street={observer.hand.street}"
    )

    assert observer.pending_street_boundaries == []

    assert observer.hand.board == [
        "As",
        "Kd",
        "7c",
    ]

    actions = observer.hand.semantic_actions()

    voluntary = [
        (
            row["street"],
            row["seat"],
            row["action"],
            row["raise_to_bb"],
        )
        for row in actions
        if row["action"] not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    assert voluntary[:4] == [
        (
            "PREFLOP",
            "utg",
            "FOLD",
            None,
        ),
        (
            "PREFLOP",
            "hero",
            "RAISE",
            2.0,
        ),
        (
            "PREFLOP",
            "sb",
            "FOLD",
            None,
        ),
        (
            "PREFLOP",
            "bb",
            "FOLD",
            None,
        ),
    ], voluntary

    assert observer.hand.street == "FLOP"

    # Product must never publish FLOP before retained PREFLOP evidence
    # has been consumed.
    flop_publications = [
        row
        for row in observer.publications
        if row["street"] == "FLOP"
    ]

    assert len(flop_publications) == 1, (
        observer.publications
    )

    flop = flop_publications[0]

    assert flop["action_count"] == 6
    assert "UTG folds" in flop["text"]
    assert "HJ raises to 2 BB" in flop["text"]
    assert "SB folds" in flop["text"]
    assert "BB folds" in flop["text"]
    assert "FLOP: As Kd 7c" in flop["text"]

    print()
    print(
        "V0.17 PENDING STREET BOUNDARY "
        "RECONCILIATION: PASS"
    )


if __name__ == "__main__":
    main()
