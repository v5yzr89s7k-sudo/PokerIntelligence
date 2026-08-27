"""
Generic asynchronous ordering regression.

A provisional bet result may arrive after the corresponding physical
commitment has already been quantitatively resolved and consumed.

Once that same-hand/same-street/seat commitment has been consumed,
a late provisional OPEN must not recreate chronology ownership.

No replay-specific frames, cards, stack values, or player identities.
"""

import src.api.api_event_state_machine as sm


ACTOR = "seat_test"
STREET = "FLOP"
TOKEN = "hand-test"


def main():
    state = sm.default_state()

    state["phase"] = STREET
    state["hand_token"] = TOKEN
    state["canonical_snapshot_ready"] = True

    key = f"{STREET}:{ACTOR}"

    # Generic post-consumption state:
    #
    # The quantitative commitment is no longer unresolved. This is exactly
    # what handle_inferred_action establishes after successful canonical
    # tracker ingestion.
    state["unresolved_stack_candidates"] = {}
    state["unresolved_provisional_bets"] = {}
    state["consumed_quantitative_commitments"] = {
        key: {
            "seat": ACTOR,
            "street": STREET,
            "action": "CALL",
            "ts": 10.0,
        }
    }

    assert key not in state["unresolved_stack_candidates"]
    assert key not in state["unresolved_provisional_bets"]

    late_event = {
        "type": "provisional_bet_opened",
        "hand_token": TOKEN,
        "seat": ACTOR,
        "street": STREET,
        "source": "transition",
        "source_request_id": "late-request",
        "bet_bb": 2.5,
        "ts": 20.0,
    }

    print("before:", state["unresolved_provisional_bets"])

    state = sm.handle_provisional_bet_opened(
        state,
        late_event,
    )

    print("after :", state["unresolved_provisional_bets"])

    assert key not in (
        state.get("unresolved_provisional_bets")
        or {}
    ), (
        "RED: a late asynchronous provisional-bet OPEN recreated "
        "chronology ownership after the corresponding quantitative "
        "commitment had already been consumed"
    )

    print()
    print(
        "PASS late provisional result cannot reopen "
        "resolved commitment ownership"
    )


if __name__ == "__main__":
    main()
