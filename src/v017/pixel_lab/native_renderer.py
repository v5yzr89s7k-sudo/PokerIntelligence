from pathlib import Path
import json

import cv2


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY_PATH = (
    ROOT / "config/v017/geometry_maximized.json"
)


def _geometry():
    return json.loads(
        GEOMETRY_PATH.read_text()
    )


def _load(path):
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


def _rect_union(*rects):
    x1 = min(r["x"] for r in rects)
    y1 = min(r["y"] for r in rects)

    x2 = max(
        r["x"] + r["width"]
        for r in rects
    )
    y2 = max(
        r["y"] + r["height"]
        for r in rects
    )

    return x1, y1, x2, y2


def seat_visual_rect(seat):
    """
    Generator-side visual patch.

    Include both the native seat/nameplate region and native
    stack region. This is not observer geometry modification;
    it merely defines which authentic ACR pixels are copied.
    """
    g = _geometry()

    seat_rect = g["seat_regions"][seat]
    stack_rect = g["stack_regions"][seat]

    x1, y1, x2, y2 = _rect_union(
        seat_rect,
        stack_rect,
    )

    # Small fixed safety margin remains generator-side.
    margin = 20

    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(3456, x2 + margin)
    y2 = min(2168, y2 + margin)

    return x1, y1, x2, y2


def transplant_seat_visual(
    destination_image,
    donor_image,
    seat,
):
    x1, y1, x2, y2 = seat_visual_rect(
        seat
    )

    result = destination_image.copy()

    result[
        y1:y2,
        x1:x2,
    ] = donor_image[
        y1:y2,
        x1:x2,
    ]

    return result


def build_generated_occupancy_frames(
    *,
    substrate_8p,
    donor_7p,
    donor_6p,
    output_dir,
):
    substrate_8p = _load(substrate_8p)
    donor_7p = _load(donor_7p)
    donor_6p = _load(donor_6p)

    output_dir = Path(output_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 8-player control: unchanged authentic native substrate.
    generated_8p = substrate_8p.copy()

    # Remove only upper-left using an authentic empty upper-left
    # appearance from the real seven-player ACR frame.
    generated_7p = transplant_seat_visual(
        generated_8p,
        donor_7p,
        "seat_upper_left",
    )

    # Then remove lower-left using authentic empty pixels from
    # the real six-player ACR frame.
    generated_6p = transplant_seat_visual(
        generated_7p,
        donor_6p,
        "seat_lower_left",
    )

    paths = {
        "8p": output_dir / "generated_8p.png",
        "7p": output_dir / "generated_7p.png",
        "6p": output_dir / "generated_6p.png",
    }

    assert cv2.imwrite(
        str(paths["8p"]),
        generated_8p,
    )
    assert cv2.imwrite(
        str(paths["7p"]),
        generated_7p,
    )
    assert cv2.imwrite(
        str(paths["6p"]),
        generated_6p,
    )

    return paths
