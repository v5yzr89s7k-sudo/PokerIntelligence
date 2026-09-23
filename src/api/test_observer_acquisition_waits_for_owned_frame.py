"""
Regression from September 8 raw-frame replay.

A WAITING frame with no visible opponent cards is not sufficient to establish
observer chronology ownership.

Critically, such a frame must not consume the one-shot acquisition token.
A later chronology-ownable PREFLOP frame must still be allowed to emit the
single observer_acquisition event for this hand.
"""

from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as coordinator
from src.events.local_event_detector import ChangeSet


def acquisition_events(events):
    return [
        event
        for event in events
        if event.get("type") == "observer_acquisition"
    ]


def visibility_side_effect(visible_seats):
    visible = set(
        seat
        for seat in visible_seats
        if seat != "hero"
    )

    hole_cards = (
        coordinator.GEOM.get("hole_cards")
        or {}
    )

    region_owner = {
        id(regions): seat
        for seat, regions in hole_cards.items()
        if seat != "hero"
    }

    def classify(frame, regions):
        seat = region_owner.get(
            id(regions)
        )

        return seat in visible

    return classify


def main():
    frame = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    changes = ChangeSet()
    changes.opponent_hole_cards_disappeared_seats = []

    state = {
        "phase": "WAITING",
        "hand_token": "sep8-owned-frame",
        "terminal_action_frozen": False,
        "physical_card_action_ownership": None,
    }

    emitted = []

    # --------------------------------------------------------------
    # Frame A:
    # Hero visibility alone while still WAITING is not chronology
    # acquisition. It must emit nothing and must not consume ownership.
    # --------------------------------------------------------------
    with (
        patch.object(
            coordinator,
            "opponent_cards_visible",
            side_effect=visibility_side_effect([]),
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
            street="WAITING",
            hero_owned=True,
        )

    assert acquisition_events(emitted) == [], (
        "RED: WAITING/empty visibility prematurely emitted "
        "observer_acquisition"
    )

    assert not state.get(
        "observer_acquisition_emitted_hand_token"
    ), (
        "RED: non-ownable WAITING frame consumed the acquisition token"
    )

    # --------------------------------------------------------------
    # Frame A2:
    # Street has advanced to PREFLOP, but Hero alone is still not
    # sufficient to establish opponent chronology ownership.
    #
    # This is the exact September 8 replay regression:
    #
    #   street=PREFLOP
    #   visible_seats=[]
    #   hero_owned=True
    #
    # It must still defer and leave the one-shot token available.
    # --------------------------------------------------------------
    state["phase"] = "PREFLOP"
    emitted.clear()

    with (
        patch.object(
            coordinator,
            "opponent_cards_visible",
            side_effect=visibility_side_effect([]),
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

    assert acquisition_events(emitted) == [], (
        "RED: PREFLOP Hero-only visibility prematurely emitted "
        "observer_acquisition"
    )

    assert not state.get(
        "observer_acquisition_emitted_hand_token"
    ), (
        "RED: PREFLOP Hero-only frame consumed the acquisition token"
    )

    # --------------------------------------------------------------
    # Frame B:
    # Same hand, now PREFLOP with positively visible opponents.
    # This is the first chronology-ownable frame.
    # --------------------------------------------------------------
    state["phase"] = "PREFLOP"
    emitted.clear()

    with (
        patch.object(
            coordinator,
            "opponent_cards_visible",
            side_effect=visibility_side_effect([
                "seat_top",
                "seat_upper_right",
                "seat_lower_right",
            ]),
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

    acquisition = acquisition_events(emitted)

    assert len(acquisition) == 1, acquisition

    event = acquisition[0]

    assert event["street"] == "PREFLOP"
    assert event["visible_seats"] == [
        "seat_top",
        "seat_upper_right",
        "seat_lower_right",
    ]
    assert event["hero_owned"] is True

    assert (
        state.get(
            "observer_acquisition_emitted_hand_token"
        )
        == "sep8-owned-frame"
    )

    # --------------------------------------------------------------
    # Frame C:
    # Same hand again. Exactly-once remains intact.
    # --------------------------------------------------------------
    emitted.clear()

    with (
        patch.object(
            coordinator,
            "opponent_cards_visible",
            side_effect=visibility_side_effect([
                "seat_upper_right",
                "seat_lower_right",
            ]),
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

    assert acquisition_events(emitted) == []

    print(
        "PASS observer acquisition waits for chronology-owned frame: "
        "WAITING/empty does not consume token; PREFLOP visibility emits once"
    )


if __name__ == "__main__":
    main()
