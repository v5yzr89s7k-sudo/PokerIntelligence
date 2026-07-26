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
TEMPLATE_PATH = ROOT / "assets/templates/dealer_button_calibrated.png"
OUT_DIR = ROOT / "runtime/dealer_location_verification"

SAMPLE_EVERY = 50
MIN_CONFIDENCE = 0.78
MAX_CANDIDATES_PER_FRAME = 3
NMS_RADIUS = 28
CLUSTER_RADIUS = 24
MIN_CLUSTER_HITS = 5
REPRESENTATIVES_PER_CLUSTER = 6


def anchor_center(zone):
    return (
        float(zone["x"]) + float(zone["width"]) / 2.0,
        float(zone["y"]) + float(zone["height"]) / 2.0,
    )


def nearest_seat(x, y, zones):
    best_seat = None
    best_distance = None

    for seat, zone in zones.items():
        zx, zy = anchor_center(zone)
        distance = hypot(x - zx, y - zy)

        if best_distance is None or distance < best_distance:
            best_seat = seat
            best_distance = distance

    return best_seat, best_distance


def extract_candidates(response, template_width, template_height):
    working = response.copy()
    output = []

    for _ in range(MAX_CANDIDATES_PER_FRAME):
        _, confidence, _, location = cv2.minMaxLoc(working)
        confidence = float(confidence)

        if confidence < MIN_CONFIDENCE:
            break

        x = int(location[0])
        y = int(location[1])

        output.append({
            "x": x,
            "y": y,
            "center_x": x + template_width / 2.0,
            "center_y": y + template_height / 2.0,
            "confidence": confidence,
        })

        x0 = max(0, x - NMS_RADIUS)
        y0 = max(0, y - NMS_RADIUS)
        x1 = min(
            working.shape[1],
            x + template_width + NMS_RADIUS,
        )
        y1 = min(
            working.shape[0],
            y + template_height + NMS_RADIUS,
        )

        working[y0:y1, x0:x1] = -1.0

    return output


def cluster_items(items):
    clusters = []

    for item in sorted(
        items,
        key=lambda value: value["confidence"],
        reverse=True,
    ):
        selected = None
        selected_distance = None

        for cluster in clusters:
            distance = hypot(
                item["center_x"] - cluster["center_x"],
                item["center_y"] - cluster["center_y"],
            )

            if (
                distance <= CLUSTER_RADIUS
                and (
                    selected_distance is None
                    or distance < selected_distance
                )
            ):
                selected = cluster
                selected_distance = distance

        if selected is None:
            clusters.append({
                "items": [item],
                "center_x": item["center_x"],
                "center_y": item["center_y"],
            })
            continue

        selected["items"].append(item)

        count = len(selected["items"])
        selected["center_x"] = (
            sum(v["center_x"] for v in selected["items"])
            / count
        )
        selected["center_y"] = (
            sum(v["center_y"] for v in selected["items"])
            / count
        )

    summaries = []

    for cluster in clusters:
        items = cluster["items"]

        if len(items) < MIN_CLUSTER_HITS:
            continue

        items = sorted(
            items,
            key=lambda value: value["confidence"],
            reverse=True,
        )

        summaries.append({
            "center_x": round(cluster["center_x"], 1),
            "center_y": round(cluster["center_y"], 1),
            "hits": len(items),
            "average_confidence": round(
                sum(v["confidence"] for v in items) / len(items),
                4,
            ),
            "maximum_confidence": round(
                max(v["confidence"] for v in items),
                4,
            ),
            "items": items,
        })

    summaries.sort(
        key=lambda value: (
            value["hits"],
            value["average_confidence"],
        ),
        reverse=True,
    )

    return summaries


