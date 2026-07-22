from datetime import datetime
from pathlib import Path
import json
import re
import sys

import cv2

from src.api.canonical_frame import (
    to_canonical_frame,
)
from src.events.detectors.card_presence import (
    SEAT_ORDER,
    hand_participant_presence,
)


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = ROOT / "config/geometry.json"
CAPTURE_DIR = ROOT / "runtime/window_captures"

DEFAULT_TARGET = (
    CAPTURE_DIR
    / "acr_table_20260720_094425_076787.png"
)

OUT_JSON = (
    ROOT
    / "runtime/debug"
    / "temporal_hand_participant_validation.json"
)

FILENAME_RE = re.compile(
    r"acr_table_(\d{8})_(\d{6})_(\d{6})\.png$"
)


def capture_time(path):
    match = FILENAME_RE.match(
        path.name
    )

    if not match:
        return None

    date_text, time_text, micro_text = (
        match.groups()
    )

    return datetime.strptime(
        date_text + time_text + micro_text,
        "%Y%m%d%H%M%S%f",
    )


def main():
    target = (
        Path(sys.argv[1]).expanduser().resolve()
        if len(sys.argv) > 1
        else DEFAULT_TARGET
    )

    if not target.exists():
        raise SystemExit(
            f"target not found: {target}"
        )

    target_time = capture_time(
        target
    )

    if target_time is None:
        raise SystemExit(
            f"cannot parse timestamp: {target.name}"
        )

    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    candidates = []

    for path in CAPTURE_DIR.iterdir():
        if (
            not path.is_file()
            or not path.name.startswith(
                "acr_table_"
            )
            or path.suffix.lower() != ".png"
        ):
            continue

        timestamp = capture_time(
            path
        )

        if timestamp is None:
            continue

        delta = (
            timestamp - target_time
        ).total_seconds()

        if -12.0 <= delta <= 2.0:
            candidates.append(
                (
                    timestamp,
                    delta,
                    path,
                )
            )

    candidates.sort(
        key=lambda item: item[0]
    )

    if not candidates:
        raise SystemExit(
            "no frames in temporal window"
        )

    first_seen = {
        seat: None
        for seat in SEAT_ORDER
    }

    last_seen = {
        seat: None
        for seat in SEAT_ORDER
    }

    visible_frames = {
        seat: 0
        for seat in SEAT_ORDER
    }

    consecutive = {
        seat: 0
        for seat in SEAT_ORDER
    }

    maximum_consecutive = {
        seat: 0
        for seat in SEAT_ORDER
    }

    frame_records = []

    for timestamp, delta, path in candidates:
        image = cv2.imread(
            str(path)
        )

        if (
            image is None
            or image.size == 0
        ):
            continue

        canonical = to_canonical_frame(
            image,
            geometry,
        )

        results = (
            hand_participant_presence(
                canonical,
                geometry,
                hero_is_dealt=True,
            )
        )

        visible = []

        for seat in SEAT_ORDER:
            detected = bool(
                results[seat][
                    "dealt_in"
                ]
            )

            if detected:
                visible.append(
                    seat
                )

                visible_frames[seat] += 1
                consecutive[seat] += 1

                maximum_consecutive[seat] = max(
                    maximum_consecutive[seat],
                    consecutive[seat],
                )

                if first_seen[seat] is None:
                    first_seen[seat] = {
                        "frame": str(path),
                        "delta_seconds": round(
                            delta,
                            6,
                        ),
                    }

                last_seen[seat] = {
                    "frame": str(path),
                    "delta_seconds": round(
                        delta,
                        6,
                    ),
                }

            else:
                consecutive[seat] = 0

        frame_records.append({
            "frame": str(path),
            "delta_seconds": round(
                delta,
                6,
            ),
            "visible_seats": visible,
            "visible_count": len(
                visible
            ),
            "results": results,
        })

    # Require detection on at least two consecutive frames. This rejects a
    # one-frame visual artifact while retaining players who fold quickly.
    frozen_candidates = [
        seat
        for seat in SEAT_ORDER
        if maximum_consecutive[seat] >= 2
    ]

    payload = {
        "target": str(target),
        "frame_count": len(
            frame_records
        ),
        "window_seconds": {
            "before": 12.0,
            "after": 2.0,
        },
        "frozen_candidates": (
            frozen_candidates
        ),
        "frozen_count": len(
            frozen_candidates
        ),
        "visible_frames": visible_frames,
        "maximum_consecutive": (
            maximum_consecutive
        ),
        "first_seen": first_seen,
        "last_seen": last_seen,
        "frames": frame_records,
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

    print("target:", target)
    print(
        "frames analyzed:",
        len(frame_records),
    )
    print()

    for seat in SEAT_ORDER:
        print(
            f"{seat:20s} "
            f"frames={visible_frames[seat]:2d} "
            f"max_consecutive="
            f"{maximum_consecutive[seat]:2d}"
        )

    print()
    print(
        "frozen_count:",
        len(frozen_candidates),
    )
    print(
        "frozen_candidates:",
        frozen_candidates,
    )
    print("json:", OUT_JSON)


if __name__ == "__main__":
    main()
