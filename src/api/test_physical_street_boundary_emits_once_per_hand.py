"""
Regression contract for physical street-boundary ownership.

Within one hand:

    FLOP  may publish once.
    TURN  may publish once.
    RIVER may publish once.

Repeated frames while canonical state trails physical state must not
republish the same boundary.

After the hand returns to WAITING, stale board pixels must not create
new physical-street events.
"""

import src.api.api_event_coordinator as c


def main():

    helper = getattr(
        c,
        "claim_physical_street_boundary",
        None,
    )

    assert helper is not None, (
        "RED: coordinator has no durable per-hand "
        "physical-boundary ownership helper"
    )

    state = {
        "phase": "PREFLOP",
        "hand_token": "hand-a",
    }

    print(
        "===== FLOP ====="
    )

    first = helper(
        state,
        street="FLOP",
        board_count=3,
    )

    second = helper(
        state,
        street="FLOP",
        board_count=3,
    )

    third = helper(
        state,
        street="FLOP",
        board_count=3,
    )

    print(
        "claims:",
        first,
        second,
        third,
    )

    assert first is True, (
        "first FLOP boundary was not claimed"
    )

    assert second is False
    assert third is False

    print()
    print(
        "===== TURN ====="
    )

    turn_1 = helper(
        state,
        street="TURN",
        board_count=4,
    )

    turn_2 = helper(
        state,
        street="TURN",
        board_count=4,
    )

    print(
        "claims:",
        turn_1,
        turn_2,
    )

    assert turn_1 is True
    assert turn_2 is False

    print()
    print(
        "===== RIVER ====="
    )

    river_1 = helper(
        state,
        street="RIVER",
        board_count=5,
    )

    river_2 = helper(
        state,
        street="RIVER",
        board_count=5,
    )

    print(
        "claims:",
        river_1,
        river_2,
    )

    assert river_1 is True
    assert river_2 is False

    print()
    print(
        "===== POST-HAND STALE BOARD ====="
    )

    state["phase"] = "WAITING"
    state["hand_token"] = None

    stale = helper(
        state,
        street="RIVER",
        board_count=5,
    )

    print(
        "claim:",
        stale,
    )

    assert stale is False, (
        "RED: stale post-hand river pixels can "
        "reopen physical-boundary ownership"
    )

    print()
    print(
        "===== NEW HAND ====="
    )

    state["phase"] = "PREFLOP"
    state["hand_token"] = "hand-b"

    new_flop = helper(
        state,
        street="FLOP",
        board_count=3,
    )

    print(
        "claim:",
        new_flop,
    )

    assert new_flop is True, (
        "new hand did not receive fresh physical "
        "boundary ownership"
    )

    print()
    print(
        "PASS: physical street boundaries are "
        "single-publication per hand and stale "
        "post-hand board pixels cannot resurrect them"
    )


if __name__ == "__main__":
    main()
