from unittest.mock import patch

from src.api import api_event_coordinator as c


class Changes:
    board_count = 4
    bet_region_appeared = ["seat_lower_left"]
    stack_changed_seats = []
    opponent_hole_cards_disappeared_seats = []


def main():
    state = c.fresh_state()

    state["phase"] = "FLOP"
    state["hand_token"] = "event-time-fast-actor-test"

    changes = Changes()

    event_street = c.event_street_for_frame(
        state,
        changes.board_count,
    )

    print("canonical street:", state["phase"])
    print("local board count:", changes.board_count)
    print("event street:", event_street)

    assert event_street == "TURN", (
        "test setup invalid: local four-card board should "
        "provisionally own TURN event attribution"
    )

    emitted = []

    with patch.object(
        c,
        "emit",
        side_effect=lambda event: emitted.append(dict(event)),
    ):
        # This models what the chronology fast path SHOULD do:
        # use the already-computed event-time street rather than
        # canonical state["phase"].
        c.emit_fast_actor_observations(
            state,
            changes,
            street=event_street,
        )

        c.emit_physical_actor_completions(
            changes,
            state,
            street=event_street,
        )

    actor = next(
        (
            event
            for event in emitted
            if event.get("type") == "actor_observed"
        ),
        None,
    )

    print("actor event:", actor)

    assert actor is not None, (
        "RED: expected physical actor observation"
    )

    assert actor.get("street") == "TURN", (
        "RED: fast physical chronology inherited stale "
        "canonical FLOP instead of event-time TURN"
    )

    # Now inspect the production call-site contract itself.
    source = open(
        "src/api/api_event_coordinator.py",
        "r",
    ).read()

    expected_call = """emit_fast_actor_observations(
            state,
            changes,
            street=event_street,
        )"""

    expected_completion = """emit_physical_actor_completions(
            changes,
            state,
            street=event_street,
        )"""

    assert expected_call in source, (
        "RED: production fast actor path still does not use "
        "event-time street attribution"
    )

    assert expected_completion in source, (
        "RED: production physical completion path still does "
        "not use event-time street attribution"
    )

    print(
        "PASS: fast physical chronology uses event-time street "
        "while canonical state may still own the prior street"
    )


if __name__ == "__main__":
    main()
