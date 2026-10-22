from pathlib import Path
import json

import cv2

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
from src.vision.stack_reader import (
    read_stack_native_fast,
)


ROOT = Path(__file__).resolve().parents[2]

CAPTURES = sorted(
    (
        ROOT
        / "runtime/window_captures"
    ).glob(
        "acr_table_20260917_1515*.png"
    )
)

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)


class ControlledClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)


def make_observer(clock):
    observer = FrameHandObserver(
        players=[
            {
                "seat": "seat_upper_right",
                "position": "UTG",
                "name": "seat_upper_right",
                "stack_bb": 92.75,
                "dealt_in": True,
            },
        ],
        action_order=[
            "seat_upper_right",
        ],
        small_blind_seat="seat_upper_right",
        big_blind_seat="seat_upper_right",
        geometry=GEOMETRY,
        trusted_stacks={
            "seat_upper_right": 92.75,
        },
        opponent_seats=[],
        quantitative_seats=[
            "seat_upper_right",
        ],
        hero_seat="hero",
        hand_id="sept17-utg-retry",
        stack_reader=read_stack_native_fast,
    )

    observer.bet_region_tracker.clock = clock

    return observer


def run_once():
    assert len(CAPTURES) > 18

    clock = ControlledClock()
    observer = make_observer(clock)

    timeline = []

    # Establish pre-action physical state through frame 11,
    # then follow the exact OCR gap and recovery.
    for frame_id in range(0, 19):
        if frame_id > 0:
            clock.advance(0.25)

        image = cv2.imread(
            str(CAPTURES[frame_id])
        )

        assert image is not None

        result = observer.process_frame(
            image,
            frame_id=frame_id,
        )

        events = [
            event
            for event in result.events
            if (
                event.get("type")
                == "STACK_QUANTITATIVE_OBSERVATION"
                and event.get("seat")
                == "seat_upper_right"
            )
        ]

        for event in events:
            timeline.append(
                (
                    frame_id,
                    bool(event.get("resolved")),
                    event.get("resolved_value"),
                    event.get("mode"),
                )
            )

        retry = (
            observer
            .quantitative_retry_pending
            .get("seat_upper_right")
        )

        print(
            f"frame={frame_id:02d}",
            f"bet="
            f"{'seat_upper_right' in observer.confirmed_bet_regions}",
            f"events={events}",
            f"retry={retry}",
        )

    print()
    print(
        "timeline =",
        timeline,
    )

    # Improved native OCR resolves the original physical wake
    # at frame 12. A later independent frame must confirm the
    # same quantitative value.
    resolved = [
        row
        for row in timeline
        if row[1]
        and row[2] is not None
        and abs(float(row[2]) - 86.75) < 0.01
    ]

    assert resolved, "UTG STACK TRANSITION LOST"

    assert resolved[0][0] == 12, (
        "EXPECTED EARLY NATIVE OCR RESOLUTION",
        resolved,
    )

    assert any(
        row[0] == 13
        and row[1]
        and abs(float(row[2]) - 86.75) < 0.01
        for row in resolved
    ), "INDEPENDENT FRAME CONFIRMATION MISSING"

    assert all(
        row[2] is not None
        and abs(float(row[2]) - 86.75) < 0.01
        for row in resolved
    ), "CONTRADICTORY QUANTITATIVE VALUE"

    assert (
        "seat_upper_right"
        not in observer.quantitative_retry_pending
    ), observer.quantitative_retry_pending

    print()
    print(
        "SEPT17 UTG RETRY OWNERSHIP: PASS"
    )

    return tuple(timeline)


def main():
    first = run_once()

    print()
    print(
        "===== INTERNAL RUN 2 ====="
    )

    second = run_once()

    assert first == second

    print()
    print(
        "SEPT17 UTG RETRY DETERMINISM: PASS"
    )


if __name__ == "__main__":
    main()
