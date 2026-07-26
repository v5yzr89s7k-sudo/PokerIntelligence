from pathlib import Path
import json
import sys
from math import hypot

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.canonical_frame import to_canonical_frame
from src.vision.dealer_detector import normalize_patch


GEOMETRY_PATH = ROOT / "config/geometry.json"
CAPTURE_DIR = ROOT / "runtime/window_captures"
TEMPLATE_PATH = (
    ROOT / "assets/templates/dealer_button_calibrated.png"
)
OUTPUT_DIR = ROOT / "runtime/dealer_analysis_fast"

SAMPLE_EVERY = 50
SEARCH_MARGIN = 120
MIN_CONFIDENCE = 0.70
CLUSTER_RADIUS = 28


def cluster_candidates(candidates):
    """
    Greedy spatial clustering of dealer-button match centers.
    """
    clusters = []

    for candidate in sorted(
        candidates,
        key=lambda item: item["confidence"],
        reverse=True,
    ):
        cx = candidate["center_x"]
        cy = candidate["center_y"]

        nearest = None
        nearest_distance = None

        for cluster in clusters:
            distance = hypot(
                cx - cluster["center_x"],
                cy - cluster["center_y"],
            )

            if (
                distance <= CLUSTER_RADIUS
                and (
                    nearest_distance is None
                    or distance < nearest_distance
                )
            ):
                nearest = cluster
                nearest_distance = distance

        if nearest is None:
            clusters.append({
                "items": [candidate],
                "center_x": float(cx),
                "center_y": float(cy),
            })
            continue

        nearest["items"].append(candidate)

        count = len(nearest["items"])
        nearest["center_x"] = (
            sum(item["center_x"] for item in nearest["items"])
            / count
        )
        nearest["center_y"] = (
            sum(item["center_y"] for item in nearest["items"])
            / count
        )

    output = []

    for cluster in clusters:
        items = cluster["items"]

        best = max(
            items,
            key=lambda item: item["confidence"],
        )

        output.append({
            "center_x": round(cluster["center_x"], 1),
            "center_y": round(cluster["center_y"], 1),
            "hits": len(items),
            "average_confidence": round(
                sum(item["confidence"] for item in items)
                / len(items),
                4,
            ),
            "maximum_confidence": round(
                max(item["confidence"] for item in items),
                4,
            ),
            "representative_frame": best["frame"],
            "representative_match": {
                "x": best["x"],
                "y": best["y"],
                "confidence": round(
                    best["confidence"],
                    4,
                ),
            },
        })

    output.sort(
        key=lambda item: (
            item["hits"],
            item["average_confidence"],
        ),
        reverse=True,
    )

    return output


