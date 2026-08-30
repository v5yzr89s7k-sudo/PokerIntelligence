import src.api.api_event_coordinator as c


def main():
    original_emit = c.emit
    original_log_latency = c.log_latency

    emitted = []

    try:
        c.emit = lambda event: emitted.append(
            dict(event)
        )

        c.log_latency = (
            lambda *args, **kwargs: None
        )

        state = c.fresh_state()

        state["phase"] = "FLOP"
        state["hand_token"] = "board-repair-test"

        # The first, shorter API read was wrong and has already
        # become coordinator-owned board state.
        state["confirmed_board"] = [
            "Jd",
            "9s",
            "Ts",
        ]

        state["confirmed_board_len"] = 3

        # ----------------------------------------------------
        # First longer read contradicts the bad FLOP.
        # It should establish contradiction evidence but
        # should not immediately rewrite canonical ownership.
        # ----------------------------------------------------

        state["board_request_id"] = "turn-read-1"
        state[
            "board_request_expected_len"
        ] = 4

        state, accepted_1 = (
            c.apply_board_result(
                state,
                {
                    "type": "board_result",
                    "request_id": "turn-read-1",
                    "hand_token":
                        "board-repair-test",
                    "expected_len": 4,
                    "ok": True,
                    "board": [
                        "Jd",
                        "9s",
                        "Tc",
                        "9h",
                    ],
                    "elapsed_ms": 1500.0,
                },
            )
        )

        print(
            "first accepted:",
            accepted_1,
        )

        print(
            "after first:",
            state.get(
                "confirmed_board"
            ),
        )

        assert not accepted_1, (
            "first contradictory longer read "
            "must not immediately rewrite "
            "confirmed board"
        )

        assert (
            state.get("confirmed_board")
            == [
                "Jd",
                "9s",
                "Ts",
            ]
        ), (
            "first contradiction mutated "
            "confirmed board"
        )

        # ----------------------------------------------------
        # A second independent longer read returns the exact
        # same contradictory board.
        #
        # At this point the longer-board evidence has been
        # independently confirmed. Keeping the original bad
        # three-card prefix would only manufacture endless
        # expensive API retries.
        # ----------------------------------------------------

        state["board_request_id"] = "turn-read-2"
        state[
            "board_request_expected_len"
        ] = 4

        state, accepted_2 = (
            c.apply_board_result(
                state,
                {
                    "type": "board_result",
                    "request_id": "turn-read-2",
                    "hand_token":
                        "board-repair-test",
                    "expected_len": 4,
                    "ok": True,
                    "board": [
                        "Jd",
                        "9s",
                        "Tc",
                        "9h",
                    ],
                    "elapsed_ms": 1600.0,
                },
            )
        )

        print(
            "second accepted:",
            accepted_2,
        )

        print(
            "final confirmed:",
            state.get(
                "confirmed_board"
            ),
        )

        print(
            "final length:",
            state.get(
                "confirmed_board_len"
            ),
        )

        print(
            "phase:",
            state.get("phase"),
        )

        print(
            "emitted:",
            emitted,
        )

        assert accepted_2, (
            "RED: independently confirmed "
            "longer-board contradiction was "
            "rejected again, forcing another "
            "expensive API retry"
        )

        assert (
            state.get("confirmed_board")
            == [
                "Jd",
                "9s",
                "Tc",
                "9h",
            ]
        ), (
            "RED: repeated longer-board evidence "
            "did not repair bad shorter prefix"
        )

        assert (
            state.get(
                "confirmed_board_len"
            )
            == 4
        )

        assert (
            state.get("phase")
            == "TURN"
        )

        board_events = [
            event
            for event in emitted
            if (
                event.get("type")
                == "board"
            )
        ]

        assert len(board_events) == 1, (
            "board repair must publish exactly "
            "one accepted TURN event"
        )

        assert (
            board_events[0].get("board")
            == [
                "Jd",
                "9s",
                "Tc",
                "9h",
            ]
        )

        print(
            "PASS: two identical longer-board "
            "reads repair one bad shorter API "
            "prefix instead of retrying forever"
        )

    finally:
        c.emit = original_emit
        c.log_latency = (
            original_log_latency
        )


if __name__ == "__main__":
    main()