def main():
    geometry = json.loads(GEOMETRY_PATH.read_text())
    zones = geometry["dealer_button_zones"]

    template_image = cv2.imread(str(TEMPLATE_PATH))
    if template_image is None:
        raise SystemExit(f"Missing template: {TEMPLATE_PATH}")

    template = normalize_patch(template_image)
    template_height, template_width = template.shape[:2]

    captures = sorted(CAPTURE_DIR.glob("*.png"))
    sampled = captures[::SAMPLE_EVERY]

    if not sampled:
        raise SystemExit(f"No captures found in {CAPTURE_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates_by_seat = {
        seat: []
        for seat in zones
    }

    print(f"Total captures: {len(captures)}")
    print(f"Sampled captures: {len(sampled)}")
    print()

    for index, frame_path in enumerate(sampled, start=1):
        image = cv2.imread(str(frame_path))
        if image is None:
            continue

        canonical = to_canonical_frame(image, geometry)
        gray = normalize_patch(canonical)

        response = cv2.matchTemplate(
            gray,
            template,
            cv2.TM_CCOEFF_NORMED,
        )

        for candidate in extract_candidates(
            response,
            template_width,
            template_height,
        ):
            seat, distance = nearest_seat(
                candidate["center_x"],
                candidate["center_y"],
                zones,
            )

            candidate.update({
                "seat": seat,
                "anchor_distance": round(float(distance), 2),
                "frame": frame_path.name,
                "frame_path": str(frame_path),
            })

            candidates_by_seat[seat].append(candidate)

        if index % 50 == 0:
            print(
                f"Processed {index}/{len(sampled)}",
                flush=True,
            )

    report = {
        "settings": {
            "sample_every": SAMPLE_EVERY,
            "minimum_confidence": MIN_CONFIDENCE,
            "cluster_radius": CLUSTER_RADIUS,
            "minimum_cluster_hits": MIN_CLUSTER_HITS,
        },
        "seats": {},
    }

    print()
    print("==================== VERIFIED CANDIDATE CLUSTERS ====================")

    for seat, candidates in candidates_by_seat.items():
        seat_dir = OUT_DIR / seat
        seat_dir.mkdir(parents=True, exist_ok=True)

        clusters = cluster_items(candidates)

        report["seats"][seat] = {
            "candidate_count": len(candidates),
            "cluster_count": len(clusters),
            "clusters": [],
        }

        print()
        print(
            f"{seat}: candidates={len(candidates)} "
            f"clusters={len(clusters)}"
        )

        for cluster_index, cluster in enumerate(clusters, start=1):
            cluster_dir = seat_dir / f"cluster_{cluster_index:02d}"
            cluster_dir.mkdir(parents=True, exist_ok=True)

            report_cluster = {
                "center_x": cluster["center_x"],
                "center_y": cluster["center_y"],
                "hits": cluster["hits"],
                "average_confidence": cluster["average_confidence"],
                "maximum_confidence": cluster["maximum_confidence"],
                "representative_files": [],
            }

            for rep_index, item in enumerate(
                cluster["items"][:REPRESENTATIVES_PER_CLUSTER],
                start=1,
            ):
                frame = cv2.imread(item["frame_path"])
                if frame is None:
                    continue

                canonical = to_canonical_frame(frame, geometry)

                padding = 20
                x0 = max(0, int(item["x"]) - padding)
                y0 = max(0, int(item["y"]) - padding)
                x1 = min(
                    canonical.shape[1],
                    int(item["x"]) + template_width + padding,
                )
                y1 = min(
                    canonical.shape[0],
                    int(item["y"]) + template_height + padding,
                )

                crop = canonical[y0:y1, x0:x1]

                filename = (
                    f"rep_{rep_index:02d}_"
                    f"{item['confidence']:.4f}_"
                    f"{item['frame']}"
                )

                output_path = cluster_dir / filename
                cv2.imwrite(str(output_path), crop)

                report_cluster["representative_files"].append(
                    str(output_path)
                )

            report["seats"][seat]["clusters"].append(
                report_cluster
            )

            print(
                f"  cluster {cluster_index}: "
                f"center=({cluster['center_x']}, "
                f"{cluster['center_y']}) "
                f"hits={cluster['hits']} "
                f"avg={cluster['average_confidence']:.4f} "
                f"max={cluster['maximum_confidence']:.4f}"
            )

    report_path = OUT_DIR / "verification_report.json"
    report_path.write_text(
        json.dumps(report, indent=2) + "\n"
    )

    print()
    print("Done.")
    print("Report:", report_path)
    print("Representative crops:", OUT_DIR)


if __name__ == "__main__":
    main()
