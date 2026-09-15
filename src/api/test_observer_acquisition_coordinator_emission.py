"""
v0.16 coordinator observer-acquisition emission contract.

The coordinator must emit exactly one neutral observer_acquisition event
for each hand, using physical card visibility from the first owned frame.

It must not emit poker-order conclusions such as pre_acquisition_seats.
Those belong exclusively to BettingRoundTracker downstream.
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

    state = {
        "phase": "PREFLOP",
        "hand_token": "hand-a",
        "terminal_action_frozen": False,
        "physical_card_action_ownership": None,
    }

    changes = ChangeSet()
    changes.opponent_hole_cards_disappeared_seats = []

    emitted = []

    # --------------------------------------------------------------
    # First owned frame:
    # emit exactly one observer_acquisition using current visibility.
    # --------------------------------------------------------------
    with (
        patch.object(
            coordinator,
            "dealt_in_seats",
            return_value=[
                "co",
                "btn",
                "sb",
            ],
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
            hero_owned=True,
        )

    acquisition = [
        event
        for event in emitted
        if event.get("type") == "observer_acquisition"
    ]

    assert len(acquisition) == 1, acquisition

    event = acquisition[0]

    assert event["hand_token"] == "hand-a"
    assert event["street"] == "PREFLOP"
    assert event["visible_seats"] == [
        "co",
        "btn",
        "sb",
    ]
    assert event["hero_owned"] is True

    assert "pre_acquisition_seats" not in event
    assert "first_owned_seat" not in event
    assert "owned_queue" not in event

    # --------------------------------------------------------------
    # Subsequent frame in the SAME hand:
    # no second observer_acquisition event.
    # --------------------------------------------------------------
    emitted.clear()

    with (
        patch.object(
            coordinator,
            "dealt_in_seats",
            return_value=[
                "btn",
                "sb",
            ],
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
            hero_owned=True,
        )

    acquisition = [
        event
        for event in emitted
        if event.get("type") == "observer_acquisition"
    ]

    assert acquisition == [], (
        "observer acquisition emitted more than once in one hand"
    )

    # --------------------------------------------------------------
    # New hand token:
    # first owned frame must emit a new acquisition event.
    # --------------------------------------------------------------
    state["hand_token"] = "hand-b"

    emitted.clear()

    with (
        patch.object(
            coordinator,
            "dealt_in_seats",
            return_value=[
                "hj",
                "co",
                "btn",
                "sb",
            ],
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
            hero_owned=True,
        )

    acquisition = [
        event
        for event in emitted
        if event.get("type") == "observer_acquisition"
    ]

    assert len(acquisition) == 1
    assert acquisition[0]["hand_token"] == "hand-b"

    print(
        "PASS coordinator observer acquisition emission: "
        "one neutral event per hand from first owned frame"
    )


if __name__ == "__main__":
    main()
