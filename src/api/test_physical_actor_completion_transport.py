from unittest.mock import patch

from src.api import api_event_coordinator as coordinator
from src.events.local_event_detector import ChangeSet


def main():
    changes = ChangeSet()

    changes.opponent_hole_cards_disappeared_seats = [
        "seat_lower_right",
    ]

    state = {
        "phase": "FLOP",
        "hand_token": "physical-actor-test",
        "terminal_action_frozen": False,
    }

    emitted = []

    with patch.object(
        coordinator,
        "emit",
        side_effect=lambda event: emitted.append(event),
    ):
        coordinator.emit_physical_actor_completions(
            changes,
            state,
            street="FLOP",
        )

    assert len(emitted) == 1

    event = emitted[0]

    assert (
        event["type"]
        == "physical_actor_completed"
    )

    assert (
        event["seat"]
        == "seat_lower_right"
    )

    assert event["street"] == "FLOP"

    # Coordinator must remain semantically neutral.
    assert "action" not in event

    print(
        "PASS physical actor transport: "
        "card disappearance emits neutral chronology evidence, "
        "not a direct fold"
    )


if __name__ == "__main__":
    main()
