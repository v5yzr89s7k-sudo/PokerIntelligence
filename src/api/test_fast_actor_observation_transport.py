from types import SimpleNamespace

import src.api.api_event_coordinator as coordinator


def main():
    emitted = []

    original_emit = coordinator.emit

    try:
        coordinator.emit = emitted.append

        state = {
            "phase": "PREFLOP",
            "hand_token": "fast-actor-token",
            "terminal_action_frozen": False,
        }

        changes = SimpleNamespace(
            bet_region_appeared=["seat_upper_right"],
            stack_changed_seats=["seat_top"],
        )

        coordinator.emit_fast_actor_observations(
            state,
            changes,
            street="PREFLOP",
        )

        assert len(emitted) == 1

        event = emitted[0]

        assert event["type"] == "actor_observed"
        assert event["hand_token"] == "fast-actor-token"
        assert event["street"] == "PREFLOP"
        assert event["seat"] == "seat_upper_right"
        assert event["source"] == "bet_region_appeared"
        assert event["blocked_seats"] == ["seat_top"]

        # Waiting state must never publish hand chronology.
        emitted.clear()

        coordinator.emit_fast_actor_observations(
            {
                "phase": "WAITING",
                "hand_token": None,
                "terminal_action_frozen": False,
            },
            changes,
            street="WAITING",
        )

        assert emitted == []

        # Terminal table activity must never leak into the completed hand.
        coordinator.emit_fast_actor_observations(
            {
                "phase": "RIVER",
                "hand_token": "old-hand",
                "terminal_action_frozen": True,
            },
            changes,
            street="RIVER",
        )

        assert emitted == []

        print(
            "PASS fast actor observation transport: "
            "bet-region chronology emits immediately with "
            "same-frame commitment blockers"
        )

    finally:
        coordinator.emit = original_emit


if __name__ == "__main__":
    main()
