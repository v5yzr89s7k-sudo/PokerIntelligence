from pathlib import Path

import cv2

from src.v017.native_seat_occupancy import (
    native_occupied_seats,
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

HAND_ID = "2826874674"

CORPUS = (
    ROOT
    / "runtime/pixel_lab/acr_hand_histories"
)

OUT = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "physical_bootstrap_occupancy"
)

EXPECTED = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_upper_left",
]


def main():
    hand = next(
        hand
        for _, hand in parse_corpus(CORPUS)
        if hand.hand_id == HAND_ID
    )

    truth = compile_truth_timeline(hand)

    rendered = render_hand_progression(
        hand=hand,
        truth_frames=truth,
        output_dir=OUT,
    )

    frame = rendered["frames"][8]

    image = cv2.imread(str(frame))
    assert image is not None, frame

    observed = native_occupied_seats(
        image,
        load_geometry(),
    )

    print("frame =", frame.name)
    print("expected =", EXPECTED)
    print("observed =", observed)

    assert observed == EXPECTED, (
        observed,
        EXPECTED,
    )

    print("EMPTY STACK ROIS AUTHENTIC: PASS")
    print("TARGET SIX-SEAT ROSTER: PASS")
    print(
        "V0.17 PHYSICAL BOOTSTRAP OCCUPANCY: PASS"
    )


if __name__ == "__main__":
    main()
