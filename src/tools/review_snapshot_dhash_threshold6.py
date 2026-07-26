from pathlib import Path
import csv
import shutil
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.snapshot_cache import (
    _hash_distance,
    image_hash,
)
from src.api.table_snapshot_reader_core_v2 import (
    GEOMETRY,
    _prepare,
)


CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT_DIR = ROOT / "runtime/dhash_threshold6_review"

SAMPLE_EVERY = 10
MAX_FRAMES = 200

OLD_THRESHOLD = 5
NEW_THRESHOLD = 6


def full_seat_crop(card):
    seat = card["seat"]
    region = GEOMETRY["seat_regions"][seat]
    bounds = card["bounds"]

    x1 = int(region["x"]) - bounds["x1"]
    y1 = int(region["y"]) - bounds["y1"]
    x2 = x1 + int(region["width"])
    y2 = y1 + int(region["height"])

    crop = card["image"][y1:y2, x1:x2]

    if crop.size == 0:
        raise ValueError(
            f"empty crop for {seat}: "
            f"x1={x1}, y1={y1}, x2={x2}, y2={y2}"
        )

    return crop


def add_label(image, text):
    label_height = 24

    canvas = np.zeros(
        (
            image.shape[0] + label_height,
            image.shape[1],
            3,
        ),
        dtype=np.uint8,
    )

    canvas[label_height:] = image

    cv2.putText(
        canvas,
        text,
        (4, 17),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    return canvas


def make_pair(previous_crop, current_crop, previous_name, current_name, distance):
    height = max(
        previous_crop.shape[0],
        current_crop.shape[0],
    )

    width = max(
        previous_crop.shape[1],
        current_crop.shape[1],
    )

    previous = cv2.resize(
        previous_crop,
        (width, height),
        interpolation=cv2.INTER_NEAREST,
    )

    current = cv2.resize(
        current_crop,
        (width, height),
        interpolation=cv2.INTER_NEAREST,
    )

    previous = add_label(
        previous,
        f"PREVIOUS: {previous_name}",
    )

    current = add_label(
        current,
        f"CURRENT: {current_name}  d={distance}",
    )

    divider = np.zeros(
        (
            previous.shape[0],
            8,
            3,
        ),
        dtype=np.uint8,
    )

    return np.hstack([
        previous,
        divider,
        current,
    ])


def main():
    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    )

    if not captures:
        raise SystemExit("No captures")

    captures = captures[::SAMPLE_EVERY][-MAX_FRAMES:]

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    previous_by_seat = {}
    rows = []

    for frame in captures:
        _, cards = _prepare(frame)

        for card in cards:
            seat = card["seat"]
            crop = full_seat_crop(card)
            current_hash = image_hash(crop)

            previous = previous_by_seat.get(seat)

            if previous is not None:
                distance = _hash_distance(
                    previous["hash"],
                    current_hash,
                )

                if (
                    OLD_THRESHOLD < distance <= NEW_THRESHOLD
                ):
                    index = len(rows) + 1

                    seat_dir = OUT_DIR / seat
                    seat_dir.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    filename = (
                        f"{index:03d}_"
                        f"{previous['frame'].stem}_TO_"
                        f"{frame.stem}_d{distance}.png"
                    )

                    pair = make_pair(
                        previous["crop"],
                        crop,
                        previous["frame"].name,
                        frame.name,
                        distance,
                    )

                    output_path = seat_dir / filename

                    cv2.imwrite(
                        str(output_path),
                        pair,
                    )

                    rows.append({
                        "index": index,
                        "seat": seat,
                        "distance": distance,
                        "previous_frame": previous["frame"].name,
                        "current_frame": frame.name,
                        "image": str(
                            output_path.relative_to(ROOT)
                        ),
                    })

            # Match the sequential benchmark:
            # update the reference only when threshold 6 misses.
            if (
                previous is None
                or _hash_distance(
                    previous["hash"],
                    current_hash,
                ) > NEW_THRESHOLD
            ):
                previous_by_seat[seat] = {
                    "hash": current_hash,
                    "crop": crop.copy(),
                    "frame": frame,
                }

    manifest = OUT_DIR / "manifest.csv"

    with manifest.open(
        "w",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "index",
                "seat",
                "distance",
                "previous_frame",
                "current_frame",
                "image",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"Frames: {len(captures)}")
    print(
        "Threshold-6-only accepted pairs: "
        f"{len(rows)}"
    )
    print()
    print("Counts by seat:")

    counts = {}

    for row in rows:
        counts[row["seat"]] = (
            counts.get(row["seat"], 0) + 1
        )

    for seat in sorted(counts):
        print(
            f"{seat:18} "
            f"{counts[seat]}"
        )

    print()
    print(f"Review directory: {OUT_DIR}")
    print(f"Manifest: {manifest}")
    print()
    print(
        "Each image shows the previous cached seat crop "
        "on the left and the newly accepted crop on the right."
    )


if __name__ == "__main__":
    main()
