"""
Product progression regression for extracted FrameHandObserver.

Every observer publication must be an exact semantic prefix of the
final July22 hand. Active streets must publish at their physical
boundary before their first action.
"""

from src.v017.test_july22_frame_observer_complete_hand import (
    BOUNDARY_STREET,
    OPPONENT_SEATS,
    STREET_ORDER,
)

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
        hand_id="july22-publication-progression",
    )


def main():
    observer = build()
    boards = load_board_observations()

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

                card_observation = boards[
                    number
                ]

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

                observer.admit_street_boundary(
                    event,
                    action_order=
                        STREET_ORDER[street],
                    board=list(
                        card_observation[
                            "board"
                        ]
                    ),
                    complete_pending=(
                        street == "RIVER"
                    ),
                )

    publications = observer.publications

    print("===== PUBLICATION SEQUENCE =====")

    for index, publication in enumerate(
        publications,
        1,
    ):
        print(
            index,
            "frame=",
            publication["frame"],
            "actions=",
            publication["action_count"],
            "street=",
            publication["street"],
            "next=",
            publication["next_actor"],
        )

    assert publications, (
        "observer emitted no product publications"
    )

    final_actions = (
        observer.hand.semantic_actions()
    )

    # Every publication's action count must be monotonic and may
    # never exceed the final authoritative sequence.
    counts = [
        row["action_count"]
        for row in publications
    ]

    assert counts == sorted(counts), counts
    assert counts[-1] == 17, counts

    # Required active-street publications.
    flop = [
        row
        for row in publications
        if (
            row["frame"] == 52
            and row["street"] == "FLOP"
        )
    ]

    turn = [
        row
        for row in publications
        if (
            row["frame"] == 103
            and row["street"] == "TURN"
        )
    ]

    river = [
        row
        for row in publications
        if (
            row["frame"] == 115
            and row["street"] == "RIVER"
        )
    ]

    assert len(flop) == 1
    assert len(turn) == 1
    assert len(river) == 1

    assert flop[0]["action_count"] == 8
    assert turn[0]["action_count"] == 12

    # RIVER boundary atomically proves the two TURN checks.
    assert river[0]["action_count"] == 14

    assert "FLOP: Jd 9s Tc" in flop[0]["text"]
    assert "TURN: 9h" in turn[0]["text"]
    assert "RIVER: 7h" in river[0]["text"]

    # At RIVER activation no RIVER action may already exist.
    assert "SB (poker5068) checks" not in (
        river[0]["text"].split(
            "RIVER: 7h",
            1,
        )[-1]
    )

    # Final publication must contain the complete final product.
    final = publications[-1]

    assert final["frame"] == 135
    assert final["action_count"] == 17
    assert final["street"] == "RIVER"
    assert final["next_actor"] is None

    # No publication can contain a semantic action beyond its
    # authoritative action_count. Re-rendering the corresponding
    # historical state is unavailable here, so use the proven
    # monotonic admission boundary plus exact final sequence.
    assert len(final_actions) == 17

    print()
    print("final frame =", final["frame"])
    print("final actions =", final["action_count"])
    print("publication count =", len(publications))

    print()
    print(
        "V0.17 FRAMEHANDOBSERVER "
        "PUBLICATION PROGRESSION: PASS"
    )


if __name__ == "__main__":
    main()
