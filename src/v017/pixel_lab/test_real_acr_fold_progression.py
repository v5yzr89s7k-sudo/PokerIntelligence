"""
V0.17 Pixel Lab real ACR hand fold progression.

Private ACR truth is used only by the generator and by this offline
post-render comparator.

The physical observation side reads PNG pixels with the unchanged
production opponent_cards_visible() detector.
"""

from pathlib import Path
import shutil

import cv2

from src.events.detectors.card_presence import (
    opponent_cards_visible,
)

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)
from src.v017.pixel_lab.acr_seat_mapper import (
    map_acr_seats,
)
from src.v017.pixel_lab.acr_truth_timeline import (
    compile_truth_timeline,
)
from src.v017.pixel_lab.acr_pixel_renderer import (
    load_geometry,
    render_hand_progression,
)


ROOT = Path(__file__).resolve().parents[3]

CORPUS = (
    ROOT
    / "runtime/pixel_lab/acr_hand_histories"
)

WORK = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "real_acr_fold_progression"
)

HAND_ID = "2826874674"


def main():
    shutil.rmtree(
        WORK,
        ignore_errors=True,
    )

    hand = next(
        hand
        for _, hand in parse_corpus(CORPUS)
        if hand.hand_id == HAND_ID
    )

    truth = compile_truth_timeline(hand)
    seat_map = map_acr_seats(hand)
    geometry = load_geometry()

    rendered = render_hand_progression(
        hand=hand,
        truth_frames=truth,
        output_dir=WORK,
    )

    assert len(rendered["frames"]) == len(truth)

    print(
        "===== REAL ACR FOLD PIXEL PROGRESSION ====="
    )
    print("hand =", hand.hand_id)
    print("frames =", len(truth))

    observed_by_sequence = {}

    for truth_frame, path in zip(
        truth,
        rendered["frames"],
    ):
        image = cv2.imread(str(path))
        assert image is not None, path

        observed = {}

        for player in truth_frame.players:
            if player.sitting_out:
                continue

            seat = seat_map[
                int(player.seat_number)
            ]

            if seat == "hero":
                continue

            visible = bool(
                opponent_cards_visible(
                    image,
                    geometry["hole_cards"][seat],
                )
            )

            observed[seat] = visible

            expected_visible = not bool(
                player.folded
            )

            assert visible == expected_visible, (
                "physical fold mismatch",
                truth_frame.sequence,
                player.name,
                seat,
                player.folded,
                visible,
                path,
            )

        observed_by_sequence[
            truth_frame.sequence
        ] = observed

    print()
    print("===== DETECTED DISAPPEARANCES =====")

    transitions = []

    previous = None

    for truth_frame in truth:
        current = observed_by_sequence[
            truth_frame.sequence
        ]

        if previous is not None:
            for seat in sorted(current):
                if (
                    previous.get(seat) is True
                    and current.get(seat) is False
                ):
                    row = (
                        truth_frame.sequence,
                        truth_frame.street,
                        truth_frame.cause_actor,
                        truth_frame.cause_action,
                        seat,
                    )
                    transitions.append(row)
                    print(row)

        previous = current

    expected_fold_rows = []

    previous_folded = set()

    for truth_frame in truth:
        current_folded = {
            seat_map[int(player.seat_number)]
            for player in truth_frame.players
            if (
                not player.sitting_out
                and player.folded
                and seat_map[
                    int(player.seat_number)
                ] != "hero"
            )
        }

        newly_folded = sorted(
            current_folded - previous_folded
        )

        for seat in newly_folded:
            expected_fold_rows.append(
                (
                    truth_frame.sequence,
                    truth_frame.street,
                    truth_frame.cause_actor,
                    truth_frame.cause_action,
                    seat,
                )
            )

        previous_folded = current_folded

    assert tuple(transitions) == tuple(
        expected_fold_rows
    ), (
        "fold transition chronology mismatch",
        transitions,
        expected_fold_rows,
    )

    assert transitions, (
        "acceptance hand produced no opponent folds"
    )

    print()
    print(
        "expected fold transitions =",
        len(expected_fold_rows),
    )
    print(
        "observed fold transitions =",
        len(transitions),
    )
    print()
    print(
        "TRUTH FOLD STATE -> AUTHENTIC PIXELS: PASS"
    )
    print(
        "PIXELS -> PRODUCTION CARD DETECTOR: PASS"
    )
    print(
        "FOLD CHRONOLOGY EXACT MATCH: PASS"
    )
    print(
        "FRAMEHANDOBSERVER IMPORTED: NO"
    )
    print()
    print(
        "V0.17 REAL ACR FOLD PROGRESSION: PASS"
    )


if __name__ == "__main__":
    main()
