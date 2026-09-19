"""
V0.17 Pixel Lab real ACR physical board progression.

Private truth controls only renderer state and the offline comparator.
Rendered PNGs are independently measured with production
count_board_cards().

This proves physical street boundaries, NOT board-card identity.
"""

from pathlib import Path
import shutil

import cv2

from src.events.detectors.card_presence import (
    count_board_cards,
)

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
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
      "real_acr_board_progression"
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
    geometry = load_geometry()

    rendered = render_hand_progression(
        hand=hand,
        truth_frames=truth,
        output_dir=WORK,
    )

    assert len(rendered["frames"]) == len(truth)

    print(
        "===== REAL ACR PHYSICAL BOARD PROGRESSION ====="
    )
    print("hand =", hand.hand_id)
    print("frames =", len(truth))

    observed = []

    for truth_frame, path in zip(
        truth,
        rendered["frames"],
    ):
        image = cv2.imread(str(path))
        assert image is not None, path

        expected_count = len(
            truth_frame.board
        )

        physical_count = int(
            count_board_cards(
                image,
                geometry,
            )
        )

        assert physical_count == expected_count, (
            "board physical mismatch",
            truth_frame.sequence,
            truth_frame.street,
            truth_frame.cause_actor,
            truth_frame.cause_action,
            expected_count,
            physical_count,
            path,
        )

        observed.append(
            (
                truth_frame.sequence,
                truth_frame.street,
                truth_frame.cause_action,
                physical_count,
            )
        )

    print()
    print("===== PHYSICAL BOARD TRANSITIONS =====")

    transitions = []
    previous = None

    for row in observed:
        count = row[3]

        if (
            previous is not None
            and count != previous
        ):
            transitions.append(row)
            print(row)

        previous = count

    expected_transitions = []

    previous = None

    for truth_frame in truth:
        count = len(truth_frame.board)

        if (
            previous is not None
            and count != previous
        ):
            expected_transitions.append(
                (
                    truth_frame.sequence,
                    truth_frame.street,
                    truth_frame.cause_action,
                    count,
                )
            )

        previous = count

    assert tuple(transitions) == tuple(
        expected_transitions
    ), (
        transitions,
        expected_transitions,
    )

    counts = tuple(
        row[3]
        for row in transitions
    )

    assert counts == (3,), (
        "acceptance hand expected only a flop boundary",
        counts,
    )

    # This specific real hand ends on the flop after the final
    # opponent folds. The generic 0/3/4/5 primitive is proven
    # separately by test_authentic_board_pixels.
    assert truth[-1].street == "FLOP"
    assert len(truth[-1].board) == 3

    print()
    print(
        "truth boundary transitions =",
        expected_transitions,
    )
    print(
        "physical boundary transitions =",
        transitions,
    )

    print()
    print(
        "TRUTH BOARD COUNT -> AUTHENTIC PIXELS: PASS"
    )
    print(
        "PIXELS -> PRODUCTION BOARD DETECTOR: PASS"
    )
    print(
        "PHYSICAL STREET CHRONOLOGY EXACT MATCH: PASS"
    )
    print(
        "BOARD IDENTITY CLAIMED: NO"
    )
    print(
        "FRAMEHANDOBSERVER IMPORTED: NO"
    )
    print()
    print(
        "V0.17 REAL ACR BOARD PROGRESSION: PASS"
    )


if __name__ == "__main__":
    main()
