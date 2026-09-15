"""
Regression contract:

Local board-count evidence must be capable of publishing the physical
next-street boundary before asynchronous board-card identity completes.

This event is evidence only. It must NOT mutate canonical board cards or
advance authoritative canonical street by itself.
"""

import copy

import src.api.api_event_state_machine as sm


def main():

    state = {
        "phase": "PREFLOP",
        "board": [],
        "physical_street": "PREFLOP",
        "pending_physical_street_boundaries": [],
    }

    event = {
        "type": "physical_street_boundary",
        "street": "FLOP",
        "board_count": 3,
        "ts": 100.0,
        "source": "local_board_count",
    }

    before = copy.deepcopy(
        state
    )

    handler = getattr(
        sm,
        "handle_physical_street_boundary",
        None,
    )

    assert handler is not None, (
        "RED: state machine has no physical-street-boundary "
        "handler; board API completion still owns street-boundary "
        "knowledge"
    )

    after = handler(
        state,
        event,
    )

    print()
    print(
        "before:",
        before,
    )

    print()
    print(
        "after:",
        after,
    )

    assert (
        after.get("physical_street")
        == "FLOP"
    ), (
        "RED: local board-count evidence did not establish "
        "physical FLOP immediately"
    )

    assert (
        after.get("phase")
        == "PREFLOP"
    ), (
        "physical evidence illegally advanced authoritative "
        "canonical phase"
    )

    assert (
        after.get("board")
        == []
    ), (
        "physical evidence illegally fabricated board identity"
    )

    print()
    print(
        "PASS: physical FLOP exists independently of "
        "asynchronous card identity while canonical authority "
        "remains unchanged"
    )


if __name__ == "__main__":
    main()
