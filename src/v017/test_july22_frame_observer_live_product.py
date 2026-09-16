"""
End-to-end v0.17 product-file regression.

Raw July22 frames -> FrameHandObserver -> semantic admissions ->
observer publications -> atomic current_hand.txt sink.

The file must always equal the latest authoritative publication.
"""

import tempfile
from pathlib import Path

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)

from src.v017.live_product_sink import (
    publish_current_hand_text,
)

from src.v017.test_july22_frame_observer_complete_hand import (
    BOUNDARY_STREET,
    OPPONENT_SEATS,
    STREET_ORDER,
)

from src.v017.july22_frame_preflop_replay import (
    ACTION_ORDER,
    GEOMETRY,
    PLAYERS,
    TRACKED_STACKS,
    load_board_observations,
    load_frame,
)


EXPECTED_PUBLICATION_FRAMES = [
    38,
    40,
    40,
    42,
    48,
    51,
    52,
    90,
    97,
    101,
    103,
    115,
    127,
    135,
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
        hand_id="july22-live-product",
    )


def main():
    observer = build()
    boards = load_board_observations()

    written = 0
    written_frames = []

    with tempfile.TemporaryDirectory() as td:
        product_path = (
            Path(td)
            / "runtime"
            / "live"
            / "current_hand.txt"
        )

        for number in range(1, 136):
            before_publications = len(
                observer.publications
            )

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

            new_publications = (
                observer.publications[
                    before_publications:
                ]
            )

            for publication in new_publications:
                publish_current_hand_text(
                    publication["text"],
                    product_path,
                )

                written += 1
                written_frames.append(
                    publication["frame"]
                )

                disk_text = (
                    product_path.read_text(
                        encoding="utf-8"
                    )
                )

                assert (
                    disk_text
                    == publication["text"]
                ), (
                    "product file differs from "
                    "authoritative publication: "
                    f"frame={number}"
                )

        assert written == 14, written

        assert (
            written_frames
            == EXPECTED_PUBLICATION_FRAMES
        ), written_frames

        assert (
            product_path.read_text(
                encoding="utf-8"
            )
            == observer.publications[-1][
                "text"
            ]
        )

        final_text = product_path.read_text(
            encoding="utf-8"
        )

        assert "RIVER: 7h" in final_text
        assert "BB (Birkam) bets 6.75 BB" in final_text
        assert "SB (poker5068) folds" in final_text

        assert observer.hand.street == "RIVER"
        assert observer.hand.next_actor is None
        assert len(
            observer.hand.semantic_actions()
        ) == 17

        print(
            "publication frames:",
            written_frames,
        )
        print(
            "writes:",
            written,
        )
        print(
            "final actions:",
            len(
                observer.hand.semantic_actions()
            ),
        )
        print()
        print(
            "V0.17 JULY22 LIVE PRODUCT FILE: PASS"
        )


if __name__ == "__main__":
    main()
