from src.api.api_event_coordinator import (
    apply_board_result,
    fresh_state,
)


def base_state(request_id):
    state = fresh_state()

    state.update({
        "confirmed_board_len": 3,
        "confirmed_board": ["Jd", "9s", "Tc"],
        "phase": "FLOP",
        "hero_decision_active": False,
        "last_hero_action_complete_phase": None,
        "hand_token": "board-prefix-test",
        "board_request_id": request_id,
        "board_request_expected_len": 4,
    })

    return state


def test_matching_prefix_accepts_turn():
    state = base_state("turn-ok")

    result = {
        "request_id": "turn-ok",
        "hand_token": "board-prefix-test",
        "ok": True,
        "expected_len": 4,
        "board": ["Jd", "9s", "Tc", "9h"],
        "elapsed_ms": 1.0,
    }

    state, emitted = apply_board_result(
        state,
        result,
    )

    assert emitted is True
    assert state["confirmed_board_len"] == 4


def test_mutated_prefix_rejected():
    state = base_state("turn-bad")

    result = {
        "request_id": "turn-bad",
        "hand_token": "board-prefix-test",
        "ok": True,
        "expected_len": 4,
        "board": ["Jh", "9s", "Tc", "9h"],
        "elapsed_ms": 1.0,
    }

    state, emitted = apply_board_result(
        state,
        result,
    )

    assert emitted is False
    assert state["confirmed_board_len"] == 3
    assert state["phase"] == "FLOP"


def main():
    test_matching_prefix_accepts_turn()
    test_mutated_prefix_rejected()

    print(
        "PASS board prefix integrity: "
        "later streets must preserve every previously confirmed board card"
    )


if __name__ == "__main__":
    main()
