"""
Replay board determinism contract.

An asynchronous board request is durable semantic ownership of a recorded
board transition. Once replay reaches the next recorded frame after the
request-owning frame, wall-clock worker latency may not allow recorded
perception to outrun that unresolved board result.

Live capture is outside this contract and remains asynchronous.

No hand-specific cards, players, stack values, or frame numbers.
"""

from unittest.mock import patch

import src.api.api_event_coordinator as c


def main():
    state = c.fresh_state()

    state["phase"] = "PREFLOP"
    state["hand_token"] = "hand-test"

    # Use production's real board transport ownership.
    state["board_request_id"] = "board-request"
    state["board_request_expected_len"] = 3

    # Recorded timestamp of the frame that created this request.
    state["board_request_replay_frame_ts"] = 100.0

    assert hasattr(
        c,
        "replay_board_semantic_barrier_allows_advance",
    ), (
        "RED: replay has no board semantic barrier tied to "
        "production board-request ownership"
    )

    with patch.object(
        c,
        "find_board_result",
        return_value=None,
    ):
        before_boundary = (
            c.replay_board_semantic_barrier_allows_advance(
                state,
                next_frame_ts=100.0,
            )
        )

        after_boundary = (
            c.replay_board_semantic_barrier_allows_advance(
                state,
                next_frame_ts=101.0,
            )
        )

    print(
        "advance at request frame:",
        before_boundary,
    )
    print(
        "advance after request frame unresolved:",
        after_boundary,
    )

    assert before_boundary is True, (
        "replay must be allowed to finish the recorded frame "
        "that established board ownership"
    )

    assert after_boundary is False, (
        "RED: replay advanced beyond the recorded board-transition "
        "frame while its authoritative board request remained unresolved"
    )

    with patch.object(
        c,
        "find_board_result",
        return_value={
            "request_id": "board-request",
            "hand_token": "hand-test",
            "expected_len": 3,
            "ok": True,
            "board": ["a", "b", "c"],
        },
    ):
        ready = (
            c.replay_board_semantic_barrier_allows_advance(
                state,
                next_frame_ts=101.0,
            )
        )

    print(
        "advance when result physically ready:",
        ready,
    )

    assert ready is True

    # No board contents are interpreted by this barrier. Physical result
    # availability is sufficient; normal apply_board_result remains the
    # semantic consumer.
    print(
        "PASS replay board transport cannot be outrun by "
        "recorded perception"
    )


if __name__ == "__main__":
    main()
