from collections import defaultdict
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
OUT_DIR = ROOT / "runtime/dhash6_similarity"

SAMPLE_EVERY = 10
MAX_FRAMES = 200
TARGET_DISTANCE = 6


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


def grayscale_pair(first, second):
    width = max(
        first.shape[1],
        second.shape[1],
    )
    height = max(
        first.shape[0],
        second.shape[0],
    )

    first_resized = cv2.resize(
        first,
        (width, height),
        interpolation=cv2.INTER_AREA,
    )
    second_resized = cv2.resize(
        second,
        (width, height),
        interpolation=cv2.INTER_AREA,
    )

    first_gray = cv2.cvtColor(
        first_resized,
        cv2.COLOR_BGR2GRAY,
    )
    second_gray = cv2.cvtColor(
        second_resized,
        cv2.COLOR_BGR2GRAY,
    )

    return (
        first_resized,
        second_resized,
        first_gray,
        second_gray,
    )


def structural_similarity(first, second):
    """
    OpenCV/Numpy SSIM implementation.

    Returns a value normally between -1 and 1, where higher means more
    structurally similar.
    """
    first = first.astype(np.float64)
    second = second.astype(np.float64)

    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    mu_first = cv2.GaussianBlur(
        first,
        (11, 11),
        1.5,
    )
    mu_second = cv2.GaussianBlur(
        second,
        (11, 11),
        1.5,
    )

    mu_first_sq = mu_first * mu_first
    mu_second_sq = mu_second * mu_second
    mu_product = mu_first * mu_second

    sigma_first_sq = (
        cv2.GaussianBlur(
            first * first,
            (11, 11),
            1.5,
        )
        - mu_first_sq
    )

    sigma_second_sq = (
        cv2.GaussianBlur(
            second * second,
            (11, 11),
            1.5,
        )
        - mu_second_sq
    )

    sigma_product = (
        cv2.GaussianBlur(
            first * second,
            (11, 11),
            1.5,
        )
        - mu_product
    )

    numerator = (
        (2 * mu_product + c1)
        * (2 * sigma_product + c2)
    )

    denominator = (
        (mu_first_sq + mu_second_sq + c1)
        * (sigma_first_sq + sigma_second_sq + c2)
    )

    score_map = numerator / np.maximum(
        denominator,
        1e-12,
    )

    return float(score_map.mean())


def histogram_correlation(first, second):
    first_hist = cv2.calcHist(
        [first],
        [0],
        None,
        [64],
        [0, 256],
    )
    second_hist = cv2.calcHist(
        [second],
        [0],
        None,
        [64],
        [0, 256],
    )

    cv2.normalize(
        first_hist,
        first_hist,
    )
    cv2.normalize(
        second_hist,
        second_hist,
    )

    return float(
        cv2.compareHist(
            first_hist,
            second_hist,
            cv2.HISTCMP_CORREL,
        )
    )


def edge_agreement(first, second):
    first_edges = cv2.Canny(
        first,
        50,
        150,
    )
    second_edges = cv2.Canny(
        second,
        50,
        150,
    )

    first_mask = first_edges > 0
    second_mask = second_edges > 0

    union = np.logical_or(
        first_mask,
        second_mask,
    ).sum()

    if union == 0:
        return 1.0

    intersection = np.logical_and(
        first_mask,
        second_mask,
    ).sum()

    return float(intersection / union)


def calculate_metrics(first, second):
    (
        first_color,
        second_color,
        first_gray,
        second_gray,
    ) = grayscale_pair(
        first,
        second,
    )

    difference = cv2.absdiff(
        first_gray,
        second_gray,
    )

    mad = float(difference.mean())
    normalized_mad = mad / 255.0

    return {
        "first_color": first_color,
        "second_color": second_color,
        "ssim": structural_similarity(
            first_gray,
            second_gray,
        ),
        "mad": mad,
        "normalized_mad": normalized_mad,
        "histogram_correlation": histogram_correlation(
            first_gray,
            second_gray,
        ),
        "edge_agreement": edge_agreement(
            first_gray,
            second_gray,
        ),
    }


def add_label(image, text):
    label_height = 28

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
        (4, 19),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    return canvas


