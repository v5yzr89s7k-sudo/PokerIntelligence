from pathlib import Path
import json
import sys
from math import hypot

import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.canonical_frame import to_canonical_frame
from src.vision.dealer_detector import normalize_patch


GEOMETRY_PATH = ROOT / "config/geometry.json"
CAPTURE_DIR = ROOT / "runtime/window_captures"
TEMPLATE_PATH = ROOT / "assets/templates/dealer_button_calibrated.png"
OUTPUT_DIR = ROOT / "runtime/dealer_locations_per_seat"

SAMPLE_EVERY = 50
SEARCH_MARGIN = 140
MIN_CONFIDENCE = 0.78
CLUSTER_RADIUS = 24
MIN_CLUSTER_HITS = 5
MAX_REPORTED_CLUSTERS = 4


def add_to_cluster(clusters, candidate):
    nearest = None
    nearest_distance = None

    for cluster in clusters:
        distance = hypot(
            candidate["center_x"] - cluster["center_x"],
            candidate["center_y"] - cluster["center_y"],
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
            "center_x": candidate["center_x"],
            "center_y": candidate["center_y"],
        })
        return

    nearest["items"].append(candidate)

    nearest["center_x"] = sum(
        item["center_x"] for item in nearest["items"]
    ) / len(nearest["items"])

    nearest["center_y"] = sum(
        item["center_y"] for item in nearest["items"]
    ) / len(nearest["items"])


def summarize_clusters(clusters):
    output = []

    for cluster in clusters:
        items = cluster["items"]

        if len(items) < MIN_CLUSTER_HITS:
            continue

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
            "representative_match_x": best["x"],
            "representative_match_y": best["y"],
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

    template_image = cv2.imread(
        str(TEMPLATE_PATH)
    )

    if template_image is None:
        raise SystemExit(
            f"Could not read template: {TEMPLATE_PATH}"
        )

    template = normalize_patch(template_image)
    template_height, template_width = template.shape[:2]

    captures = sorted(
        CAPTURE_DIR.glob("*.png")
    )

    sampled = captures[::SAMPLE_EVERY]

    if not sampled:
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

    print(f"Total captures: {len(captures)}")
    print(f"Sampled captures: {len(sampled)}")
    print(f"Sample every: {SAMPLE_EVERY}")
    print(f"Minimum confidence: {MIN_CONFIDENCE}")
    print()

    for index, frame_path in enumerate(
        sampled,
        start=1,
    ):
        image = cv2.imread(
            str(frame_path)
        )

        if image is None:
            continue

        canonical = to_canonical_frame(
            image,
            geometry,
        )

        image_height, image_width = canonical.shape[:2]

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

            crop = canonical[y0:y1, x0:x1]

            if (
                crop.shape[0] < template_height
                or crop.shape[1] < template_width
            ):
                continue

            gray = normalize_patch(crop)

            response = cv2.matchTemplate(
                gray,
                template,
                cv2.TM_CCOEFF_NORMED,
            )

            _, confidence, _, location = (
                cv2.minMaxLoc(response)
            )

            confidence = float(confidence)

            if confidence < MIN_CONFIDENCE:
                continue

            match_x = int(
                x0 + location[0]
            )
            match_y = int(
                y0 + location[1]
            )

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
                f"Processed {index}/{len(sampled)}",
                flush=True,
            )

    report = {
        "settings": {
            "total_captures": len(captures),
            "sampled_captures": len(sampled),
            "sample_every": SAMPLE_EVERY,
            "search_margin": SEARCH_MARGIN,
            "minimum_confidence": MIN_CONFIDENCE,
            "cluster_radius": CLUSTER_RADIUS,
            "minimum_cluster_hits": MIN_CLUSTER_HITS,
        },
        "seats": {},
    }

    print()
    print("==================== DEALER LOCATIONS ====================")

    for seat, candidates in candidates_by_seat.items():
        clusters = []

        for candidate in sorted(
            candidates,
            key=lambda item: item["confidence"],
            reverse=True,
        ):
            add_to_cluster(
                clusters,
                candidate,
            )

        summarized = summarize_clusters(
            clusters
        )

        report["seats"][seat] = {
            "candidate_count": len(candidates),
            "location_count": len(summarized),
            "locations": summarized,
        }

        print()
        print(
            f"{seat}: "
            f"candidates={len(candidates)} "
            f"locations={len(summarized)}"
        )

        for number, location in enumerate(
            summarized[:MAX_REPORTED_CLUSTERS],
            start=1,
        ):
            print(
                f"  location {number}: "
                f"center=({location['center_x']}, "
                f"{location['center_y']}) "
                f"hits={location['hits']} "
                f"avg={location['average_confidence']:.4f} "
                f"max={location['maximum_confidence']:.4f}"
            )

    report_path = (
        OUTPUT_DIR
        / "dealer_locations_by_seat.json"
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


if __name__ == "__main__":
    main()
