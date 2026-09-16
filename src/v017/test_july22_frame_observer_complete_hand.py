"""
Extracted FrameHandObserver complete July22 regression.

Raw frames -> physical observations -> dedicated admission primitives
-> HandEngine.

Fixture-specific board identity and postflop action orders remain here,
outside production FrameHandObserver.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)

from src.v017.july22_frame_preflop_replay import (
    ACTION_ORDER,
    GEOMETRY,
    PLAYERS,
    TRACKED_STACKS,
    load_board_observations,
    load_frame,
)


OPPONENT_SEATS = [
    "seat_upper_left",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "seat_lower_left",
]

STREET_ORDER = {
    "FLOP": [
        "hero",
        "seat_lower_left",
        "seat_lower_right",
    ],
    "TURN": [
        "hero",
        "seat_lower_left",
    ],
    "RIVER": [
        "hero",
        "seat_lower_left",
    ],
}

BOUNDARY_STREET = {
    "FLOP_BOUNDARY_PHYSICAL": "FLOP",
    "TURN_BOUNDARY_PHYSICAL": "TURN",
    "RIVER_BOUNDARY_PHYSICAL": "RIVER",
}

EXPECTED = [
    ("PREFLOP", "hero", "POST_SMALL_BLIND", 0.5, None),
    ("PREFLOP", "seat_lower_left", "POST_BIG_BLIND", 1.0, None),
    ("PREFLOP", "seat_upper_left", "FOLD", None, None),
    ("PREFLOP", "seat_upper_right", "FOLD", None, None),
    ("PREFLOP", "seat_mid_right", "FOLD", None, None),
    ("PREFLOP", "seat_lower_right", "RAISE", None, 2.0),
    ("PREFLOP", "hero", "CALL", 1.5, None),
    ("PREFLOP", "seat_lower_left", "CALL", 1.0, None),
    ("FLOP", "hero", "CHECK", None, None),
    ("FLOP", "seat_lower_left", "BET", 3.37, None),
    ("FLOP", "seat_lower_right", "FOLD", None, None),
    ("FLOP", "hero", "CALL", 3.37, None),
    ("TURN", "hero", "CHECK", None, None),
    ("TURN", "seat_lower_left", "CHECK", None, None),
    ("RIVER", "hero", "CHECK", None, None),
    ("RIVER", "seat_lower_left", "BET", 6.75, None),
    ("RIVER", "hero", "FOLD", None, None),
]


def build():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
        geometry=GEOMETRY,
        trusted_stacks=dict(
            TRACKED_STACKS
        ),
        opponent_seats=OPPONENT_SEATS,
        quantitative_seats=[
            "seat_lower_right",
            "hero",
            "seat_lower_left",
        ],
        hero_seat="hero",
        hand_id="july22-extracted-complete",
    )


def semantic(row):
    return (
        row["street"],
        row["seat"],
        row["action"],
        row["amount_bb"],
        row["raise_to_bb"],
    )


def main():
    observer = build()
    boards = load_board_observations()

    physical_boundaries = []
    admitted_boundaries = []

    for number in range(1, 136):
        result = observer.process_frame(
            load_frame(number),
            frame_id=number,
        )

        for event in result.events:
            typ = event["type"]

            if typ in {
                "OPPONENT_CARDS_DISAPPEARED",
                "HERO_CARDS_DISAPPEARED_PHYSICAL",
            }:
                observer.admit_card_disappearance(
                    event["seat"],
                    frame_id=number,
                    physical_type=typ,
                )

            elif (
                typ
                == "STACK_QUANTITATIVE_OBSERVATION"
            ):
                observer.admit_quantitative_observation(
                    event
                )

            elif typ in BOUNDARY_STREET:
                street = BOUNDARY_STREET[
                    typ
                ]

                physical_boundaries.append(
                    (
                        number,
                        typ,
                        event["board_count"],
                    )
                )

                card_observation = boards.get(
                    number
                )

                assert (
                    card_observation
                    is not None
                ), (
                    "missing board identity "
                    f"frame={number}"
                )

                if (
                    street == "FLOP"
                    and card_observation[
                        "hero_cards"
                    ]
                ):
                    observer.hand.observe_hero_cards(
                        list(
                            card_observation[
                                "hero_cards"
                            ]
                        )
                    )

                # FLOP and TURN should already be closed from
                # ordinary action evidence.
                #
                # RIVER appearance is the objective proof that
                # Hero and BB completed TURN with zero additional
                # commitment.
                complete_pending = (
                    street == "RIVER"
                )

                emitted = (
                    observer.admit_street_boundary(
                        event,
                        action_order=
                            STREET_ORDER[street],
                        board=list(
                            card_observation[
                                "board"
                            ]
                        ),
                        complete_pending=
                            complete_pending,
                    )
                )

                assert emitted, (
                    "boundary not admitted: "
                    f"frame={number} "
                    f"street={street} "
                    f"next_actor="
                    f"{observer.hand.next_actor}"
                )

                admitted = [
                    row
                    for row in emitted
                    if row["type"]
                    == "STREET_BOUNDARY_ADMITTED"
                ]

                assert len(admitted) == 1

                admitted_boundaries.append(
                    (
                        number,
                        admitted[0]["street"],
                    )
                )

    observed = [
        semantic(row)
        for row
        in observer.hand.semantic_actions()
    ]

    print("===== BOUNDARIES =====")
    print("physical =", physical_boundaries)
    print("admitted =", admitted_boundaries)

    print()
    print("===== ACTIONS =====")
    for row in observer.hand.semantic_actions():
        print(
            row["sequence"],
            row["street"],
            row["seat"],
            row["action"],
            row["amount_bb"],
            row["raise_to_bb"],
        )

    print()
    print("===== TRUSTED STACKS =====")
    print(observer.trusted_stacks)

    assert physical_boundaries == [
        (52, "FLOP_BOUNDARY_PHYSICAL", 3),
        (103, "TURN_BOUNDARY_PHYSICAL", 4),
        (115, "RIVER_BOUNDARY_PHYSICAL", 5),
    ]

    assert admitted_boundaries == [
        (52, "FLOP"),
        (103, "TURN"),
        (115, "RIVER"),
    ]

    assert observed == EXPECTED, (
        "complete semantic mismatch: "
        f"{observed}"
    )

    assert observer.hand.street == "RIVER"
    assert observer.hand.next_actor is None

    assert observer.hand.board == [
        "Jd",
        "9s",
        "Tc",
        "9h",
        "7h",
    ]

    assert observer.hand.hero_cards == [
        "Qd",
        "Ah",
    ]

    assert (
        observer.trusted_stacks[
            "seat_lower_right"
        ]
        == 56.55
    )

    assert (
        observer.trusted_stacks[
            "seat_lower_left"
        ]
        == 37.45
    )

    assert (
        observer.trusted_stacks[
            "hero"
        ]
        == 6.90
    )

    turn_completion = [
        event
        for event in observer.events
        if (
            event.get("type")
            == "STREET_BOUNDARY_COMPLETION"
            and event.get("frame")
            == 115
        )
    ]

    assert [
        (
            row["seat"],
            row["semantic_action"],
        )
        for row in turn_completion
    ] == [
        ("hero", "CHECK"),
        ("seat_lower_left", "CHECK"),
    ]

    print()
    print(
        "G3.5 COMPLETE JULY22 "
        "FRAMEHANDOBSERVER: PASS"
    )


if __name__ == "__main__":
    main()
