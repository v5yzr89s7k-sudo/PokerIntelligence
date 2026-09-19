from pathlib import Path
import json
import shutil

import cv2
import numpy as np

from src.vision.stack_reader import (
    read_stack_native_fast,
)
from src.v017.native_seat_occupancy import (
    native_occupied_seats,
)


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)

SOURCE = (
    ROOT
    / "runtime/pixel_lab/substrates/"
    "native_6_7_8/substrate_8p.png"
)

GENERATOR_ROOT = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
    "novel_stack"
)

OBSERVER_ROOT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
    "novel_stack"
)

TRUTH_VALUE = 37.42
TARGET_SEAT = "hero"


def load_image(path):
    image = cv2.imread(str(path))
    assert image is not None, path
    assert image.shape[:2] == (2168, 3456)
    return image


def stack_crop(image, seat):
    r = GEOMETRY["stack_regions"][seat]

    return image[
        r["y"]:r["y"] + r["height"],
        r["x"]:r["x"] + r["width"],
    ].copy()


def green_mask(crop):
    hsv = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2HSV,
    )

    return cv2.inRange(
        hsv,
        np.array([35, 40, 40]),
        np.array([100, 255, 255]),
    )


def build_atlas(image):
    # Character boxes established from authentic ACR stack
    # crops during Pixel Lab calibration.
    donors = {
        "seat_top": (
            ("7", (123, 110, 25, 42)),
            ("9", (152, 110, 23, 42)),
            ("6", (196, 110, 23, 43)),
            ("2", (223, 110, 25, 42)),
        ),
        "seat_upper_right": (
            ("1", (104, 102, 15, 42)),
            ("2", (131, 102, 25, 42)),
            ("0", (160, 102, 23, 43)),
            ("5", (204, 102, 23, 43)),
            ("3", (231, 102, 23, 43)),
            # Authentic ACR decimal point. Keep the vertical canvas
            # aligned with the digit glyphs so paste_glyph() uses the
            # same baseline as every other character.
            (".", (187, 102, 10, 43)),
        ),
        "seat_mid_right": (
            ("8", (105, 107, 23, 43)),
            ("2", (132, 107, 25, 42)),
            ("1", (177, 107, 15, 42)),
            ("4", (203, 107, 26, 42)),
        ),
    }

    atlas = {}

    for seat, entries in donors.items():
        crop = stack_crop(
            image,
            seat,
        )
        mask = green_mask(crop)

        for char, box in entries:
            if char in atlas:
                continue

            x, y, w, h = box

            atlas[char] = (
                crop[
                    y:y + h,
                    x:x + w,
                ].copy(),
                mask[
                    y:y + h,
                    x:x + w,
                ].copy(),
            )

    assert set("3742.").issubset(
        atlas
    )

    return atlas


def paste_glyph(
    target,
    atlas,
    char,
    x,
    y,
):
    glyph, mask = atlas[char]

    h, w = glyph.shape[:2]

    roi = target[
        y:y + h,
        x:x + w,
    ]

    assert roi.shape[:2] == (
        h,
        w,
    )

    roi[mask > 0] = glyph[mask > 0]

    return x + w



