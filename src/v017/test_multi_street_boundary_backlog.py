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
        "name": "Hero",
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


def boundary(frame, typ, count):
    return {
        "frame": frame,
        "type": typ,
        "board_count": count,
    }


def make_observer():
    return FrameHandObserver(
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
        hand_id="multi-street-backlog",
    )


def main():
    observer = make_observer()

    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "utg"

    # Hero's raise is physically known before UTG resolves.
    assert observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    ) == ()

    # Later PREFLOP actors physically fold.
    assert observer.admit_card_disappearance(
        "sb",
        frame_id=11,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    ) is None

    assert observer.admit_card_disappearance(
        "bb",
        frame_id=12,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    ) is None

    # --------------------------------------------------------
    # The physical table now runs ahead all the way to river
    # while semantic chronology is still blocked at PREFLOP.
    # --------------------------------------------------------

    flop = observer.admit_street_boundary(
        boundary(
            13,
            "FLOP_BOUNDARY_PHYSICAL",
            3,
        ),
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

    assert flop == ()
    assert observer.hand.street == "PREFLOP"

    turn = observer.admit_street_boundary(
        boundary(
            14,
            "TURN_BOUNDARY_PHYSICAL",
            4,
        ),
        action_order=[
            "sb",
            "bb",
            "hero",
        ],
        board=[
            "As",
            "Kd",
            "7c",
            "2h",
        ],
        complete_pending=True,
    )

    assert turn == ()
    assert observer.hand.street == "PREFLOP"

    river = observer.admit_street_boundary(
        boundary(
            15,
            "RIVER_BOUNDARY_PHYSICAL",
            5,
        ),
        action_order=[
            "sb",
            "bb",
            "hero",
        ],
        board=[
            "As",
            "Kd",
            "7c",
            "2h",
            "Ad",
        ],
        complete_pending=True,
    )

    assert river == ()
    assert observer.hand.street == "PREFLOP"

    print(
        "pending boundary types before release =",
        [
            row["observation"]["type"]
            for row
            in observer.pending_street_boundaries
        ],
    )

    # E5 requirement:
    #
    # All three physical observations must retain ownership even
    # though TURN/RIVER were observed before semantic FLOP existed.
    assert len(
        observer.pending_street_boundaries
    ) == 3, (
        "MISSING ARCHITECTURE: later physical street "
        "boundaries are discarded while semantics lag"
    )

    assert [
        row["observation"]["type"]
        for row
        in observer.pending_street_boundaries
    ] == [
        "FLOP_BOUNDARY_PHYSICAL",
        "TURN_BOUNDARY_PHYSICAL",
        "RIVER_BOUNDARY_PHYSICAL",
    ]

    # --------------------------------------------------------
    # Release the original predecessor.
    #
    # This should eventually drain:
    #
    # UTG fold
    # Hero raise
    # SB fold
    # BB fold
    # FLOP
    #
    # TURN/RIVER may remain blocked by their own street-local
    # obligations. The first E5 contract is ownership preservation.
    # --------------------------------------------------------

    observer.admit_card_disappearance(
        "utg",
        frame_id=16,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    # Production must consume the complete already-known physical
    # runout in strict street order during the same catch-up.
    assert observer.hand.street == "RIVER", (
        observer.hand.street
    )

    remaining = [
        row["observation"]["type"]
        for row
        in observer.pending_street_boundaries
    ]

    print(
        "street after predecessor release =",
        observer.hand.street,
    )

    print(
        "remaining boundary ownership =",
        remaining,
    )

    assert remaining == [], remaining

    assert observer.hand.board == [
        "As",
        "Kd",
        "7c",
        "2h",
        "Ad",
    ], observer.hand.board

    admitted_boundaries = [
        event
        for event in observer.events
        if event.get("type")
        == "STREET_BOUNDARY_ADMITTED"
    ]

    observed_boundary_sequence = [
        (
            event.get("frame"),
            event.get("street"),
        )
        for event in admitted_boundaries
    ]

    print(
        "admitted boundary sequence =",
        observed_boundary_sequence,
    )

    assert observed_boundary_sequence == [
        (13, "FLOP"),
        (14, "TURN"),
        (15, "RIVER"),
    ], observed_boundary_sequence

    # Every retained physical boundary is consumed exactly once.
    assert len(admitted_boundaries) == 3

    # The entire backlog is reconciled inside the chronology-release
    # publication transaction. The product must not expose transient
    # FLOP-only or TURN-only states when those later physical streets
    # were already known before release.
    assert len(observer.publications) == 1, (
        observer.publications
    )

    publication = observer.publications[0]

    assert publication["street"] == "RIVER"
    # Six PREFLOP actions plus two objectively boundary-proven
    # zero-commitment actions:
    #
    # TURN proves Hero completed FLOP with CHECK.
    # RIVER proves Hero completed TURN with CHECK.
    assert publication["action_count"] == 8

    text = publication["text"]

    assert "UTG folds" in text
    assert "HJ (Hero) raises to 2 BB" in text
    assert "SB folds" in text
    assert "BB folds" in text

    # The physical TURN and RIVER boundaries objectively complete
    # Hero's zero-commitment FLOP and TURN actions.
    semantic = observer.hand.semantic_actions()

    postflop = [
        (
            row["street"],
            row["seat"],
            row["action"],
        )
        for row in semantic
        if row["street"] != "PREFLOP"
    ]

    assert postflop == [
        ("FLOP", "hero", "CHECK"),
        ("TURN", "hero", "CHECK"),
    ], postflop

    assert text.count(
        "HJ (Hero) checks"
    ) == 2, text

    # Renderer formatting is intentionally checked by card identity,
    # not by assuming one exact board-label layout.
    for card in (
        "As",
        "Kd",
        "7c",
        "2h",
        "Ad",
    ):
        assert card in text, text

    # A second reconciliation attempt is a no-op: exactly-once
    # ownership has already consumed FLOP, TURN and RIVER.
    action_count = len(
        observer.hand.actions
    )
    event_count = len(
        observer.events
    )
    publication_count = len(
        observer.publications
    )

    again = (
        observer
        .reconcile_pending_street_boundaries()
    )

    assert again == ()
    assert len(observer.hand.actions) == action_count
    assert len(observer.events) == event_count
    assert (
        len(observer.publications)
        == publication_count
    )

    print()
    print(
        "V0.17 MULTI-STREET FLOP -> TURN -> RIVER "
        "CATCH-UP: PASS"
    )


if __name__ == "__main__":
    main()
