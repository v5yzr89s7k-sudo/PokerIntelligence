from pathlib import Path
import sys
import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.table_snapshot_reader_core_v2 import (
    _prepare,
    _cache_fingerprint_image,
)

CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT = ROOT / "runtime/fingerprint_debug"

SAMPLE_EVERY = 25
MAX_FRAMES = 40


def main():

    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    )

    captures = captures[::SAMPLE_EVERY][-MAX_FRAMES:]

    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Frames: {len(captures)}")

    for frame_index, frame in enumerate(captures):

        _, cards = _prepare(frame)

        for card in cards:

            seat = card["seat"]

            image = _cache_fingerprint_image(card)

            seat_dir = OUT / seat
            seat_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            filename = (
                f"{frame_index:03d}_"
                f"{frame.stem}.png"
            )

            cv2.imwrite(
                str(seat_dir / filename),
                image,
            )

    print()
    print("Saved to:")
    print(OUT)


if __name__ == "__main__":
    main()
