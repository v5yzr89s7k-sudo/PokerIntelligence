from pathlib import Path
import json

import cv2
import numpy as np

from src.api.canonical_frame import to_canonical_frame
from src.events.detectors.card_presence import SEAT_ORDER


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = ROOT / "config/geometry.json"

TEMPORAL_JSON = (
    ROOT
    / "runtime/debug"
    / "hand_participant_temporal_diagnostic.json"
)

OUT_JSON = (
    ROOT
    / "runtime/debug"
    / "opponent_card_feature_analysis.json"
)

OUT_DIR = (
    ROOT
    / "runtime/debug"
    / "opponent_card_feature_crops"
)


def crop(image, rect):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    return image[
        y:y + h,
        x:x + w,
    ].copy()


def features(image):
    if image is None or image.size == 0:
        return {
            "bright_ratio": 0.0,
            "saturated_ratio": 0.0,
            "dark_ratio": 0.0,
            "edge_density": 0.0,
            "gray_std": 0.0,
            "mean_bgr": [0.0, 0.0, 0.0],
            "mean_hsv": [0.0, 0.0, 0.0],
        }

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    hsv = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2HSV,
    )

    edges = cv2.Canny(
        gray,
        60,
        140,
    )

    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    return {
        "bright_ratio": float(
            (gray > 145).mean()
        ),
        "saturated_ratio": float(
            (saturation > 70).mean()
        ),
        "dark_ratio": float(
            (gray < 55).mean()
        ),
        "edge_density": float(
            (edges > 0).mean()
        ),
        "gray_std": float(
            np.std(gray)
        ),
        "mean_bgr": [
            round(float(value), 3)
            for value in image.mean(
                axis=(0, 1)
            )
        ],
        "mean_hsv": [
            round(float(value), 3)
            for value in hsv.mean(
                axis=(0, 1)
            )
        ],
    }


def normalized_similarity(first, second):
    if (
        first is None
        or second is None
        or first.size == 0
        or second.size == 0
    ):
        return 0.0

    height = min(
        first.shape[0],
        second.shape[0],
    )

    width = min(
        first.shape[1],
        second.shape[1],
    )

    first = first[:height, :width]
    second = second[:height, :width]

    first_gray = cv2.cvtColor(
        first,
        cv2.COLOR_BGR2GRAY,
    ).astype(np.float32)

    second_gray = cv2.cvtColor(
        second,
        cv2.COLOR_BGR2GRAY,
    ).astype(np.float32)

    first_gray = (
        first_gray - first_gray.mean()
    ) / (
        first_gray.std() + 1e-6
    )

    second_gray = (
        second_gray - second_gray.mean()
    ) / (
        second_gray.std() + 1e-6
    )

    correlation = float(
        np.mean(
            first_gray * second_gray
        )
    )

    return round(
        max(-1.0, min(1.0, correlation)),
        6,
    )


def strongest_frame_for_seat(data, seat):
    first_path = (
        data["maximum_frame"]
        [seat]
        .get("card_1")
    )

    second_path = (
        data["maximum_frame"]
        [seat]
        .get("card_2")
    )

    candidates = [
        value
        for value in [
            first_path,
            second_path,
        ]
        if value
    ]

    if not candidates:
        return None

    # Use the frame that produced the stronger of the two recorded maxima.
    first_score = float(
        data["maxima"][seat]["card_1"]
    )

    second_score = float(
        data["maxima"][seat]["card_2"]
    )

    return Path(
        first_path
        if first_score >= second_score
        else second_path
    )


def main():
    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    temporal = json.loads(
        TEMPORAL_JSON.read_text()
    )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    analysis = {}

    for seat in SEAT_ORDER:
        frame_path = strongest_frame_for_seat(
            temporal,
            seat,
        )

        if (
            frame_path is None
            or not frame_path.exists()
        ):
            analysis[seat] = {
                "error": "no usable frame",
            }
            continue

        original = cv2.imread(
            str(frame_path)
        )

        if original is None:
            analysis[seat] = {
                "error": (
                    f"could not read {frame_path}"
                ),
            }
            continue

        canonical = to_canonical_frame(
            original,
            geometry,
        )

        regions = (
            geometry
            .get("hole_cards", {})
            .get(seat, {})
        )

        first = crop(
            canonical,
            regions["card_1"],
        )

        second = crop(
            canonical,
            regions["card_2"],
        )

        cv2.imwrite(
            str(
                OUT_DIR
                / f"{seat}_card_1.png"
            ),
            first,
        )

        cv2.imwrite(
            str(
                OUT_DIR
                / f"{seat}_card_2.png"
            ),
            second,
        )

        # Calibrated card rectangles may differ slightly in width/height.
        # Normalize both crops to a shared display height before concatenating.
        target_height = max(
            first.shape[0],
            second.shape[0],
        )

        def resize_to_height(image, height):
            if image.shape[0] == height:
                return image

            scale = height / float(
                image.shape[0]
            )

            target_width = max(
                1,
                int(round(
                    image.shape[1] * scale
                )),
            )

            return cv2.resize(
                image,
                (
                    target_width,
                    height,
                ),
                interpolation=cv2.INTER_CUBIC,
            )

        display_first = resize_to_height(
            first,
            target_height,
        )

        display_second = resize_to_height(
            second,
            target_height,
        )

        combined = cv2.hconcat([
            display_first,
            display_second,
        ])

        cv2.imwrite(
            str(
                OUT_DIR
                / f"{seat}_pair.png"
            ),
            combined,
        )

        analysis[seat] = {
            "frame": str(frame_path),
            "card_1": features(first),
            "card_2": features(second),
            "pair_similarity": (
                normalized_similarity(
                    first,
                    second,
                )
            ),
        }

    payload = {
        "analysis": analysis,
    }

    OUT_JSON.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n"
    )

    for seat in SEAT_ORDER:
        result = analysis[seat]

        if "error" in result:
            print(
                f"{seat:20s} "
                f"ERROR {result['error']}"
            )
            continue

        first = result["card_1"]
        second = result["card_2"]

        print(
            f"{seat:20s} "
            f"bright=({first['bright_ratio']:.3f},"
            f"{second['bright_ratio']:.3f}) "
            f"sat=({first['saturated_ratio']:.3f},"
            f"{second['saturated_ratio']:.3f}) "
            f"edge=({first['edge_density']:.3f},"
            f"{second['edge_density']:.3f}) "
            f"similarity={result['pair_similarity']:.3f}"
        )

    print()
    print("json:", OUT_JSON)
    print("crops:", OUT_DIR)


if __name__ == "__main__":
    main()
