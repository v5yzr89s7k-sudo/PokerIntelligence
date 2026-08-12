import cv2
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


def changes(
    *,
    appeared=None,
    stack_changed=None,
):
    return SimpleNamespace(
        board_count=3,
        bet_region_appeared=list(appeared or []),
        stack_changed_seats=list(stack_changed or []),
        stack_change_details={},
    )


def show_pending(label, state):
    entry = (
        state.get("pending_stack_reads") or {}
    ).get("seat_mid_left")

    print()
    print(label)

    if entry is None:
        print("    pending=None")
    else:
        print(
            "    street=",
            entry.get("origin_street"),
            "sources=",
            entry.get("trigger_sources"),
            "first=",
            entry.get("first_change_ts"),
            "last=",
            entry.get("last_change_ts"),
            "attempts=",
            entry.get("ocr_attempts"),
        )


def main():
    emitted = []

    state = {
        "phase": "PREFLOP",
        "pending_stack_reads": {},
    }

    canonical_values = {
        "seat_mid_left": 56.6,
    }

    event_street = (
        coordinator.event_street_for_frame(
            state,
            3,
        )
    )

    assert event_street == "FLOP"

    frame58 = load_frame(58)
    frame59 = load_frame(59)
    frame63 = load_frame(63)

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
        # ----------------------------------------------------
        # Frame 58:
        # physical flop is present and BB bet region appears.
        # Stack still reads 56.6.
        # ----------------------------------------------------
        with patch.object(
            coordinator.time,
            "time",
            return_value=10.0,
        ):
            coordinator.enrich_stack_change_measurements(
                changes(
                    appeared=["seat_mid_left"],
                ),
                frame58,
                state,
                prior_occupied_bet_regions=set(),
                prior_commitment_seats=set(),
                event_street=event_street,
            )

        show_pending(
            "===== AFTER FRAME 58 TRIGGER =====",
            state,
        )

        assert (
            state["pending_stack_reads"]
            ["seat_mid_left"]
            ["origin_street"]
            == "FLOP"
        )

        # ----------------------------------------------------
        # Frame 59:
        # ~620 ms later, enough for the current 450 ms settle
        # window. But BB stack still visually reads 56.6.
        #
        # This is the suspected premature-settlement point.
        # ----------------------------------------------------
        with patch.object(
            coordinator.time,
            "time",
            return_value=10.62,
        ):
            coordinator.enrich_stack_change_measurements(
                changes(),
                frame59,
                state,
                prior_occupied_bet_regions={
                    "seat_mid_left",
                },
                prior_commitment_seats=set(),
                event_street=event_street,
            )

        show_pending(
            "===== AFTER FRAME 59 EARLY SETTLE =====",
            state,
        )

        print(
            "    emitted=",
            emitted,
        )

        survived_early_settle = (
            "seat_mid_left"
            in state.get(
                "pending_stack_reads",
                {},
            )
        )

        # ----------------------------------------------------
        # Frame 63:
        # actual displayed stack is now 51.6.
        # Give the candidate enough elapsed time again.
        # ----------------------------------------------------
        with patch.object(
            coordinator.time,
            "time",
            return_value=12.68,
        ):
            coordinator.enrich_stack_change_measurements(
                changes(),
                frame63,
                state,
                prior_occupied_bet_regions={
                    "seat_mid_left",
                },
                prior_commitment_seats=set(),
                event_street=event_street,
            )

        show_pending(
            "===== AFTER FRAME 63 REAL STACK =====",
            state,
        )

    stack_events = [
        event
        for event in emitted
        if event.get("type") == "stack_update"
        and event.get("seat") == "seat_mid_left"
    ]

    print()
    print("===== RESULT =====")
    print(
        "survived_early_settle=",
        survived_early_settle,
    )
    print(
        "stack_events=",
        stack_events,
    )

    if stack_events:
        event = stack_events[-1]

        print()
        print(
            "RECOVERED:",
            event.get("previous_stack_bb"),
            "->",
            event.get("current_stack_bb"),
            "delta=",
            event.get("delta_bb"),
            "street=",
            event.get("origin_street"),
        )

    # This test is diagnostic for the current production behavior.
    #
    # The desired final behavior is:
    #   candidate survives the early zero-delta read
    #   and eventually emits 56.6 -> 51.6 on FLOP.
    if not survived_early_settle:
        print()
        print(
            "FAIL Replay 0001 timing diagnosis: "
            "BB flop candidate was discarded before "
            "the 51.6 stack became visible"
        )
        raise SystemExit(1)

    assert len(stack_events) == 1, stack_events

    event = stack_events[0]

    assert event["previous_stack_bb"] == 56.6, event
    assert event["current_stack_bb"] == 51.6, event
    assert event["delta_bb"] == 5.0, event
    assert event["origin_street"] == "FLOP", event

    print()
    print(
        "PASS Replay 0001 flop BB settlement timing: "
        "56.6 -> 51.6 -> 5 BB on FLOP"
    )


if __name__ == "__main__":
    main()
