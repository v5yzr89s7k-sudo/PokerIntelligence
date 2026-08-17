from pathlib import Path
from statistics import mean, median
from time import perf_counter, time
import json

import cv2

from src.capture.sck_frame_source import SCKFrameSource
from src.events.local_event_detector import LocalEventDetector


OUT = Path("runtime/debug/sck_change_gate_live")
OUT.mkdir(parents=True, exist_ok=True)

LOG = OUT / "change_gate.jsonl"

# Fresh diagnostic run.
LOG.write_text("")

for old in OUT.glob("change_*.png"):
    old.unlink()


def semantic_reasons(changes):
    reasons = []

    scalar = (
        "hero_changed",
        "board_changed",
        "pot_changed",
        "dealer_changed",
        "action_buttons_changed",
        "hero_cards_appeared",
        "hero_cards_cleared",
    )

    for name in scalar:
        if bool(getattr(changes, name, False)):
            reasons.append(name)

    sequences = (
        "stack_changed_seats",
        "bet_region_appeared",
        "bet_region_cleared",
        "opponent_hole_card_changed_seats",
    )

    for name in sequences:
        value = getattr(
            changes,
            name,
            None,
        )

        if value:
            reasons.append(
                f"{name}="
                + ",".join(
                    str(x)
                    for x in value
                )
            )

    return reasons


def main():
    source = SCKFrameSource()
    detector = LocalEventDetector()

    sample_times = []
    detector_times = []

    semantic_count = 0
    quiet_count = 0

    # About 20 seconds at ~28-30 FPS.
    target_samples = 600

    started = perf_counter()

    print("=" * 72)
    print("SCK LIVE CHANGE-GATE PROBE")
    print("=" * 72)
    print(
        "Raw samples are NOT saved."
    )
    print(
        "Only semantic-change frames are persisted."
    )
    print()

    try:
        for index in range(
            1,
            target_samples + 1,
        ):
            read_started = perf_counter()

            frame = source.read()

            read_ms = (
                perf_counter()
                - read_started
            ) * 1000.0

            detect_started = perf_counter()

            changes = detector.detect(
                frame
            )

            detect_ms = (
                perf_counter()
                - detect_started
            ) * 1000.0

            sample_times.append(
                read_ms
            )

            detector_times.append(
                detect_ms
            )

            reasons = semantic_reasons(
                changes
            )

            if reasons:
                semantic_count += 1

                filename = (
                    f"change_{semantic_count:04d}_"
                    f"sample_{index:04d}.png"
                )

                path = OUT / filename

                cv2.imwrite(
                    str(path),
                    frame,
                )

                row = {
                    "sample": index,
                    "semantic_index": (
                        semantic_count
                    ),
                    "ts": time(),
                    "read_ms": round(
                        read_ms,
                        3,
                    ),
                    "detector_ms": round(
                        detect_ms,
                        3,
                    ),
                    "reasons": reasons,
                    "frame": str(path),
                }

                with LOG.open("a") as f:
                    f.write(
                        json.dumps(row)
                        + "\n"
                    )

                print(
                    f"CHANGE "
                    f"sample={index:04d} "
                    f"detector={detect_ms:6.2f}ms "
                    + " | ".join(reasons)
                )

            else:
                quiet_count += 1

    finally:
        source.close()

    elapsed = (
        perf_counter()
        - started
    )

    total = (
        semantic_count
        + quiet_count
    )

    print()
    print("=" * 72)
    print("RESULT")
    print("=" * 72)

    print(
        "raw samples       :",
        total,
    )
    print(
        "semantic frames   :",
        semantic_count,
    )
    print(
        "quiet discarded   :",
        quiet_count,
    )

    if total:
        print(
            "semantic %       :",
            f"{100*semantic_count/total:.1f}%"
        )
        print(
            "discard %        :",
            f"{100*quiet_count/total:.1f}%"
        )

    print(
        f"elapsed           : "
        f"{elapsed:.2f}s"
    )

    print(
        f"effective FPS     : "
        f"{total/elapsed:.2f}"
    )

    print()
    print(
        "FRAME RECEIVE"
    )
    print(
        f"  median : "
        f"{median(sample_times):.2f} ms"
    )
    print(
        f"  mean   : "
        f"{mean(sample_times):.2f} ms"
    )
    print(
        f"  max    : "
        f"{max(sample_times):.2f} ms"
    )

    print()
    print(
        "LOCAL DETECTOR"
    )
    print(
        f"  median : "
        f"{median(detector_times):.2f} ms"
    )
    print(
        f"  mean   : "
        f"{mean(detector_times):.2f} ms"
    )
    print(
        f"  max    : "
        f"{max(detector_times):.2f} ms"
    )

    print()
    print(
        "record:",
        LOG,
    )
    print(
        "saved semantic frames:",
        semantic_count,
    )


if __name__ == "__main__":
    main()
