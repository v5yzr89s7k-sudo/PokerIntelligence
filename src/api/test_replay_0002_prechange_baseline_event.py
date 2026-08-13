from pathlib import Path
import json

import cv2

import src.api.api_event_coordinator as coordinator
from src.events.local_event_detector import LocalEventDetector


ROOT = Path(__file__).resolve().parents[2]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260808_114630"
)

SEAT = "seat_mid_right"


def load_frame(index):
    path = SESSION / f"{index:04d}_full.png"

    assert path.exists(), path

    image = cv2.imread(str(path))
    assert image is not None

    return cv2.resize(
        image,
        (934, 696),
    )


def main():
    before = load_frame(12)
    after = load_frame(13)

    detector = LocalEventDetector()
    detector.previous_frame = before.copy()

    preserved_previous = (
        detector.previous_frame.copy()
    )

    changes = detector.detect(after)

    assert SEAT in changes.stack_changed_seats, (
        changes.stack_change_details
    )

    emitted = []

    old_emit = coordinator.emit
    old_canonical = coordinator._canonical_stack_values

    coordinator.emit = lambda event: emitted.append(
        dict(event)
    )

    # Production condition under test:
    # the starting baseline has not yet been canonicalized.
    coordinator._canonical_stack_values = lambda: {
        SEAT: None,
    }

    try:
        state = {
            "phase": "PREFLOP",
        }

        coordinator.enrich_stack_change_measurements(
            changes,
            after,
            state,
            prechange_image=preserved_previous,
            prior_occupied_bet_regions=[],
            prior_commitment_seats=[],
            event_street="PREFLOP",
        )

    finally:
        coordinator.emit = old_emit
        coordinator._canonical_stack_values = (
            old_canonical
        )

    baseline_events = [
        event
        for event in emitted
        if event.get("type")
        == "stack_baseline_observation"
        and event.get("seat") == SEAT
    ]

    print()
    print("===== BASELINE EVENTS =====")

    for event in baseline_events:
        print(event)

    assert len(baseline_events) == 1, emitted

    event = baseline_events[0]

    assert event["observed_stack_bb"] == 55.41
    assert event["votes"] == 5
    assert event["confidence"] >= 0.95
    assert (
        event["mode"]
        == "independent_segmentation"
    )

    # This event must contain perception evidence only.
    assert "delta_bb" not in event
    assert "action" not in event
    assert "raise_to_bb" not in event

    print()
    print(
        "PASS Replay 0002 pre-change baseline event: "
        "real frame 12->13 stack motion automatically emits "
        "trusted 55.41 absolute pre-change evidence without "
        "action semantics or inferred delta"
    )


if __name__ == "__main__":
    main()
