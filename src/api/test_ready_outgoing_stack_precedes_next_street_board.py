from unittest.mock import patch

from src.api import api_event_coordinator as c


def main():
    state = c.fresh_state()

    state["phase"] = "FLOP"
    state["hand_token"] = "generic-hand"

    state["board_request_id"] = "turn-board-request"
    state["board_request_expected_len"] = 4

    state["pending_stack_reads"] = {
        "hero": {
            "origin_street": "FLOP",
            "last_stack_sample_ts": 10.0,
            "last_change_ts": 10.0,
            "stack_worker_request_id": "hero-stack-request",
        }
    }

    state["pending_stack_worker_requests"] = {
        "hero-stack-request": {
            "seat": "hero",
            "street": "FLOP",
            "purpose": "settled",
            "hand_token": "generic-hand",
            "frame": "/tmp/frame.png",
        }
    }

    board_result = {
        "type": "board_result",
        "request_id": "turn-board-request",
        "hand_token": "generic-hand",
        "expected_len": 4,
        "board": ["As", "Kd", "7c", "2h"],
        "ok": True,
    }

    stack_result = {
        "type": "stack_result",
        "request_id": "hero-stack-request",
        "hand_token": "generic-hand",
        "seat": "hero",
        "street": "FLOP",
        "purpose": "settled",
        "ok": True,
    }

    applied_boards = []

    def fake_apply_board_result(
        coordinator_state,
        result,
    ):
        applied_boards.append(result)
        coordinator_state["phase"] = "TURN"
        return coordinator_state, True

    with patch.object(
        c,
        "find_board_result",
        return_value=board_result,
    ), patch.object(
        c,
        "find_stack_worker_result",
        side_effect=lambda request_id: (
            stack_result
            if request_id == "hero-stack-request"
            else None
        ),
    ), patch.object(
        c,
        "apply_board_result",
        side_effect=fake_apply_board_result,
    ), patch.object(
        c,
        "save_state",
    ):
        state, consumed, board_emitted = (
            c.consume_ready_worker_results(
                state
            )
        )

    print(
        "board applications:",
        len(applied_boards),
    )
    print(
        "phase:",
        state.get("phase"),
    )
    print(
        "consumed:",
        consumed,
    )
    print(
        "board emitted:",
        board_emitted,
    )

    assert not applied_boards, (
        "RED: next-street board was applied while "
        "completed outgoing-street settled-stack "
        "evidence still owned reconciliation"
    )

    assert state["phase"] == "FLOP", (
        "RED: coordinator advanced street before "
        "ready outgoing-street quantitative evidence "
        "received reconciliation"
    )

    assert (
        state["board_request_id"]
        == "turn-board-request"
    ), (
        "RED: deferred board lost durable request ownership"
    )

    assert not consumed, (
        "RED: deferred board was reported as consumed"
    )

    assert not board_emitted, (
        "RED: deferred board was reported as emitted"
    )

    print(
        "PASS ready outgoing-stack barrier: "
        "next-street board remains pending until "
        "old-street quantitative evidence reconciles"
    )


if __name__ == "__main__":
    main()