def write_pair_image(
    output_path,
    first,
    second,
    metrics,
):
    first_label = add_label(
        first,
        "PREVIOUS",
    )

    second_label = add_label(
        second,
        (
            f"CURRENT d=6 "
            f"SSIM={metrics['ssim']:.3f} "
            f"MAD={metrics['mad']:.1f}"
        ),
    )

    divider = np.zeros(
        (
            first_label.shape[0],
            8,
            3,
        ),
        dtype=np.uint8,
    )

    combined = np.hstack([
        first_label,
        divider,
        second_label,
    ])

    cv2.imwrite(
        str(output_path),
        combined,
    )


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
    counts = defaultdict(int)

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

                if distance == TARGET_DISTANCE:
                    metrics = calculate_metrics(
                        previous["crop"],
                        crop,
                    )

                    counts[seat] += 1
                    index = len(rows) + 1

                    seat_dir = OUT_DIR / seat
                    seat_dir.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    filename = (
                        f"{index:03d}_"
                        f"{previous['frame'].stem}_TO_"
                        f"{frame.stem}_d6.png"
                    )

                    output_path = seat_dir / filename

                    write_pair_image(
                        output_path,
                        metrics["first_color"],
                        metrics["second_color"],
                        metrics,
                    )

                    rows.append({
                        "index": index,
                        "seat": seat,
                        "distance": distance,
                        "ssim": metrics["ssim"],
                        "mad": metrics["mad"],
                        "normalized_mad": metrics["normalized_mad"],
                        "histogram_correlation": metrics[
                            "histogram_correlation"
                        ],
                        "edge_agreement": metrics[
                            "edge_agreement"
                        ],
                        "previous_frame": previous["frame"].name,
                        "current_frame": frame.name,
                        "image": str(
                            output_path.relative_to(ROOT)
                        ),
                    })

            # Match threshold-6 production behavior:
            # retain the cached reference on distances <= 6,
            # and refresh only after a miss above 6.
            if (
                previous is None
                or _hash_distance(
                    previous["hash"],
                    current_hash,
                ) > TARGET_DISTANCE
            ):
                previous_by_seat[seat] = {
                    "hash": current_hash,
                    "crop": crop.copy(),
                    "frame": frame,
                }

    rows.sort(
        key=lambda row: (
            row["ssim"],
            row["histogram_correlation"],
            row["edge_agreement"],
            -row["mad"],
        )
    )

    manifest = OUT_DIR / "ranked_manifest.csv"

    with manifest.open(
        "w",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "rank",
                "index",
                "seat",
                "distance",
                "ssim",
                "mad",
                "normalized_mad",
                "histogram_correlation",
                "edge_agreement",
                "previous_frame",
                "current_frame",
                "image",
            ],
        )

        writer.writeheader()

        for rank, row in enumerate(
            rows,
            start=1,
        ):
            writer.writerow({
                "rank": rank,
                **row,
            })

    print(f"Frames: {len(captures)}")
    print(f"Distance-6 pairs: {len(rows)}")

    print()
    print("Counts by seat:")

    for seat in sorted(counts):
        print(
            f"{seat:18} "
            f"{counts[seat]}"
        )

    if rows:
        ssim_values = [
            row["ssim"]
            for row in rows
        ]
        mad_values = [
            row["mad"]
            for row in rows
        ]
        histogram_values = [
            row["histogram_correlation"]
            for row in rows
        ]
        edge_values = [
            row["edge_agreement"]
            for row in rows
        ]

        print()
        print("================ METRIC RANGES ================")
        print(
            f"SSIM: "
            f"min={min(ssim_values):.4f} "
            f"median={np.median(ssim_values):.4f} "
            f"max={max(ssim_values):.4f}"
        )
        print(
            f"MAD: "
            f"min={min(mad_values):.2f} "
            f"median={np.median(mad_values):.2f} "
            f"max={max(mad_values):.2f}"
        )
        print(
            f"Histogram correlation: "
            f"min={min(histogram_values):.4f} "
            f"median={np.median(histogram_values):.4f} "
            f"max={max(histogram_values):.4f}"
        )
        print(
            f"Edge agreement: "
            f"min={min(edge_values):.4f} "
            f"median={np.median(edge_values):.4f} "
            f"max={max(edge_values):.4f}"
        )

        print()
        print("================ LOWEST-SSIM PAIRS ================")

        for rank, row in enumerate(
            rows[:15],
            start=1,
        ):
            print(
                f"{rank:2}. "
                f"{row['seat']:18} "
                f"SSIM={row['ssim']:.4f} "
                f"MAD={row['mad']:.2f} "
                f"HIST={row['histogram_correlation']:.4f} "
                f"EDGE={row['edge_agreement']:.4f} "
                f"{row['image']}"
            )

    print()
    print(f"Output: {OUT_DIR}")
    print(f"Ranked manifest: {manifest}")


if __name__ == "__main__":
    main()
