"""
RED contract.

An unresolved same-hand/same-street transition bet is already
aggression ownership even before stack corroboration allows the BET
to become canonical.

That provisional aggression may widen a responder's numeric stack
continuity search.

It must NOT:
- publish the provisional BET;
- publish the responder's action;
- count as final stack-transition commitment evidence;
- cross hand/street boundaries.
"""

from src.api import api_event_coordinator as c


def main():
    state = c.fresh_state()

    state["hand_token"] = "hand-a"
    state["phase"] = "FLOP"

    # BB's visible transition has already produced a quantitative bet
    # result, but stack corroboration has not arrived yet.
    state["deferred_bet_amount_results"] = {
        "bb-request": {
            "request": {
                "request_id": "bb-request",
                "hand_token": "hand-a",
                "seat": "bb",
                "street": "FLOP",
                "source": "transition",
            },
            "result": {
                "request_id": "bb-request",
                "hand_token": "hand-a",
                "seat": "bb",
                "street": "FLOP",
                "bet_bb": 3.25,
                "ok": True,
            },
            "bet_bb": 3.25,
            "seat": "bb",
            "street": "FLOP",
        }
    }

    # Gate 6O requires a pure coordinator helper that exposes the seats
    # which may safely use the wider continuity SEARCH window because
    # they are responding to unresolved earlier aggression.
    #
    # Naming is intentionally fixed now so production and future tests
    # have one contract.
    assert hasattr(
        c,
        "provisional_response_context_seats",
    ), (
        "RED: coordinator has no provisional-aggression "
        "response-context helper"
    )

    responders = c.provisional_response_context_seats(
        state,
        hand_token="hand-a",
        street="FLOP",
        candidate_seats={"hero", "btn"},
    )

    print(
        "responders:",
        sorted(responders),
    )

    assert "hero" in responders
    assert "btn" in responders

    # Wrong hand must fail closed.
    assert not c.provisional_response_context_seats(
        state,
        hand_token="other-hand",
        street="FLOP",
        candidate_seats={"hero"},
    )

    # Wrong street must fail closed.
    assert not c.provisional_response_context_seats(
        state,
        hand_token="hand-a",
        street="TURN",
        candidate_seats={"hero"},
    )

    # Initial inventory is not aggression.
    state["deferred_bet_amount_results"] = {
        "initial-request": {
            "request": {
                "request_id": "initial-request",
                "hand_token": "hand-a",
                "seat": "bb",
                "street": "FLOP",
                "source": "initial_inventory",
            },
            "result": {
                "request_id": "initial-request",
                "hand_token": "hand-a",
                "seat": "bb",
                "street": "FLOP",
                "bet_bb": 3.25,
                "ok": True,
            },
            "bet_bb": 3.25,
            "seat": "bb",
            "street": "FLOP",
        }
    }

    assert not c.provisional_response_context_seats(
        state,
        hand_token="hand-a",
        street="FLOP",
        candidate_seats={"hero"},
    )

    print()
    print(
        "PASS: unresolved transition aggression can "
        "safely supply continuity-search response context"
    )


if __name__ == "__main__":
    main()
