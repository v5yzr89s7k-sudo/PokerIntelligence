from pathlib import Path

import cv2

from src.api.paced_replay_capture import PacedReplayCapture
from src.events.local_event_detector import LocalEventDetector


ROOT = Path(__file__).resolve().parents[2]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260722_152155"
)


EXPECTED = [
    (43, ("seat_lower_right",), ()),
    (49, ("hero",), ()),
    (52, (), ("seat_lower_right", "hero")),
    (54, ("seat_mid_left",), ()),
    (91, ("seat_lower_left",), ()),
    (102, (), ("seat_lower_left",)),
    (116, ("seat_mid_right",), ()),
    (128, ("seat_lower_left",), ()),
    (136, (), ("seat_lower_left",)),
    (142, ("seat_lower_left",), ()),
    (
        149,
        (),
        (
            "seat_mid_left",
            "seat_mid_right",
            "seat_lower_left",
        ),
    ),
]


def main():
    assert SESSION.exists(), SESSION

    replay = PacedReplayCapture(SESSION)
    detector = LocalEventDetector()

    detector.bet_region_tracker.clock = (
        lambda: replay.current_recorded_elapsed
    )

    observed = []

    # Process as fast as possible. Semantic time comes exclusively from
    # the recorded frame timestamps, proving detector behavior is
    # independent of replay processing speed.
    for record in replay.records:
        replay.current_recorded_elapsed = (
            float(record["ts"])
            - replay.first_recorded_ts
        )

        image = cv2.imread(
            str(record["frame_path"])
        )

        assert image is not None, record["frame_path"]

        image = cv2.resize(
            image,
            (934, 696),
        )

        changes = detector.detect(image)

        appeared = tuple(
            changes.bet_region_appeared
            or []
        )

        cleared = tuple(
            changes.bet_region_cleared
            or []
        )

        if appeared or cleared:
            observed.append(
                (
                    int(record["index"]),
                    appeared,
                    cleared,
                )
            )

    print("===== EXPECTED =====")
    for item in EXPECTED:
        print(item)

    print()
    print("===== OBSERVED =====")
    for item in observed:
        print(item)

    # Appeared/cleared seats within one detector frame are
    # simultaneous membership observations. Their tuple order
    # is not poker chronology and must not affect this contract.
    def normalize(rows):
        return [
            (
                frame,
                tuple(sorted(appeared)),
                tuple(sorted(cleared)),
            )
            for frame, appeared, cleared in rows
        ]

    assert normalize(observed) == normalize(EXPECTED), (
        "recorded replay clock did not preserve "
        "bet-region temporal semantics"
        f"\nexpected={normalize(EXPECTED)}"
        f"\nobserved={normalize(observed)}"
    )

    print()
    print(
        "PASS: deterministic replay preserves all "
        "11 recorded bet-region transitions"
    )


if __name__ == "__main__":
    main()
