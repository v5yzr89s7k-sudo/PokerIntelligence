"""
v0.16 current-frame physical-card ownership wiring contract.

Required ordering:

    current frame
        -> sample visible opponent cards
        -> update same-hand ownership
        -> transport disappearance evidence

The participant prebuffer is deliberately absent from this contract.
Chronology ownership begins with the current hand-owned frame only.
"""

from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as coordinator
from src.events.local_event_detector import ChangeSet


def main():
    frame = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    changes = ChangeSet()

    # Simulate a process-level transition that crossed acquisition:
    # seat_top disappeared relative to LocalEventDetector.previous_frame.
    changes.opponent_hole_cards_disappeared_seats = [
        "seat_top",
    ]

    state = {
        "phase": "PREFLOP",
        "hand_token": "hand-owned-frame",
        "terminal_action_frozen": False,
        "physical_card_action_ownership": None,
    }

    emitted = []

    # Current owned frame says:
    #
    # seat_top       ABSENT
    # seat_mid_right VISIBLE
    # seat_lower_right VISIBLE
    #
    # Therefore seat_top's process-level disappearance must NOT transport.
    with (
        patch.object(
            coordinator,
            "dealt_in_seats",
            return_value=[
                "seat_mid_right",
                "seat_lower_right",
            ],
            create=True,
        ),
        patch.object(
            coordinator,
            "emit",
            side_effect=lambda event: emitted.append(event),
        ),
    ):
        coordinator.process_current_frame_physical_card_ownership(
            state,
            frame,
            changes,
            street="PREFLOP",
        )

    ownership = state[
        "physical_card_action_ownership"
    ]

    assert ownership == {
        "hand_token": "hand-owned-frame",
        "visible_seats": [
            "seat_mid_right",
            "seat_lower_right",
        ],
    }, ownership

    physical_completions = [
        event
        for event in emitted
        if event.get("type") == "physical_actor_completed"
    ]

    assert physical_completions == [], (
        "cross-acquisition disappearance transported before "
        "current-frame ownership was established"
    )

    acquisition_events = [
        event
        for event in emitted
        if event.get("type") == "observer_acquisition"
    ]

    assert len(acquisition_events) == 1, acquisition_events

    # --------------------------------------------------------------
    # A later owned frame sees seat_mid_right disappear.
    #
    # Because it was positively visible on the first owned frame,
    # transport is now authorized.
    # --------------------------------------------------------------
    later_changes = ChangeSet()

    later_changes.opponent_hole_cards_disappeared_seats = [
        "seat_mid_right",
    ]

    emitted = []

    with (
        patch.object(
            coordinator,
            "dealt_in_seats",
            return_value=[
                "seat_lower_right",
            ],
            create=True,
        ),
        patch.object(
            coordinator,
            "emit",
            side_effect=lambda event: emitted.append(event),
        ),
    ):
        coordinator.process_current_frame_physical_card_ownership(
            state,
            frame,
            later_changes,
            street="PREFLOP",
        )

    assert len(emitted) == 1, emitted

    event = emitted[0]

    assert event["type"] == "physical_actor_completed"
    assert event["seat"] == "seat_mid_right"
    assert event["hand_token"] == "hand-owned-frame"

    # Monotonic ownership retains the fact that seat_mid_right had been
    # positively observed earlier in this same hand.
    assert state[
        "physical_card_action_ownership"
    ]["visible_seats"] == [
        "seat_mid_right",
        "seat_lower_right",
    ]

    print(
        "PASS current-frame physical-card ownership wiring: "
        "ownership precedes disappearance transport"
    )


if __name__ == "__main__":
    main()
