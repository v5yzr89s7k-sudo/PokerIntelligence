from types import SimpleNamespace
from unittest.mock import patch

import src.api.api_event_coordinator as c


def main():
    state = c.fresh_state()
    state["hand_token"] = "hand-test"
    state["phase"] = "FLOP"

    request_id = "bet-request"

    state["deferred_bet_amount_results"][request_id] = {
        "request": {
            "hand_token": "hand-test",
            "seat": "seat_mid_left",
            "street": "FLOP",
            "source": "transition",
        },
        "result": {
            "hand_token": "hand-test",
            "seat": "seat_mid_left",
            "street": "FLOP",
            "bet_bb": 2.25,
            "ok": True,
        },
        "bet_bb": 2.25,
        "seat": "seat_mid_left",
        "street": "FLOP",
    }

    state["pending_stack_reads"] = {
        "seat_mid_left": {
            "origin_street": "FLOP",
            "trigger_sources": [
                "bet_region_appeared",
            ],
        }
    }

    emitted = []

    with patch.object(
        c,
        "emit",
        side_effect=lambda event: emitted.append(dict(event)),
    ):
        c.close_pending_stack_candidate(
            state,
            state["pending_stack_reads"],
            "seat_mid_left",
            reason="candidate_removed",
        )

    print("deferred:", state["deferred_bet_amount_results"])
    print("events:", emitted)

    assert request_id not in (
        state["deferred_bet_amount_results"]
    ), (
        "provisional quantitative ownership survived "
        "after its corroboration candidate exhausted"
    )

    closures = [
        event
        for event in emitted
        if (
            event.get("type")
            == "provisional_bet_closed"
            and event.get("seat")
            == "seat_mid_left"
            and event.get("street")
            == "FLOP"
        )
    ]

    assert len(closures) == 1

    assert (
        closures[0].get("reason")
        == "stack_candidate_uncorroborated"
    )

    print()
    print(
        "PASS: exhausted stack candidate retires its "
        "same-hand/same-street provisional bet"
    )


if __name__ == "__main__":
    main()
