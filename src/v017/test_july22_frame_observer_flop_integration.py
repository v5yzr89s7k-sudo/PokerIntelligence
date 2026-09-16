"""
G3.5C integrated real-frame FLOP regression.

Raw July 22 frames flow through FrameHandObserver:
    process_frame()
        -> physical observations
    dedicated admission primitives
        -> HandEngine semantics

Fixture-specific board identity and postflop action order remain in
this replay adapter, never in FrameHandObserver.
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

FLOP_ACTION_ORDER = [
    "hero",
    "seat_lower_left",
    "seat_lower_right",
]

EXPECTED = [
    ("POST_SMALL_BLIND", "hero", 0.5, None),
    ("POST_BIG_BLIND", "seat_lower_left", 1.0, None),
    ("FOLD", "seat_upper_left", None, None),
    ("FOLD", "seat_upper_right", None, None),
    ("FOLD", "seat_mid_right", None, None),
    ("RAISE", "seat_lower_right", None, 2.0),
    ("CALL", "hero", 1.5, None),
    ("CALL", "seat_lower_left", 1.0, None),
    ("CHECK", "hero", None, None),
    ("BET", "seat_lower_left", 3.37, None),
    ("FOLD", "seat_lower_right", None, None),
    ("CALL", "hero", 3.37, None),
]


def build_observer():
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
        hand_id="july22-g3.5c-flop",
    )


def semantic_tuple(row):
    return (
        row["action"],
        row["seat"],
        row["amount_bb"],
        row["raise_to_bb"],
    )


def main():
    observer = build_observer()
    board_observations = (
        load_board_observations()
    )

    physical_boundaries = []
    admitted_boundaries = []

    # Stop at 102. This proves the complete FLOP while preventing
    # the TURN boundary from entering this milestone.
    for number in range(1, 103):
        frame = load_frame(number)

        result = observer.process_frame(
            frame,
            frame_id=number,
        )

        for event in result.events:
            event_type = event["type"]

            if event_type in {
                "OPPONENT_CARDS_DISAPPEARED",
                "HERO_CARDS_DISAPPEARED_PHYSICAL",
            }:
                observer.admit_card_disappearance(
                    event["seat"],
                    frame_id=number,
                    physical_type=event_type,
                )

            elif (
                event_type
                == "STACK_QUANTITATIVE_OBSERVATION"
            ):
                observer.admit_quantitative_observation(
                    event
                )

            elif (
                event_type
                == "FLOP_BOUNDARY_PHYSICAL"
            ):
                physical_boundaries.append(
                    (
                        number,
                        event_type,
                        event["board_count"],
                    )
                )

                assert (
                    observer.hand.next_actor
                    is None
                ), (
                    "PREFLOP not closed at physical FLOP: "
                    f"frame={number} "
                    f"next_actor={observer.hand.next_actor}"
                )

                card_observation = (
                    board_observations.get(
                        number
                    )
                )

                assert (
                    card_observation
                    is not None
                ), (
                    "missing external FLOP identity "
                    f"at frame={number}"
                )

                hero_cards = list(
                    card_observation[
                        "hero_cards"
                    ]
                )

                if hero_cards:
                    observer.hand.observe_hero_cards(
                        hero_cards
                    )

                emitted = (
                    observer.admit_street_boundary(
                        event,
                        action_order=
                            FLOP_ACTION_ORDER,
                        board=list(
                            card_observation[
                                "board"
                            ]
                        ),
                    )
                )

                assert len(emitted) == 1
                assert (
                    emitted[0]["type"]
                    == "STREET_BOUNDARY_ADMITTED"
                )

                admitted_boundaries.append(
                    (
                        number,
                        emitted[0]["street"],
                        tuple(
                            emitted[0]["board"]
                        ),
                    )
                )

    observed = [
        semantic_tuple(row)
        for row
        in observer.hand.semantic_actions()
        if row["street"] in {
            "PREFLOP",
            "FLOP",
        }
    ]

    print("===== PHYSICAL BOUNDARIES =====")
    for row in physical_boundaries:
        print(row)

    print()
    print("===== ADMITTED BOUNDARIES =====")
    for row in admitted_boundaries:
        print(row)

    print()
    print("===== SEMANTIC ACTIONS =====")
    for row in observer.hand.semantic_actions():
        print(row)

    print()
    print("===== TRUSTED STACKS =====")
    print(observer.trusted_stacks)

    assert physical_boundaries == [
        (
            52,
            "FLOP_BOUNDARY_PHYSICAL",
            3,
        ),
    ]

    assert admitted_boundaries == [
        (
            52,
            "FLOP",
            (
                "Jd",
                "9s",
                "Tc",
            ),
        ),
    ]

    assert observed == EXPECTED, (
        "G3.5C semantic mismatch: "
        f"{observed}"
    )

    assert observer.hand.street == "FLOP"
    assert observer.hand.next_actor is None

    assert observer.hand.board == [
        "Jd",
        "9s",
        "Tc",
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
        == 44.20
    )

    assert (
        observer.trusted_stacks[
            "hero"
        ]
        == 6.90
    )

    hero_check = [
        event
        for event in observer.events
        if (
            event.get("type")
            == "CHRONOLOGY_COMPLETION"
            and event.get("seat")
            == "hero"
            and event.get("frame")
            == 90
            and event.get(
                "semantic_action"
            )
            == "CHECK"
        )
    ]

    assert len(hero_check) == 1
    assert (
        hero_check[0]["proved_by"]
        == "seat_lower_left"
    )

    hero_call = [
        event
        for event in observer.events
        if (
            event.get("type")
            == "QUANTITATIVE_ADMITTED"
            and event.get("seat")
            == "hero"
            and event.get("frame")
            == 101
            and event.get(
                "semantic_action"
            )
            == "CALL"
        )
    ]

    assert len(hero_call) == 1

    assert (
        hero_call[0][
            "physical_delta_bb"
        ]
        == 3.38
    )

    assert (
        hero_call[0][
            "normalized_delta_bb"
        ]
        == 3.37
    )

    assert (
        hero_call[0][
            "snapped_to_call_price"
        ]
        is True
    )

    print()
    print(
        "G3.5C JULY22 FRAMEHANDOBSERVER "
        "FLOP INTEGRATION: PASS"
    )


if __name__ == "__main__":
    main()