def render_stack_value(
    image,
    *,
    geometry,
    seat,
    value,
    atlas=None,
):
    """
    Generator-side only.

    Render a two-decimal stack value using authentic ACR
    glyphs. No semantic evidence is returned.
    """
    if atlas is None:
        atlas = build_atlas(image)

    value_text = f"{float(value):.2f}"

    whole, fractional = value_text.split(".")

    assert len(fractional) == 2
    assert all(
        char in atlas
        for char in whole + fractional
    )

    r = geometry["stack_regions"][seat]

    original = image[
        r["y"]:r["y"] + r["height"],
        r["x"]:r["x"] + r["width"],
    ].copy()

    target = original.copy()
    old_mask = green_mask(target)

    # Clear authentic green stack text lane only.
    y1 = 96
    y2 = 154

    clean_strip = target[
        75:95,
        70:350,
    ]

    background = np.median(
        clean_strip.reshape(-1, 3),
        axis=0,
    ).astype(np.uint8)

    band = target[
        y1:y2,
    ].copy()

    band_mask = old_mask[
        y1:y2,
    ]

    band[
        band_mask > 0
    ] = background

    target[
        y1:y2,
    ] = band

    green_pixels = original[
        old_mask > 0
    ]

    assert len(green_pixels)

    foreground = np.median(
        green_pixels,
        axis=0,
    ).astype(np.uint8)

    # Match the proven authentic stack text lane.
    x = 105
    y = 106

    for index, char in enumerate(whole):
        x = paste_glyph(
            target,
            atlas,
            char,
            x,
            y,
        )

        if index != len(whole) - 1:
            x += 4

    x += 4

    # Use the authentic ACR decimal glyph rather than a synthetic
    # circle. OCR is sensitive to the decimal's shape/baseline when
    # surrounded by narrow glyph combinations such as 1-3-1.
    x = paste_glyph(
        target,
        atlas,
        ".",
        x,
        y,
    )

    x += 4

    for index, char in enumerate(
        fractional
    ):
        x = paste_glyph(
            target,
            atlas,
            char,
            x,
            y,
        )

        if index != len(fractional) - 1:
            x += 4

    x += 13

    # Authentic BB glyphs from the Hero stack crop.
    hero_original = stack_crop(
        image,
        "hero",
    )

    hero_mask = green_mask(
        hero_original
    )

    for bx, by, bw, bh in (
        (255, 106, 25, 42),
        (286, 106, 25, 42),
    ):
        glyph = hero_original[
            by:by + bh,
            bx:bx + bw,
        ]

        mask = hero_mask[
            by:by + bh,
            bx:bx + bw,
        ]

        roi = target[
            y:y + bh,
            x:x + bw,
        ]

        assert roi.shape[:2] == (
            bh,
            bw,
        )

        roi[mask > 0] = (
            glyph[mask > 0]
        )

        x += bw + 6

    image[
        r["y"]:r["y"] + r["height"],
        r["x"]:r["x"] + r["width"],
    ] = target

    return image

def generator_phase():
    shutil.rmtree(
        GENERATOR_ROOT,
        ignore_errors=True,
    )
    shutil.rmtree(
        OBSERVER_ROOT,
        ignore_errors=True,
    )

    GENERATOR_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )
    OBSERVER_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    image = load_image(SOURCE)
    atlas = build_atlas(image)

    print(
        "generator digit atlas =",
        tuple(sorted(atlas)),
    )

    original_hero = stack_crop(
        image,
        TARGET_SEAT,
    )

    hero = original_hero.copy()
    old_mask = green_mask(hero)

    # Clear only the authentic green stack text band.
    y1 = 96
    y2 = 154

    clean_strip = hero[
        75:95,
        70:350,
    ]

    background = np.median(
        clean_strip.reshape(-1, 3),
        axis=0,
    ).astype(np.uint8)

    band = hero[
        y1:y2,
    ].copy()

    band_mask = old_mask[
        y1:y2,
    ]

    band[
        band_mask > 0
    ] = background

    hero[
        y1:y2,
    ] = band

    green_pixels = original_hero[
        old_mask > 0
    ]

    assert len(green_pixels)

    foreground = np.median(
        green_pixels,
        axis=0,
    ).astype(np.uint8)

    # Render a genuinely novel value:
    #
    # 37.42 BB
    #
    # The complete number does not exist in the donor frame.
    x = 105
    y = 106

    x = paste_glyph(
        hero, atlas, "3", x, y
    )
    x += 4

    x = paste_glyph(
        hero, atlas, "7", x, y
    )
    x += 4

    x = paste_glyph(
        hero,
        atlas,
        ".",
        x,
        y,
    )

    x += 4

    x = paste_glyph(
        hero, atlas, "4", x, y
    )
    x += 4

    x = paste_glyph(
        hero, atlas, "2", x, y
    )
    x += 13

    # Authentic Hero BB glyphs.
    original_mask = green_mask(
        original_hero
    )

    for bx, by, bw, bh in (
        (255, 106, 25, 42),
        (286, 106, 25, 42),
    ):
        glyph = original_hero[
            by:by + bh,
            bx:bx + bw,
        ]

        mask = original_mask[
            by:by + bh,
            bx:bx + bw,
        ]

        roi = hero[
            y:y + bh,
            x:x + bw,
        ]

        assert roi.shape[:2] == (
            bh,
            bw,
        )

        roi[mask > 0] = (
            glyph[mask > 0]
        )

        x += bw + 6

    generated = image.copy()

    r = GEOMETRY[
        "stack_regions"
    ][TARGET_SEAT]

    generated[
        r["y"]:r["y"] + r["height"],
        r["x"]:r["x"] + r["width"],
    ] = hero

    private_image = (
        GENERATOR_ROOT
        / "generated.png"
    )

    observer_image = (
        OBSERVER_ROOT
        / "frame_0001.png"
    )

    assert cv2.imwrite(
        str(private_image),
        generated,
    )

    # Only pixels cross the isolation wall.
    assert cv2.imwrite(
        str(observer_image),
        generated,
    )

    (
        GENERATOR_ROOT
        / "truth.json"
    ).write_text(
        json.dumps(
            {
                "seat": TARGET_SEAT,
                "stack_bb": TRUTH_VALUE,
            },
            indent=2,
        )
        + "\n"
    )

    print(
        "generator truth =",
        TRUTH_VALUE,
    )


