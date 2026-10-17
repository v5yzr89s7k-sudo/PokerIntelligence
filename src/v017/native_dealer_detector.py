from pathlib import Path

import cv2
import json

from src.vision.dealer_detector import normalize_patch


ROOT = Path(__file__).resolve().parents[2]

TEMPLATE_PATH = (
    ROOT
    / "assets/templates/dealer_button_calibrated.png"
)

SCALES = (
    2.9,
    3.0,
    3.1,
    3.2,
    3.3,
)

GEOMETRY_PATH = (
    ROOT
    / "config/v017/geometry_maximized.json"
)


def detect_native_dealer(image):
    if image is None or image.size == 0:
        raise ValueError("native dealer frame is empty")

    if image.shape[:2] != (2168, 3456):
        raise ValueError(
            "native dealer detector requires 3456x2168"
        )

    template = cv2.imread(str(TEMPLATE_PATH))

    if template is None:
        raise FileNotFoundError(TEMPLATE_PATH)

    frame_gray = normalize_patch(image)

    candidates = []

    for scale in SCALES:
        scaled = cv2.resize(
            template,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

        response = cv2.matchTemplate(
            frame_gray,
            normalize_patch(scaled),
            cv2.TM_CCOEFF_NORMED,
        )

        _, confidence, _, location = (
            cv2.minMaxLoc(response)
        )

        x, y = location
        h, w = scaled.shape[:2]

        candidates.append({
            "scale": scale,
            "confidence": float(confidence),
            "match_x": int(x),
            "match_y": int(y),
            "center_x": float(x + w / 2.0),
            "center_y": float(y + h / 2.0),
        })

    best = max(
        candidates,
        key=lambda row: row["confidence"],
    )

    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    owners = []

    for seat, zones in geometry[
        "dealer_button_zones"
    ].items():
        if not isinstance(zones, list):
            zones = [zones]

        for zone_index, rect in enumerate(zones):
            if (
                rect["x"]
                <= best["center_x"]
                <= rect["x"] + rect["width"]
                and
                rect["y"]
                <= best["center_y"]
                <= rect["y"] + rect["height"]
            ):
                owners.append(
                    (seat, zone_index)
                )

    best["owners"] = owners
    best["dealer_button_seat"] = (
        owners[0][0]
        if len(owners) == 1
        else None
    )

    return best
