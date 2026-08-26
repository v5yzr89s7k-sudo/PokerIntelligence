"""
Contract for read-only betting context used by stack continuity search.

The coordinator may widen numeric continuity search when authoritative
same-hand/same-street betting state establishes that a seat still owes a
response to open aggression.

This helper is evidence routing only:
- it does not publish an action;
- it does not mutate canonical betting state;
- it does not constitute final semantic commitment evidence;
- stale hand/street status must fail closed.
"""

from src.api import api_event_coordinator as c


def context(status, *, token="hand-a", street="FLOP", seat="hero"):
    return c.stack_response_context(
        status,
        hand_token=token,
        street=street,
        seat=seat,
    )


def test_positive_response():
    status = {
        "hand_token": "hand-a",
        "street": "FLOP",
        "betting_open": True,
        "players_owing_action": [
            "hero",
            "seat_lower_right",
        ],
        "current_price": 3.25,
        "last_aggressor": "seat_lower_left",
    }

    result = context(status)

    print("positive:", result)

    assert result["authoritative"] is True
    assert result["owes_response"] is True
    assert result["betting_open"] is True


def test_not_owing_fails_closed():
    status = {
        "hand_token": "hand-a",
        "street": "FLOP",
        "betting_open": True,
        "players_owing_action": [
            "seat_lower_right",
        ],
        "current_price": 3.25,
        "last_aggressor": "seat_lower_left",
    }

    result = context(status)

    print("not owing:", result)

    assert result["authoritative"] is True
    assert result["owes_response"] is False


def test_no_open_aggression_fails_closed():
    status = {
        "hand_token": "hand-a",
        "street": "FLOP",
        "betting_open": False,
        "players_owing_action": [
            "hero",
        ],
        "current_price": 0.0,
        "last_aggressor": None,
    }

    result = context(status)

    print("no aggression:", result)

    assert result["authoritative"] is True
    assert result["owes_response"] is False


def test_wrong_hand_fails_closed():
    status = {
        "hand_token": "old-hand",
        "street": "FLOP",
        "betting_open": True,
        "players_owing_action": ["hero"],
    }

    result = context(status)

    print("wrong hand:", result)

    assert result["authoritative"] is False
    assert result["owes_response"] is False


def test_wrong_street_fails_closed():
    status = {
        "hand_token": "hand-a",
        "street": "TURN",
        "betting_open": True,
        "players_owing_action": ["hero"],
    }

    result = context(status)

    print("wrong street:", result)

    assert result["authoritative"] is False
    assert result["owes_response"] is False


def test_missing_status_fails_closed():
    result = context({})

    print("missing:", result)

    assert result["authoritative"] is False
    assert result["owes_response"] is False


def main():
    test_positive_response()
    test_not_owing_fails_closed()
    test_no_open_aggression_fails_closed()
    test_wrong_hand_fails_closed()
    test_wrong_street_fails_closed()
    test_missing_status_fails_closed()

    print()
    print(
        "PASS stack response betting context: "
        "same-hand/same-street open aggression + owing seat "
        "is the only positive response context"
    )


if __name__ == "__main__":
    main()
