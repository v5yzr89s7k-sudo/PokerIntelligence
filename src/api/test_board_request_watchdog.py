from pathlib import Path
import tempfile
from unittest.mock import patch

from src.api import api_event_coordinator as c


def main():
    old_requests = c.BOARD_REQUESTS
    old_results = c.BOARD_RESULTS

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        c.BOARD_REQUESTS = root / "board_requests.jsonl"
        c.BOARD_RESULTS = root / "board_results.jsonl"

        frame = root / "0054_full.png"
        frame.write_bytes(b"frame")

        try:
            state = c.fresh_state()

            state["phase"] = "PREFLOP"
            state["hand_token"] = "hand-1"
            state["confirmed_board_len"] = 0

            # Existing FLOP request has produced no result.
            state["board_request_id"] = "request-old"
            state["board_request_expected_len"] = 3

            # This field is the intended ownership timestamp. Current
            # production does not yet maintain/use it for board requests.
            state["board_request_ts"] = 100.0

            # Keep ordinary board API pacing out of the test.
            state["last_api_attempt_ts"] = 0.0

            with patch(
                "src.api.api_event_coordinator.time.time",
                return_value=105.0,
            ):
                state = c.maybe_read_board(
                    state,
                    3,
                    frame,
                )

            print(
                "board_request_id:",
                state.get("board_request_id"),
            )
            print(
                "board_request_expected_len:",
                state.get(
                    "board_request_expected_len"
                ),
            )
            print(
                "board_request_ts:",
                state.get("board_request_ts"),
            )

            requests = []

            if c.BOARD_REQUESTS.exists():
                requests = [
                    line
                    for line in
                    c.BOARD_REQUESTS.read_text().splitlines()
                    if line.strip()
                ]

            print(
                "replacement requests:",
                len(requests),
            )

            # Required transport invariant:
            #
            # A board request with no result cannot retain ownership
            # indefinitely. Once its coordinator deadline expires,
            # the old request must be retired.
            assert (
                state.get("board_request_id")
                != "request-old"
            ), (
                "REPRODUCED: missing board result "
                "retains coordinator ownership "
                "past watchdog deadline"
            )

            print(
                "PASS: stale board request no longer "
                "permanently owns board transport"
            )

        finally:
            c.BOARD_REQUESTS = old_requests
            c.BOARD_RESULTS = old_results


if __name__ == "__main__":
    main()
