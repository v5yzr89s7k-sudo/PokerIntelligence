from datetime import datetime
from pathlib import Path
import json
import re
import sys

import cv2

from src.api.canonical_frame import to_canonical_frame
from src.events.detectors.card_presence import (
    SEAT_ORDER,
    seat_card_presence,
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
    / "hand_participant_temporal_diagnostic.json"
)

OUT_MONTAGE = (
    ROOT
    / "runtime/debug"
    / "hand_participant_temporal_montage.png"
)

FILENAME_RE = re.compile(
    r"acr_table_(\d{8})_(\d{6})_(\d{6})\.png$"
)


def capture_time(path):
    match = FILENAME_RE.match(path.name)

    if not match:
        return None

    date_text, time_text, micro_text = match.groups()

    return datetime.strptime(
        date_text + time_text + micro_text,
        "%Y%m%d%H%M%S%f",
    )


def load_frame(path, geometry):
    image = cv2.imread(str(path))

    if image is None or image.size == 0:
        return None

    return to_canonical_frame(
        image,
        geometry,
    )


def annotate(frame, path, results):
    image = frame.copy()

    y = 22

    cv2.putText(
        image,
        path.name,
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    y += 22

    for seat in SEAT_ORDER:
        result = results[seat]
        scores = result["card_scores"]

        text = (
            f"{seat}: "
            f"{scores.get('card_1', 0.0):.3f}, "
            f"{scores.get('card_2', 0.0):.3f}"
        )

        cv2.putText(
            image,
            text,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        y += 18

    return image


def main():
    target = (
        Path(sys.argv[1]).expanduser().resolve()
        if len(sys.argv) > 1
        else DEFAULT_TARGET
    )

    if not target.exists():
        raise SystemExit(
            f"target frame not found: {target}"
        )

    target_time = capture_time(target)

    if target_time is None:
        raise SystemExit(
            f"could not parse target timestamp: {target.name}"
        )

    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    candidates = []

    for path in sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    ):
        timestamp = capture_time(path)

        if timestamp is None:
            continue

        delta_seconds = (
            timestamp - target_time
        ).total_seconds()

        # Look eight seconds before the API-associated frame and two seconds
        # after it. The useful dealt-card state should be in the earlier part.
        if -8.0 <= delta_seconds <= 2.0:
            candidates.append(
                (
                    path,
                    timestamp,
                    delta_seconds,
                )
            )

    if not candidates:
        raise SystemExit(
            "no capture frames found in temporal window"
        )

    frame_results = []
    maxima = {
        seat: {
            "card_1": 0.0,
            "card_2": 0.0,
        }
        for seat in SEAT_ORDER
    }

    maximum_frame = {
        seat: {
            "card_1": "",
            "card_2": "",
        }
        for seat in SEAT_ORDER
    }

    panels = []

    # Avoid generating an enormous montage if capture cadence is high.
    montage_stride = max(
        1,
        len(candidates) // 12,
    )

    for index, (
        path,
        timestamp,
        delta_seconds,
    ) in enumerate(candidates):
        frame = load_frame(
            path,
            geometry,
        )

        if frame is None:
            continue

        results = seat_card_presence(
            frame,
            geometry,
        )

        frame_results.append({
            "frame": str(path),
            "time": timestamp.isoformat(),
            "delta_seconds": round(
                delta_seconds,
                6,
            ),
            "results": results,
        })

        for seat in SEAT_ORDER:
            for card_name in (
                "card_1",
                "card_2",
            ):
                score = float(
                    results[seat][
                        "card_scores"
                    ].get(
                        card_name,
                        0.0,
                    )
                )

                if score > maxima[seat][card_name]:
                    maxima[seat][card_name] = score
                    maximum_frame[seat][
                        card_name
                    ] = str(path)

        if (
            index % montage_stride == 0
            or index == len(candidates) - 1
        ):
            panels.append(
                annotate(
                    frame,
                    path,
                    results,
                )
            )

    # Diagnostic classification only. This is deliberately not wired into
    # production. It reports whether both card regions ever exceeded the
    # existing threshold during the temporal window.
    temporal_candidates = []

    for seat in SEAT_ORDER:
        if (
            maxima[seat]["card_1"] > 0.08
            and maxima[seat]["card_2"] > 0.08
        ):
            temporal_candidates.append(
                seat
            )

    payload = {
        "target_frame": str(target),
        "window_seconds": {
            "before": 8.0,
            "after": 2.0,
        },
        "frame_count": len(frame_results),
        "temporal_candidates_existing_threshold": (
            temporal_candidates
        ),
        "maxima": maxima,
        "maximum_frame": maximum_frame,
        "frames": frame_results,
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

    if panels:
        width = max(
            panel.shape[1]
            for panel in panels
        )

        normalized = []

        for panel in panels:
            if panel.shape[1] < width:
                pad = cv2.copyMakeBorder(
                    panel,
                    0,
                    0,
                    0,
                    width - panel.shape[1],
                    cv2.BORDER_CONSTANT,
                    value=(0, 0, 0),
                )

                panel = pad

            normalized.append(panel)

        montage = cv2.vconcat(
            normalized
        )

        cv2.imwrite(
            str(OUT_MONTAGE),
            montage,
        )

    print("target:", target)
    print(
        "frames analyzed:",
        len(frame_results),
    )
    print()

    for seat in SEAT_ORDER:
        print(
            f"{seat:20s} "
            f"max1={maxima[seat]['card_1']:.6f} "
            f"max2={maxima[seat]['card_2']:.6f}"
        )

    print()
    print(
        "temporal candidates:",
        temporal_candidates,
    )
    print("json:", OUT_JSON)
    print("montage:", OUT_MONTAGE)


if __name__ == "__main__":
    main()