def assert_wall():
    files = tuple(
        sorted(
            OBSERVER_ROOT.iterdir()
        )
    )

    print(
        "observer input =",
        tuple(
            p.name
            for p in files
        ),
    )

    assert len(files) == 1
    assert files[0].name == (
        "frame_0001.png"
    )

    assert all(
        p.suffix.lower() == ".png"
        for p in files
    )

    print(
        "ONLY PIXELS CROSSED WALL: PASS"
    )


def observer_phase():
    # This function deliberately reads neither truth.json
    # nor any generator metadata.
    path = (
        OBSERVER_ROOT
        / "frame_0001.png"
    )

    image = load_image(path)

    crop = stack_crop(
        image,
        TARGET_SEAT,
    )

    result = read_stack_native_fast(
        crop
    )

    print(
        "observer result =",
        result,
    )

    return result, image


def comparator_phase(result):
    # Comparison occurs only after observation.
    truth = json.loads(
        (
            GENERATOR_ROOT
            / "truth.json"
        ).read_text()
    )

    observed = result.get(
        "stack_bb"
    )

    print(
        "offline truth =",
        truth["stack_bb"],
    )

    print(
        "offline observed =",
        observed,
    )

    assert observed == truth[
        "stack_bb"
    ], (
        truth,
        result,
    )

    print(
        "NOVEL STACK PIXEL RECOVERY: PASS"
    )


def main():
    print(
        "===== GENERATOR PHASE ====="
    )
    generator_phase()

    print()
    print(
        "===== ISOLATION WALL ====="
    )
    assert_wall()

    print()
    print(
        "===== OBSERVER PHASE ====="
    )
    result, image = observer_phase()

    print()
    print(
        "===== OFFLINE COMPARATOR ====="
    )
    comparator_phase(result)

    print()
    print(
        "===== OCCUPANCY REGRESSION ====="
    )

    occupied = tuple(
        native_occupied_seats(
            image,
            GEOMETRY,
        )
    )

    print(
        "occupied =",
        occupied,
    )

    assert len(occupied) == 8

    print(
        "NOVEL STACK OCCUPANCY: PASS"
    )

    print()
    print(
        "V0.17 PIXEL LAB NOVEL STACK: PASS"
    )


if __name__ == "__main__":
    main()
