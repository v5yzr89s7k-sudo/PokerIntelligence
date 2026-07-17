from pathlib import Path
import json
import shutil

import cv2

from src.api.seat_crop_builder import (
    build_seat_cards,
    build_seat_card_montage,
)


ROOT = Path(__file__).resolve().parents[2]
CAPTURE_DIR = ROOT / "runtime/validation/snapshot_v2/captures"
RESULTS_DIR = ROOT / "runtime/validation/snapshot_v2/results"


def safe_name(path: Path) -> str:
    return path.stem


def serialize_card(card: dict, filename: str) -> dict:
    return {
        "seat": card["seat"],
        "occupied": bool(card["occupied"]),
        "confidence": float(card["occupancy_confidence"]),
        "bounds": card["bounds"],
        "filename": filename,
    }


def validate_capture(capture_path: Path) -> dict:
    frame = cv2.imread(str(capture_path))

    if frame is None or frame.size == 0:
        raise RuntimeError(f"could not read capture: {capture_path}")

    output_dir = RESULTS_DIR / safe_name(capture_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    cards = build_seat_cards(
        frame,
        occupied_only=False,
    )

    metadata_cards = []

    for card in cards:
        filename = f"{card['seat']}.png"
        output_path = output_dir / filename

        if not cv2.imwrite(
            str(output_path),
            card["image"],
        ):
            raise RuntimeError(
                f"failed to write seat crop: {output_path}"
            )

        metadata_cards.append(
            serialize_card(card, filename)
        )

    montage = build_seat_card_montage(cards)
    montage_path = output_dir / "montage.png"

    if not cv2.imwrite(str(montage_path), montage):
        raise RuntimeError(
            f"failed to write montage: {montage_path}"
        )

    metadata = {
        "capture": str(capture_path.relative_to(ROOT)),
        "frame_width": int(frame.shape[1]),
        "frame_height": int(frame.shape[0]),
        "cards": metadata_cards,
    }

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n"
    )

    return metadata


def main():
    captures = sorted(CAPTURE_DIR.glob("*.png"))

    if not captures:
        raise SystemExit(
            f"no PNG captures found in {CAPTURE_DIR}"
        )

    if RESULTS_DIR.exists():
        shutil.rmtree(RESULTS_DIR)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []

    for index, capture_path in enumerate(captures, start=1):
        metadata = validate_capture(capture_path)
        all_results.append(metadata)

        print(
            f"[{index}/{len(captures)}] "
            f"{capture_path.name}"
        )

        for card in metadata["cards"]:
            print(
                f"  {card['seat']:<18} "
                f"occupied={str(card['occupied']):<5} "
                f"confidence={card['confidence']:.3f}"
            )

    summary_path = RESULTS_DIR / "results.json"
    summary_path.write_text(
        json.dumps(all_results, indent=2) + "\n"
    )

    print()
    print(f"Validated captures: {len(captures)}")
    print(f"Results directory: {RESULTS_DIR}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
