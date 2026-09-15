from unittest.mock import patch

from src.api import api_event_coordinator as coordinator
from src.events.local_event_detector import ChangeSet


def changes(*, disappeared=None):
    value = ChangeSet()
    value.opponent_hole_cards_disappeared_seats = list(
        disappeared or []
    )
    return value


def main():
    # ------------------------------------------------------------------
    # RED 1:
    # A disappearance detected across the hand-acquisition boundary
    # must NOT become current-hand physical completion evidence.
    # ------------------------------------------------------------------
    state = {
        "phase": "PREFLOP",
        "hand_token": "frontier-hand",
        "terminal_action_frozen": False,
        "physical_card_action_ownership": {
            "hand_token": "frontier-hand",
            "armed": True,
            "visible_seats": [],
        },
    }

    emitted = []

    with patch.object(
        coordinator,
        "emit",
        side_effect=lambda event: emitted.append(event),
    ):
        coordinator.emit_physical_actor_completions(
            changes(disappeared=["seat_top"]),
            state,
            street="PREFLOP",
        )

    assert emitted == [], (
        "RED: disappearance without same-hand visible ownership "
        "crossed the acquisition frontier"
    )

    # ------------------------------------------------------------------
    # RED 2:
    # Once the seat has been positively visible during this hand,
    # its later disappearance IS owned physical completion evidence.
    # ------------------------------------------------------------------
    state["physical_card_action_ownership"]["visible_seats"] = [
        "seat_top",
    ]

    emitted = []

    with patch.object(
        coordinator,
        "emit",
        side_effect=lambda event: emitted.append(event),
    ):
        coordinator.emit_physical_actor_completions(
            changes(disappeared=["seat_top"]),
            state,
            street="PREFLOP",
        )

    assert len(emitted) == 1, (
        "RED: same-hand visible->absent transition was suppressed"
    )

    assert emitted[0]["type"] == "physical_actor_completed"
    assert emitted[0]["seat"] == "seat_top"
    assert emitted[0]["hand_token"] == "frontier-hand"

    # ------------------------------------------------------------------
    # RED 3:
    # Visibility ownership from another hand token is stale.
    # ------------------------------------------------------------------
    state["physical_card_action_ownership"] = {
        "hand_token": "old-hand",
        "armed": True,
        "visible_seats": ["seat_top"],
    }

    emitted = []

    with patch.object(
        coordinator,
        "emit",
        side_effect=lambda event: emitted.append(event),
    ):
        coordinator.emit_physical_actor_completions(
            changes(disappeared=["seat_top"]),
            state,
            street="PREFLOP",
        )

    assert emitted == [], (
        "RED: stale previous-hand card ownership authorized completion"
    )

    print(
        "PASS physical card acquisition frontier: "
        "only same-hand owned visible->absent transitions transport"
    )


if __name__ == "__main__":
    main()
