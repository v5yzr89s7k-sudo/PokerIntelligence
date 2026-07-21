from pathlib import Path
import json
import sys

import cv2

from src.api.canonical_frame import to_canonical_frame
from src.events.detectors.card_presence import (
    SEAT_ORDER,
    dealt_in_seats,
    seat_card_presence,
)


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = ROOT / "config/geometry.json"

DEFAULT_FRAME = (
    ROOT
    / "runtime/window_captures"
    / "acr_table_20260720_094425_076787.png"
)

OUT_JSON = (
    ROOT
    / "runtime/debug"
    / "hand_participant_detection.json"
)

OUT_OVERLAY = (
    ROOT
    / "runtime/debug"
    / "hand_participant_detection_overlay.png"
)


def draw_region(image, rect, label, detected):
    x = int(rect["x"])
    y = int(rect["y"])
    width = int(rect["width"])
    height = int(rect["height"])

    # Green means detected, red means absent.
    color = (
        (0, 255, 0)
        if detected
        else (0, 0, 255)
    )

    cv2.rectangle(
        image,
        (x, y),
        (x + width, y + height),
        color,
        2,
    )

    cv2.putText(
        image,
        label,
        (x, max(14, y - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        color,
        1,
        cv2.LINE_AA,
    )


def main():
    frame_path = (
        Path(sys.argv[1]).expanduser().resolve()
        if len(sys.argv) > 1
        else DEFAULT_FRAME
    )

    if not frame_path.exists():
        raise SystemExit(
            f"frame not found: {frame_path}"
        )

    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    image = cv2.imread(
        str(frame_path)
    )

    if image is None or image.size == 0:
        raise SystemExit(
            f"could not read frame: {frame_path}"
        )

    canonical = to_canonical_frame(
        image,
        geometry,
    )

    results = seat_card_presence(
        canonical,
        geometry,
    )

    participants = dealt_in_seats(
        canonical,
        geometry,
    )

    payload = {
        "frame": str(frame_path),
        "dealt_in_seats": participants,
        "dealt_in_count": len(participants),
        "results": results,
    }

    OUT_JSON.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUT_JSON.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n"
    )

    overlay = canonical.copy()
    hole_cards = geometry.get(
        "hole_cards",
        {},
    )

    for seat in SEAT_ORDER:
        result = results[seat]

        for card_name, rect in (
            hole_cards.get(seat) or {}
        ).items():
            score = result[
                "card_scores"
            ].get(
                card_name,
                0.0,
            )

            draw_region(
                overlay,
                rect,
                (
                    f"{seat}:{card_name} "
                    f"{score:.3f}"
                ),
                score > result["threshold"],
            )

    cv2.imwrite(
        str(OUT_OVERLAY),
        overlay,
    )

    print("frame:", frame_path)
    print(
        "dealt_in_count:",
        len(participants),
    )
    print(
        "dealt_in_seats:",
        participants,
    )

    print()

    for seat in SEAT_ORDER:
        result = results[seat]

        print(
            f"{seat:20s} "
            f"dealt_in={str(result['dealt_in']):5s} "
            f"visible={result['visible_card_count']} "
            f"scores={result['card_scores']}"
        )

    print()
    print("json:", OUT_JSON)
    print("overlay:", OUT_OVERLAY)


if __name__ == "__main__":
    main()
