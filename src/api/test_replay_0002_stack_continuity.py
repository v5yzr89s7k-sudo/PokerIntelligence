from pathlib import Path
from types import SimpleNamespace
import json

import cv2

import src.api.api_event_coordinator as coordinator


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/debug/action_sequence/20260808_114630/0013_full.png"
)

SEAT = "seat_mid_right"


class FakeRecent:
    def __init__(self):
        self.items = []

    def add(self, **kwargs):
        self.items.append(kwargs)


def main():
    assert FRAME.exists(), FRAME

    image = cv2.imread(str(FRAME))
    assert image is not None

    image = cv2.resize(
        image,
        (934, 696),
    )

    # Real raw OCR evidence first.
    region = coordinator.GEOM["stack_regions"][SEAT]
    crop = coordinator._crop_geometry_region(
        image,
        region,
    )

    raw = coordinator.read_stack(crop)

    raw_values = {
        float(item["stack_bb"])
        for item in raw.get("raw") or []
        if item.get("stack_bb") is not None
    }

    print("===== REAL FRAME 13 RAW OCR =====")
    print(raw)

    assert 93.41 in raw_values, raw_values
    assert 53.41 in raw_values, raw_values

    # The reader remains provisional. Continuity must perform the correction.
    assert raw["stack_bb"] == 93.41, raw

    # Cycle 1: detector observes stack motion. Production intentionally
    # opens/refreshes a pending candidate and does NOT OCR immediately.
    changes = SimpleNamespace(
        stack_changed_seats=[SEAT],
        stack_change_details={
            SEAT: {
                "mean_diff": 10.0,
            },
        },
        bet_region_appeared=[],
    )

    state = {
        "phase": "PREFLOP",
        "pending_stack_reads": {},
    }

    recent = FakeRecent()
    emitted = []

    old_canonical = coordinator._canonical_stack_values
    old_emit = coordinator.emit

    try:
        # Human-verified authoritative prior stack.
        coordinator._canonical_stack_values = lambda: {
            SEAT: 55.41,
        }

        coordinator.emit = lambda event: emitted.append(
            dict(event)
        )

        coordinator.enrich_stack_change_measurements(
            changes,
            image,
            state,
            prior_occupied_bet_regions=[],
            prior_commitment_seats=[],
            event_street="PREFLOP",
            recent_stack_observations=recent,
            frame_path=str(FRAME),
            frame_ts=13.0,
        )

        assert SEAT in state["pending_stack_reads"]
        assert changes.stack_changed_seats == []

        # Cycle 2: region is now quiet. Move the pending timestamp beyond
        # the real 0.45s settlement requirement, then run a frame with no
        # fresh movement trigger. This is the actual production lifecycle.
        state["pending_stack_reads"][SEAT][
            "last_change_ts"
        ] = 0.0

        quiet_changes = SimpleNamespace(
            stack_changed_seats=[],
            stack_change_details={},
            bet_region_appeared=[],
        )

        coordinator.enrich_stack_change_measurements(
            quiet_changes,
            image,
            state,
            prior_occupied_bet_regions=[],
            prior_commitment_seats=[],
            event_street="PREFLOP",
            recent_stack_observations=recent,
            frame_path=str(FRAME),
            frame_ts=13.5,
        )

        changes = quiet_changes

    finally:
        coordinator._canonical_stack_values = old_canonical
        coordinator.emit = old_emit

    print()
    print("===== SETTLED CHANGE =====")
    print("seats:", changes.stack_changed_seats)
    print(
        json.dumps(
            changes.stack_change_details,
            indent=2,
        )
    )

    print()
    print("===== EMITTED =====")
    for item in emitted:
        print(item)

    assert changes.stack_changed_seats == [
        SEAT
    ], changes.stack_changed_seats

    detail = changes.stack_change_details[SEAT]

    assert detail["previous_stack_bb"] == 55.41, detail
    assert detail["current_stack_bb"] == 53.41, detail
    assert detail["delta_bb"] == 2.0, detail
    assert detail["stack_read_mode"] == "continuity", detail

    stack_updates = [
        event
        for event in emitted
        if event.get("type") == "stack_update"
    ]

    assert len(stack_updates) == 1, stack_updates

    event = stack_updates[0]

    assert event["seat"] == SEAT
    assert event["previous_stack_bb"] == 55.41
    assert event["current_stack_bb"] == 53.41
    assert event["delta_bb"] == 2.0
    assert event["stack_read_mode"] == "continuity"

    assert recent.items, "trusted observation was not recorded"
    assert recent.items[-1]["stack_bb"] == 53.41

    print()
    print(
        "PASS Replay 0002 stack continuity: "
        "real frame 13 correlated 93.41 OCR is corrected by "
        "canonical continuity to 53.41, producing the real 2 BB transition"
    )


if __name__ == "__main__":
    main()
