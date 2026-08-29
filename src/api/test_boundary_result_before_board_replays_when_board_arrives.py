"""
Regression contract:

A retrospective boundary-stack result may arrive before the confirmed
next-street board event.

If the result belongs to the currently canonical old street, it must not
become stranded merely because pending_board_events is empty at the exact
instant the asynchronous boundary worker finishes.

Once the matching next-street board subsequently arrives, the preserved
boundary result must be replayed against the still-canonical old street so
that old-street obligations can resolve and the board can promote.
"""

import copy

import src.api.api_event_state_machine as sm


OLD = "TURN"
NEXT = "RIVER"


def main():

    state = {
        "phase": OLD,
        "hand_token": "boundary-result-before-board-test",
        "canonical_snapshot_ready": True,
        "pending_board_events": [],
        "pending_boundary_results": [],
    }

    result = {
        "type": "boundary_stack_result",
        "request_id": "early-boundary-result",
        "hand_token": state["hand_token"],
        "street": OLD,
        "next_street": NEXT,
        "observations": [],
        "ts": 100.0,
    }

    print()
    print("===== EARLY BOUNDARY RESULT =====")

    # Isolate the ordering contract. The current implementation should
    # preserve this because the matching River board does not exist yet.
    original_canonical_ready = (
        state["canonical_snapshot_ready"]
    )

    before = copy.deepcopy(state)

    # We cannot safely execute full poker semantics without constructing
    # an entire CanonicalHand. Instead reproduce the routing predicate
    # owned by handle_boundary_stack_result().
    current_street = str(
        state.get("phase") or ""
    ).upper()

    old_street = str(
        result.get("street") or ""
    ).upper()

    expected_current = {
        "PREFLOP": "FLOP",
        "FLOP": "TURN",
        "TURN": "RIVER",
    }.get(old_street)

    pending_boards = list(
        state.get("pending_board_events")
        or []
    )

    matching_pending_board = any(
        sm.transition_for_board_len(
            len(item.get("board") or [])
        )
        == expected_current
        for item in pending_boards
        if isinstance(item, dict)
    )

    assert old_street == current_street
    assert expected_current == NEXT
    assert matching_pending_board is False

    state["pending_boundary_results"].append(
        dict(result)
    )

    print(
        "preserved boundary results:",
        [
            item.get("request_id")
            for item in state[
                "pending_boundary_results"
            ]
        ],
    )

    print()
    print("===== RIVER BOARD ARRIVES LATER =====")

    river_event = {
        "type": "board",
        "board": [
            "Jd",
            "9s",
            "Tc",
            "9h",
            "7h",
        ],
        "ts": 101.0,
    }

    # Model handle_board's blocked-board state:
    # TURN is still canonical and River becomes pending.
    state["pending_board_events"].append(
        dict(river_event)
    )

    matching_now = any(
        sm.transition_for_board_len(
            len(item.get("board") or [])
        )
        == NEXT
        for item in (
            state.get("pending_board_events")
            or []
        )
        if isinstance(item, dict)
    )

    print(
        "matching River pending:",
        matching_now,
    )

    assert matching_now is True

    # Contract we need:
    #
    # Once the matching pending board exists while the old street is
    # still canonical, already-arrived boundary results for that street
    # must be selected for immediate old-street replay.
    replayable = [
        item
        for item in (
            state.get(
                "pending_boundary_results"
            )
            or []
        )
        if (
            str(
                item.get("street")
                or ""
            ).upper()
            == OLD
        )
    ]

    print(
        "replayable after board arrival:",
        [
            item.get("request_id")
            for item in replayable
        ],
    )

    # This deliberately tests for the missing production behavior rather
    # than merely proving that the data remains stored.
    helper = getattr(
        sm,
        "replay_pending_boundary_results_for_current_street",
        None,
    )

    assert helper is not None, (
        "RED: matching next-street board can arrive after its "
        "boundary result, but there is no current-street replay path "
        "to consume the already-preserved result"
    )

    print(
        "PASS boundary result/board ordering contract"
    )


if __name__ == "__main__":
    main()
