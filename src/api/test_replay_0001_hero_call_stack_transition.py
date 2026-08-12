import cv2
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.api.api_event_coordinator as coordinator


ROOT = Path(__file__).resolve().parents[2]
SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260812_104222"
)


def load_frame(index):
    path = SESSION / f"{index:04d}_full.png"

    if not path.exists():
        raise AssertionError(
            f"Replay 0001 frame missing: {path}"
        )

    image = cv2.imread(str(path))
    assert image is not None

    return cv2.resize(
        image,
        (934, 696),
    )


def trigger_changes():
    return SimpleNamespace(
        stack_changed_seats=["hero"],
        stack_change_details={
            "hero": {
                "mean_diff": 10.0,
            },
        },
        bet_region_appeared=[],
    )


def quiet_changes():
    return SimpleNamespace(
        stack_changed_seats=[],
        stack_change_details={},
        bet_region_appeared=[],
    )


def main():
    emitted = []

    state = {
        "phase": "PREFLOP",
        "pending_stack_reads": {},
    }

    canonical_values = {
        "hero": 57.34,
    }

    # Frame 0066 is the first stable trusted 50.84 reading.
    trigger_frame = load_frame(66)
    settled_frame = load_frame(67)

    with (
        patch.object(
            coordinator,
            "_canonical_stack_values",
            return_value=canonical_values,
        ),
        patch.object(
            coordinator,
            "emit",
            side_effect=lambda event: emitted.append(event),
        ),
    ):
        coordinator.enrich_stack_change_measurements(
            trigger_changes(),
            trigger_frame,
            state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats={
                "hero",
                "seat_mid_left",
            },
        )

        assert "hero" in state["pending_stack_reads"], (
            state["pending_stack_reads"]
        )

        state["pending_stack_reads"][
            "hero"
        ]["last_change_ts"] = time.time() - 0.60

        coordinator.enrich_stack_change_measurements(
            quiet_changes(),
            settled_frame,
            state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats={
                "hero",
                "seat_mid_left",
            },
        )

    stack_events = [
        event
        for event in emitted
        if event.get("type") == "stack_update"
        and event.get("seat") == "hero"
    ]

    assert len(stack_events) == 1, emitted

    event = stack_events[0]

    assert event["previous_stack_bb"] == 57.34, event
    assert event["current_stack_bb"] == 50.84, event
    assert event["delta_bb"] == 6.5, event
    assert event["origin_street"] == "PREFLOP", event

    assert (
        "hero"
        not in state["pending_stack_reads"]
    ), state["pending_stack_reads"]

    print(
        "PASS Replay 0001 Hero response stack transition: "
        "57.34 -> 50.84 -> delta 6.5"
    )


if __name__ == "__main__":
    main()