def main():
    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    template_image = cv2.imread(str(TEMPLATE_PATH))

    if template_image is None:
        raise SystemExit(
            f"Could not read dealer template: {TEMPLATE_PATH}"
        )

    template = normalize_patch(template_image)
    template_height, template_width = template.shape[:2]

    all_captures = sorted(
        CAPTURE_DIR.glob("*.png")
    )

    sampled_captures = all_captures[::SAMPLE_EVERY]

    if not sampled_captures:
        raise SystemExit(
            f"No captures found in {CAPTURE_DIR}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidates_by_seat = {
        seat: []
        for seat in geometry["dealer_button_zones"]
    }

    print(
        f"Total captures: {len(all_captures)}",
        flush=True,
    )
    print(
        f"Sampled captures: {len(sampled_captures)} "
        f"(every {SAMPLE_EVERY}th frame)",
        flush=True,
    )
    print(
        f"Minimum confidence: {MIN_CONFIDENCE:.2f}",
        flush=True,
    )
    print()

    for index, frame_path in enumerate(
        sampled_captures,
        start=1,
    ):
        image = cv2.imread(str(frame_path))

        if image is None:
            continue

        image = to_canonical_frame(
            image,
            geometry,
        )

        image_height, image_width = image.shape[:2]

        for seat, zone in (
            geometry["dealer_button_zones"].items()
        ):
            zone_x = int(zone["x"])
            zone_y = int(zone["y"])
            zone_width = int(zone["width"])
            zone_height = int(zone["height"])

            x0 = max(
                0,
                zone_x - SEARCH_MARGIN,
            )
            y0 = max(
                0,
                zone_y - SEARCH_MARGIN,
            )
            x1 = min(
                image_width,
                zone_x + zone_width + SEARCH_MARGIN,
            )
            y1 = min(
                image_height,
                zone_y + zone_height + SEARCH_MARGIN,
            )

            crop = image[y0:y1, x0:x1]

            if (
                crop.shape[0] < template_height
                or crop.shape[1] < template_width
            ):
                continue

            crop_gray = normalize_patch(crop)

            response = cv2.matchTemplate(
                crop_gray,
                template,
                cv2.TM_CCOEFF_NORMED,
            )

            _, confidence, _, location = (
                cv2.minMaxLoc(response)
            )

            confidence = float(confidence)

            if confidence < MIN_CONFIDENCE:
                continue

            match_x = int(x0 + location[0])
            match_y = int(y0 + location[1])

            candidates_by_seat[seat].append({
                "frame": frame_path.name,
                "x": match_x,
                "y": match_y,
                "center_x": (
                    match_x + template_width / 2.0
                ),
                "center_y": (
                    match_y + template_height / 2.0
                ),
                "confidence": confidence,
            })

        if index % 50 == 0:
            print(
                f"Processed {index}/{len(sampled_captures)}",
                flush=True,
            )

    report = {
        "settings": {
            "total_capture_count": len(all_captures),
            "sampled_capture_count": len(sampled_captures),
            "sample_every": SAMPLE_EVERY,
            "search_margin": SEARCH_MARGIN,
            "minimum_confidence": MIN_CONFIDENCE,
            "cluster_radius": CLUSTER_RADIUS,
            "template_width": template_width,
            "template_height": template_height,
        },
        "seats": {},
    }

    print()
    print("==================== RESULTS ====================")

    for seat, candidates in candidates_by_seat.items():
        clusters = cluster_candidates(candidates)

        report["seats"][seat] = {
            "candidate_count": len(candidates),
            "cluster_count": len(clusters),
            "clusters": clusters,
        }

        print()
        print(
            f"{seat}: candidates={len(candidates)} "
            f"clusters={len(clusters)}"
        )

        for cluster_index, cluster in enumerate(
            clusters[:8],
            start=1,
        ):
            print(
                f"  cluster {cluster_index}: "
                f"center=({cluster['center_x']},"
                f"{cluster['center_y']}) "
                f"hits={cluster['hits']} "
                f"avg={cluster['average_confidence']:.4f} "
                f"max={cluster['maximum_confidence']:.4f}"
            )

        canvas = np.zeros(
            (
                geometry["table_size"]["height"],
                geometry["table_size"]["width"],
                3,
            ),
            dtype=np.uint8,
        )

        for candidate in candidates:
            cv2.circle(
                canvas,
                (
                    int(candidate["center_x"]),
                    int(candidate["center_y"]),
                ),
                2,
                (255, 255, 255),
                -1,
            )

        for cluster_index, cluster in enumerate(
            clusters,
            start=1,
        ):
            center = (
                int(round(cluster["center_x"])),
                int(round(cluster["center_y"])),
            )

            cv2.circle(
                canvas,
                center,
                CLUSTER_RADIUS,
                (0, 255, 255),
                2,
            )

            cv2.putText(
                canvas,
                (
                    f"{cluster_index}:"
                    f"{cluster['hits']}"
                ),
                (
                    center[0] + 5,
                    center[1] - 5,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

        cv2.imwrite(
            str(
                OUTPUT_DIR
                / f"{seat}_clusters.png"
            ),
            canvas,
        )

    report_path = (
        OUTPUT_DIR
        / "dealer_position_clusters.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n"
    )

    print()
    print("Analysis complete.")
    print("Report:", report_path)
    print("Images:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
