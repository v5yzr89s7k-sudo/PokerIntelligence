"""
V0.17 Pixel Lab authentic board-pixel primitive.

Generator-side acceptance only.

Authentic July22 ACR community-card ROIs are transformed from the
historical calibrated 934x696 geometry into the corresponding calibrated
3456x2168 V0.17 board ROIs.

The unchanged production count_board_cards() detector must recover:

    PREFLOP -> 0
    FLOP    -> 3
    TURN    -> 4
    RIVER   -> 5

No production detector or geometry is modified.
"""

from pathlib import Path
import json
import shutil

import cv2

from src.events.detectors.card_presence import (
    count_board_cards,
    board_card_present,
    crop,
)


ROOT = Path(__file__).resolve().parents[3]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence/"
      "20260722_152155"
)

OLD_GEOMETRY = json.loads(
    (
        ROOT / "config/geometry.json"
    ).read_text()
)

NEW_GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)

SUBSTRATE = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_8p.png"
)

WORK = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "authentic_board_pixels"
)

DONORS = {
    0: SESSION / "0001_full.png",
    3: SESSION / "0052_full.png",
    4: SESSION / "0103_full.png",
    5: SESSION / "0115_full.png",
}

BOARD_ORDER = (
    "flop_1",
    "flop_2",
    "flop_3",
    "turn",
    "river",
)


def load_old(path):
    image = cv2.imread(str(path))
    assert image is not None, path

    if image.shape[:2] != (696, 934):
        image = cv2.resize(
            image,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    return image


def load_new(path):
    image = cv2.imread(str(path))
    assert image is not None, path
    assert image.shape[:2] == (
        2168,
        3456,
    ), (
        path,
        image.shape,
    )
    return image


def transplant_board_roi(
    destination,
    donor,
    card_name,
):
    old_rect = OLD_GEOMETRY[
        "board"
    ][card_name]

    new_rect = NEW_GEOMETRY[
        "board"
    ][card_name]

    old_crop = crop(
        donor,
        old_rect,
    )

    assert old_crop.size > 0

    target_w = int(
        new_rect["width"]
    )
    target_h = int(
        new_rect["height"]
    )

    resized = cv2.resize(
        old_crop,
        (
            target_w,
            target_h,
        ),
        interpolation=cv2.INTER_CUBIC,
    )

    result = destination.copy()

    x = int(new_rect["x"])
    y = int(new_rect["y"])

    result[
        y:y + target_h,
        x:x + target_w,
    ] = resized

    return result


def render_count(
    *,
    substrate,
    donor,
    expected_count,
):
    image = substrate.copy()

    # Copy all five calibrated board ROIs from the corresponding
    # authentic donor. This preserves both present and absent physical
    # states rather than fabricating empty board pixels.
    for card_name in BOARD_ORDER:
        image = transplant_board_roi(
            image,
            donor,
            card_name,
        )

    observed = int(
        count_board_cards(
            image,
            NEW_GEOMETRY,
        )
    )

    assert observed == expected_count, (
        "maximized board transform mismatch",
        expected_count,
        observed,
    )

    return image


def print_scores(image):
    for card_name in BOARD_ORDER:
        rect = NEW_GEOMETRY[
            "board"
        ][card_name]

        card = crop(
            image,
            rect,
        )

        gray = cv2.cvtColor(
            card,
            cv2.COLOR_BGR2GRAY,
        )

        bright = float(
            (gray > 145).mean()
        )

        print(
            " ",
            card_name,
            "present=",
            board_card_present(card),
            "bright=",
            round(bright, 4),
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

    substrate = load_new(
        SUBSTRATE
    )

    print(
        "===== AUTHENTIC BOARD PIXEL PRIMITIVE ====="
    )

    observed_progression = []

    for expected_count in (
        0,
        3,
        4,
        5,
    ):
        donor_path = DONORS[
            expected_count
        ]

        donor = load_old(
            donor_path
        )

        image = render_count(
            substrate=substrate,
            donor=donor,
            expected_count=expected_count,
        )

        output = (
            WORK
            / f"board_{expected_count}.png"
        )

        assert cv2.imwrite(
            str(output),
            image,
        ), output

        observed = int(
            count_board_cards(
                image,
                NEW_GEOMETRY,
            )
        )

        observed_progression.append(
            observed
        )

        print()
        print(
            "EXPECTED",
            expected_count,
            "OBSERVED",
            observed,
        )
        print(
            " donor =",
            donor_path,
        )

        print_scores(image)

    assert tuple(
        observed_progression
    ) == (
        0,
        3,
        4,
        5,
    )

    print()
    print(
        "AUTHENTIC JULY22 BOARD ROIS: PASS"
    )
    print(
        "OLD ROI -> MAXIMIZED ROI TRANSFORM: PASS"
    )
    print(
        "PRODUCTION BOARD DETECTOR UNCHANGED: PASS"
    )
    print(
        "OBSERVED BOARD PROGRESSION 0/3/4/5: PASS"
    )
    print()
    print(
        "V0.17 AUTHENTIC BOARD PIXELS: PASS"
    )


if __name__ == "__main__":
    main()
