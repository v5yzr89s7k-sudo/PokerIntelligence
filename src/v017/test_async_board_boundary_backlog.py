"""
V0.17 asynchronous board-boundary backlog ownership.

A later physical street boundary must not disappear while an earlier
board identity request owns transport.
"""

from pathlib import Path

import src.v017.run_live_observer as live


class FakeBoardReader:
    def __init__(self):
        self.future = None
        self.request = None
        self.submissions = []

    def submit_if_idle(
        self,
        *,
        frame_path,
        boundary_event,
        expected_count,
    ):
        if self.future is not None:
            return False

        self.future = object()

        self.request = {
            "frame_path": frame_path,
            "boundary_event":
                dict(boundary_event),
            "expected_count":
                int(expected_count),
        }

        self.submissions.append(
            (
                boundary_event["frame"],
                boundary_event["type"],
                int(expected_count),
            )
        )

        return True


def main():
    state = live.FrameTransactionState()

    # Avoid creating/using the real executor in this structural
    # backlog test.
    state.board_identity_reader.close()

    fake = FakeBoardReader()

    state.board_identity_reader = fake

    flop = {
        "frame_path":
            Path("/tmp/flop.png"),
        "boundary_event": {
            "frame": 100,
            "type":
                "FLOP_BOUNDARY_PHYSICAL",
        },
        "expected_count": 3,
    }

    turn = {
        "frame_path":
            Path("/tmp/turn.png"),
        "boundary_event": {
            "frame": 120,
            "type":
                "TURN_BOUNDARY_PHYSICAL",
        },
        "expected_count": 4,
    }

    state.pending_board_boundaries.extend(
        [
            flop,
            turn,
        ]
    )

    assert (
        live.submit_next_pending_board_boundary(
            state
        )
        is True
    )

    assert fake.submissions == [
        (
            100,
            "FLOP_BOUNDARY_PHYSICAL",
            3,
        )
    ]

    assert [
        item["boundary_event"]["frame"]
        for item
        in state.pending_board_boundaries
    ] == [120]

    # Transport remains owned by FLOP.
    assert (
        live.submit_next_pending_board_boundary(
            state
        )
        is False
    )

    assert [
        item["boundary_event"]["frame"]
        for item
        in state.pending_board_boundaries
    ] == [120]

    # Simulate FLOP result collection retiring transport.
    fake.future = None
    fake.request = None

    assert (
        live.submit_next_pending_board_boundary(
            state
        )
        is True
    )

    assert fake.submissions == [
        (
            100,
            "FLOP_BOUNDARY_PHYSICAL",
            3,
        ),
        (
            120,
            "TURN_BOUNDARY_PHYSICAL",
            4,
        ),
    ]

    assert (
        state.pending_board_boundaries
        == []
    )

    print(
        "ASYNC BOARD BOUNDARY BACKLOG: PASS"
    )


if __name__ == "__main__":
    main()
