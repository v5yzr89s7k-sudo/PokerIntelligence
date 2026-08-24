from unittest.mock import patch

from src.api import api_event_state_machine as sm


HAND = "provisional-bet-lifecycle"
BB = "seat_lower_left"
BTN = "seat_lower_right"


def make_state():
    # handle_stack_candidate_closed() requires only ordinary
    # state dictionaries for this lifecycle contract. Avoid
    # assuming a fresh_state() constructor that this module
    # does not expose.
    return {
        "hand_token": HAND,
        "phase": "FLOP",

        "unresolved_stack_candidates": {
            f"FLOP:{BB}": {
                "seat": BB,
                "street": "FLOP",
                "sources": [
                    "stack_motion",
                ],
            },
        },

        # Independent blocker ownership required by Gate 4H.
        # Production does not implement its lifecycle yet.
        "unresolved_provisional_bets": {
            f"FLOP:{BB}": {
                "seat": BB,
                "street": "FLOP",
                "source": "transition",
                "source_request_id": "bet-request",
            },
        },

        "pending_actor_observations": [
            {
                "type": "actor_observed",
                "hand_token": HAND,
                "seat": BTN,
                "street": "FLOP",
                "source": "bet_region_appeared",
                "blocked_seats": [
                    BB,
                ],
            },
        ],
    }


def main():
    state = make_state()

    replay_calls = []

    def fake_replay(current):
        replay_calls.append({
            "stack": dict(
                current.get(
                    "unresolved_stack_candidates"
                )
                or {}
            ),
            "provisional": dict(
                current.get(
                    "unresolved_provisional_bets"
                )
                or {}
            ),
            "pending": list(
                current.get(
                    "pending_actor_observations"
                )
                or []
            ),
        })

        return current

    # ========================================================
    # CONTRACT 1
    #
    # BB's ordinary stack candidate closes after bounded
    # unchanged quantitative reads.
    #
    # But independent provisional bet evidence remains.
    # Therefore preserved BTN chronology MUST NOT replay.
    # ========================================================

    with patch.object(
        sm,
        "replay_pending_actor_observations",
        side_effect=fake_replay,
    ):
        state = sm.handle_stack_candidate_closed(
            state,
            {
                "type": "stack_candidate_closed",
                "hand_token": HAND,
                "seat": BB,
                "street": "FLOP",
                "reason": "candidate_removed",
            },
        )

    print(
        "stack candidates:",
        state.get(
            "unresolved_stack_candidates"
        ),
    )

    print(
        "provisional blockers:",
        state.get(
            "unresolved_provisional_bets"
        ),
    )

    print(
        "pending actors:",
        state.get(
            "pending_actor_observations"
        ),
    )

    print(
        "replay calls:",
        replay_calls,
    )

    assert (
        f"FLOP:{BB}"
        not in (
            state.get(
                "unresolved_stack_candidates"
            )
            or {}
        )
    )

    assert (
        f"FLOP:{BB}"
        in (
            state.get(
                "unresolved_provisional_bets"
            )
            or {}
        )
    )

    assert replay_calls == [], (
        "REGRESSION REPRODUCED: stack candidate closure "
        "released preserved later chronology while an "
        "independent provisional bet blocker for the same "
        "seat/street still existed"
    )

    # ========================================================
    # CONTRACT 2
    #
    # Provisional evidence needs its own explicit closure
    # lifecycle. Only that closure may release chronology
    # once no other blocker remains.
    # ========================================================

    assert hasattr(
        sm,
        "handle_provisional_bet_closed",
    ), (
        "REGRESSION REPRODUCED: no independent provisional "
        "bet closure handler exists"
    )

    replay_calls.clear()

    with patch.object(
        sm,
        "replay_pending_actor_observations",
        side_effect=fake_replay,
    ):
        state = sm.handle_provisional_bet_closed(
            state,
            {
                "type": "provisional_bet_closed",
                "hand_token": HAND,
                "seat": BB,
                "street": "FLOP",
                "reason": "retired",
                "source_request_id": "bet-request",
            },
        )

    assert (
        f"FLOP:{BB}"
        not in (
            state.get(
                "unresolved_provisional_bets"
            )
            or {}
        )
    )

    assert len(replay_calls) == 1

    print(
        "PASS provisional bet blocker independently "
        "owns chronology until explicit closure"
    )


if __name__ == "__main__":
    main()
