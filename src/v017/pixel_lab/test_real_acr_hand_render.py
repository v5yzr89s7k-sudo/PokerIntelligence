"""
V0.17 Pixel Lab: first full real-ACR-hand renderer acceptance.

This test remains entirely on the PRIVATE GENERATOR side.

It proves:

    real ACR TXT
        -> parser
        -> deterministic truth timeline
        -> deterministic ACR/physical seat mapping
        -> native 3456x2168 physical PNG progression

FrameHandObserver is deliberately NOT imported here.

Observer integration occurs only after this renderer boundary is proven.
"""

from pathlib import Path
import hashlib
import shutil

import cv2

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)
from src.v017.pixel_lab.acr_seat_mapper import (
    map_acr_seats,
    mapped_positions,
)
from src.v017.pixel_lab.acr_truth_timeline import (
    compile_truth_timeline,
)
from src.v017.pixel_lab.acr_pixel_renderer import (
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
      "real_acr_hand_2826874674"
)

HAND_ID = "2826874674"


def digest(path):
    return hashlib.sha256(
        Path(path).read_bytes()
    ).hexdigest()


def load_hand():
    return next(
        hand
        for _, hand in parse_corpus(CORPUS)
        if hand.hand_id == HAND_ID
    )


def render_once(destination):
    hand = load_hand()

    truth = compile_truth_timeline(hand)

    return (
        hand,
        truth,
        render_hand_progression(
            hand=hand,
            truth_frames=truth,
            output_dir=destination,
        ),
    )


def main():
    shutil.rmtree(
        WORK,
        ignore_errors=True,
    )
    WORK.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_a = WORK / "run_a"
    run_b = WORK / "run_b"
    run_c = WORK / "run_c"

    hand_a, truth_a, result_a = (
        render_once(run_a)
    )
    hand_b, truth_b, result_b = (
        render_once(run_b)
    )
    hand_c, truth_c, result_c = (
        render_once(run_c)
    )

    assert hand_a == hand_b == hand_c
    assert truth_a == truth_b == truth_c

    seat_map = map_acr_seats(hand_a)
    positions = mapped_positions(hand_a)

    print(
        "===== REAL ACR HAND ====="
    )
    print("hand =", hand_a.hand_id)
    print("players =", len(hand_a.players))
    print("truth frames =", len(truth_a))
    print(
        "ACR -> physical =",
        seat_map,
    )
    print("positions =", positions)

    # Previously established first-hand physical contract.
    assert seat_map[3] == "seat_upper_left"
    assert seat_map[4] == "seat_top"
    assert seat_map[5] == "seat_upper_right"
    assert seat_map[6] == "seat_mid_right"
    assert seat_map[7] == "seat_lower_right"
    assert seat_map[8] == "hero"

    assert positions[
        seat_map[3]
    ] == "BTN"
    assert positions[
        seat_map[4]
    ] == "SB"
    assert positions[
        seat_map[5]
    ] == "BB"
    assert positions[
        seat_map[6]
    ] == "UTG"
    assert positions[
        seat_map[7]
    ] == "HJ"
    assert positions["hero"] == "CO"

    frames_a = result_a["frames"]
    frames_b = result_b["frames"]
    frames_c = result_c["frames"]

    assert len(frames_a) == len(truth_a)
    assert len(frames_b) == len(truth_a)
    assert len(frames_c) == len(truth_a)

    assert frames_a

    for path in (
        frames_a[0],
        frames_a[-1],
    ):
        image = cv2.imread(str(path))
        assert image is not None, path
        assert image.shape[:2] == (
            2168,
            3456,
        ), (
            path,
            image.shape,
        )

    digests_a = tuple(
        digest(path)
        for path in frames_a
    )
    digests_b = tuple(
        digest(path)
        for path in frames_b
    )
    digests_c = tuple(
        digest(path)
        for path in frames_c
    )

    assert (
        digests_a
        == digests_b
        == digests_c
    ), "rendered PNG progression is nondeterministic"

    assert (
        result_a["private_manifest"]
        == result_b["private_manifest"]
        == result_c["private_manifest"]
    )

    print()
    print(
        "===== PHYSICAL RENDER ====="
    )
    print(
        "frame count =",
        len(frames_a),
    )
    print(
        "first =",
        frames_a[0],
    )
    print(
        "last =",
        frames_a[-1],
    )
    print(
        "first sha256 =",
        digests_a[0],
    )
    print(
        "last sha256 =",
        digests_a[-1],
    )

    changed = sum(
        1
        for before, after in zip(
            digests_a,
            digests_a[1:],
        )
        if before != after
    )

    print(
        "physical frame transitions =",
        changed,
    )

    assert changed > 0, (
        "truth progression produced no physical pixel changes"
    )

    print()
    print(
        "TRUTH -> RENDERER: PASS"
    )
    print(
        "NATIVE 3456x2168 OUTPUT: PASS"
    )
    print(
        "3/3 PIXEL DETERMINISM: PASS"
    )
    print(
        "FRAMEHANDOBSERVER IMPORTED: NO"
    )
    print()
    print(
        "V0.17 REAL ACR HAND RENDER: PASS"
    )


if __name__ == "__main__":
    main()
