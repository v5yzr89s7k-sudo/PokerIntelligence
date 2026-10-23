
"""Blocked board catch-up must preserve identity for retry."""

from src.v017.test_live_board_catchup import make_observer
from src.v017.run_live_observer import (
    FrameTransactionState,
    finalize_async_board_identity_result,
)


def main():
    observer = make_observer()

    observer.admit_street_boundary(
        {
            "frame": 90,
            "type": "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
        },
        action_order=["hero", "bb"],
        board=["2h", "9c", "Ts"],
    )

    observer.quantitative_confirmation_pending["hero"] = {
        "first_frame": 95,
        "street": "FLOP",
        "value": 45.0,
    }

    state = FrameTransactionState()

    completed = {
        "request": {
            "boundary_event": {
                "frame": 100,
                "type": "FLOP_BOUNDARY_PHYSICAL",
                "board_count": 3,
            },
            "expected_count": 3,
        },
        "board": ["2h", "9c", "Ts", "Td", "7s"],
        "error": None,
    }

    try:
        result = finalize_async_board_identity_result(
            observer,
            state,
            completed,
            publication_frame=100,
        )

        print("street=", observer.hand.street)
        print("applied=", result.get("applied"))
        print(
            "identity_retained=",
            state.pending_board_identity_result is not None,
        )

        assert observer.hand.street == "FLOP"
        assert state.pending_board_identity_result is not None, (
            "RED: BLOCKED BOARD IDENTITY DISCARDED"
        )

        # Resolve quantitative ownership and retry the exact
        # retained identity without another physical observation.
        observer.quantitative_confirmation_pending.pop("hero")

        retry = finalize_async_board_identity_result(
            observer,
            state,
            state.pending_board_identity_result,
            publication_frame=101,
        )

        print("retry_applied=", retry.get("applied"))
        print("final_street=", observer.hand.street)
        print("final_board=", observer.hand.board)

        assert retry["applied"] is True
        assert observer.hand.street == "RIVER"
        assert observer.hand.board == [
            "2h", "9c", "Ts", "Td", "7s"
        ]
        assert state.pending_board_identity_result is None

    finally:
        state.board_identity_reader.close()

    print("BOARD IDENTITY RETENTION: PASS")


if __name__ == "__main__":
    main()
