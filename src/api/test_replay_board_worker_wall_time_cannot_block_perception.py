import src.api.api_event_coordinator as c


def main():
    state = c.fresh_state()

    state["hand_token"] = "test-hand"
    state["phase"] = "FLOP"
    state["board_request_id"] = "pending-board-request"
    state["board_request_expected_len"] = 4
    state["board_request_replay_frame_ts"] = 100.0

    original = c.find_board_result

    try:
        c.find_board_result = lambda request_id: None

        allowed = (
            c.replay_board_semantic_barrier_allows_advance(
                state,
                next_frame_ts=100.1,
            )
        )

        print(
            "perception advance allowed:",
            allowed,
        )

        assert allowed, (
            "RED: asynchronous board worker wall time "
            "still blocks the next recorded perception frame"
        )

        assert (
            state["board_request_id"]
            == "pending-board-request"
        ), (
            "board transport ownership was lost merely "
            "because perception advanced"
        )

        assert (
            state["board_request_expected_len"]
            == 4
        ), (
            "canonical board ownership was mutated merely "
            "because perception advanced"
        )

        print(
            "PASS: pending board transport retains canonical "
            "ownership without blocking recorded perception"
        )

    finally:
        c.find_board_result = original


if __name__ == "__main__":
    main()
