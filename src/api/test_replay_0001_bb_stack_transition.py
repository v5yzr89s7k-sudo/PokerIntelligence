import cv2
import json
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


def changes_with_bb_bet():
    return SimpleNamespace(
        stack_changed_seats=[],
        stack_change_details={},
        bet_region_appeared=[
            "seat_mid_left",
        ],
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

    # Frame 0051 is already showing the post-3-bet 56.6 BB stack.
    trigger_frame = load_frame(51)

    # A later stable frame still shows 56.6 BB.
    settled_frame = load_frame(52)

    canonical_values = {
        "seat_mid_left": 65.6,
    }

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
            changes_with_bb_bet(),
            trigger_frame,
            state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
        )

        assert "seat_mid_left" in state["pending_stack_reads"], (
            state["pending_stack_reads"]
        )

        # Force only the settlement clock forward. This preserves the exact
        # production settlement logic without sleeping in a deterministic test.
        state["pending_stack_reads"][
            "seat_mid_left"
        ]["last_change_ts"] = time.time() - 0.60

        changes = quiet_changes()

        coordinator.enrich_stack_change_measurements(
            changes,
            settled_frame,
            state,
            prior_occupied_bet_regions={
                "seat_mid_left",
            },
            prior_commitment_seats=set(),
        )

    stack_events = [
        event
        for event in emitted
        if event.get("type") == "stack_update"
        and event.get("seat") == "seat_mid_left"
    ]

    assert len(stack_events) == 1, emitted

    event = stack_events[0]

    assert event["previous_stack_bb"] == 65.6, event
    assert event["current_stack_bb"] == 56.6, event
    assert event["delta_bb"] == 9.0, event
    assert event["origin_street"] == "PREFLOP", event
    assert event["stack_read_mode"] == "psm13_verification", event

    assert (
        "seat_mid_left"
        not in state["pending_stack_reads"]
    ), state["pending_stack_reads"]

    print(
        "PASS Replay 0001 BB stack transition: "
        "bet-region trigger -> 65.6 -> 56.6 -> delta 9.0"
    )


if __name__ == "__main__":
    main()
