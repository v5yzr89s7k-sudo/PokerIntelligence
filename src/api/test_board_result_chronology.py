"""
Regression: completed board worker results must not advance the street through
the pre-perception worker fast path.

Board results remain pending until maybe_read_board(), which is reached after
local perception, episode settlement, scheduling, inference, and qualification.
"""

import src.api.api_event_coordinator as coordinator


REQUEST_ID = "board-test-request"
HAND_TOKEN = "hand-test-token"

BOARD_RESULT = {
    "request_id": REQUEST_ID,
    "hand_token": HAND_TOKEN,
    "ok": True,
    "expected_len": 3,
    "board": ["As", "Kd", "7c"],
    "elapsed_ms": 12.5,
}


def make_state():
    state = coordinator.fresh_state()

    state.update({
        "phase": "PREFLOP",
        "hero_read": True,
        "hand_token": HAND_TOKEN,
        "confirmed_board_len": 0,
        "board_request_id": REQUEST_ID,
        "board_request_expected_len": 3,
        "hero_request_id": None,
        "pot_request_id": None,
    })

    return state


original_find_board_result = coordinator.find_board_result
original_emit = coordinator.emit
original_log_latency = coordinator.log_latency
original_save_state = coordinator.save_state

emitted = []

try:
    coordinator.find_board_result = (
        lambda request_id:
        BOARD_RESULT
        if request_id == REQUEST_ID
        else None
    )

    coordinator.emit = lambda event: emitted.append(dict(event))
    coordinator.log_latency = lambda *args, **kwargs: None
    coordinator.save_state = lambda state: None

    # ------------------------------------------------------------------
    # Phase 1:
    # The pre-perception worker consumer MUST NOT consume the board result.
    # ------------------------------------------------------------------

    state = make_state()

    state, consumed, board_emitted = (
        coordinator.consume_ready_worker_results(state)
    )

    assert consumed is False
    assert board_emitted is False

    assert state["phase"] == "PREFLOP"
    assert state["confirmed_board_len"] == 0

    assert state["board_request_id"] == REQUEST_ID
    assert state["board_request_expected_len"] == 3

    assert emitted == []

    # ------------------------------------------------------------------
    # Phase 2:
    # The chronology-safe board path consumes that SAME pending result.
    # ------------------------------------------------------------------

    state = coordinator.maybe_read_board(
        state,
        count=3,
        frame=None,
    )

    assert state["phase"] == "FLOP"
    assert state["confirmed_board_len"] == 3

    assert state["board_request_id"] is None
    assert state["board_request_expected_len"] is None

    board_events = [
        event
        for event in emitted
        if event.get("type") == "board"
    ]

    assert board_events == [
        {
            "type": "board",
            "board": ["As", "Kd", "7c"],
        }
    ]

finally:
    coordinator.find_board_result = original_find_board_result
    coordinator.emit = original_emit
    coordinator.log_latency = original_log_latency
    coordinator.save_state = original_save_state


print("Board result chronology regression passed.")
