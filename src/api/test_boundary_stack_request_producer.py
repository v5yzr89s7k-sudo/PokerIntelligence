import json
import tempfile
from pathlib import Path

import src.api.api_event_coordinator as coordinator


def base_state():
    state = coordinator.fresh_state()
    state["phase"] = "PREFLOP"
    state["hand_token"] = "hand-A"
    return state


def frames():
    return [
        {
            "ts": 10.0,
            "frame_path": "/tmp/001.png",
            "local_board_count": 0,
        },
        {
            "ts": 11.0,
            "frame_path": "/tmp/002.png",
            "local_board_count": 3,
        },
    ]


def matching_status():
    return {
        "hand_token": "hand-A",
        "street": "PREFLOP",
        "players_owing_action": [
            "seat_mid_right",
            "seat_top",
        ],
    }


def test_valid_boundary_queues_once():
    with tempfile.TemporaryDirectory() as td:
        old_path = coordinator.BOUNDARY_STACK_REQUESTS

        try:
            coordinator.BOUNDARY_STACK_REQUESTS = (
                Path(td) / "requests.jsonl"
            )

            state = base_state()

            state, payload = (
                coordinator.maybe_queue_boundary_stack_request(
                    state,
                    previous_street="PREFLOP",
                    next_street="FLOP",
                    frames=frames(),
                    status=matching_status(),
                )
            )

            assert payload is not None
            assert payload["hand_token"] == "hand-A"
            assert payload["street"] == "PREFLOP"
            assert payload["next_street"] == "FLOP"
            assert payload["seats"] == [
                "seat_mid_right",
                "seat_top",
            ]
            assert len(payload["frames"]) == 2

            lines = (
                coordinator.BOUNDARY_STACK_REQUESTS
                .read_text()
                .splitlines()
            )

            assert len(lines) == 1
            assert json.loads(lines[0]) == payload

            state, duplicate = (
                coordinator.maybe_queue_boundary_stack_request(
                    state,
                    previous_street="PREFLOP",
                    next_street="FLOP",
                    frames=frames(),
                    status=matching_status(),
                )
            )

            assert duplicate is None

            lines = (
                coordinator.BOUNDARY_STACK_REQUESTS
                .read_text()
                .splitlines()
            )

            assert len(lines) == 1

        finally:
            coordinator.BOUNDARY_STACK_REQUESTS = old_path


def test_stale_hand_token_rejected():
    state = base_state()

    status = matching_status()
    status["hand_token"] = "hand-B"

    state, payload = (
        coordinator.maybe_queue_boundary_stack_request(
            state,
            previous_street="PREFLOP",
            next_street="FLOP",
            frames=frames(),
            status=status,
        )
    )

    assert payload is None
    assert state["last_boundary_stack_request_key"] is None


def test_wrong_status_street_rejected():
    state = base_state()

    status = matching_status()
    status["street"] = "FLOP"

    state, payload = (
        coordinator.maybe_queue_boundary_stack_request(
            state,
            previous_street="PREFLOP",
            next_street="FLOP",
            frames=frames(),
            status=status,
        )
    )

    assert payload is None


def test_empty_obligation_rejected():
    state = base_state()

    status = matching_status()
    status["players_owing_action"] = []

    state, payload = (
        coordinator.maybe_queue_boundary_stack_request(
            state,
            previous_street="PREFLOP",
            next_street="FLOP",
            frames=frames(),
            status=status,
        )
    )

    assert payload is None


def test_non_boundary_rejected():
    state = base_state()

    state, payload = (
        coordinator.maybe_queue_boundary_stack_request(
            state,
            previous_street="PREFLOP",
            next_street="PREFLOP",
            frames=frames(),
            status=matching_status(),
        )
    )

    assert payload is None


if __name__ == "__main__":
    test_valid_boundary_queues_once()
    test_stale_hand_token_rejected()
    test_wrong_status_street_rejected()
    test_empty_obligation_rejected()
    test_non_boundary_rejected()

    print(
        "PASS boundary stack request producer: "
        "valid local street advance + matching hand/street obligation "
        "queues exactly once; stale/empty/non-boundary cases queue nothing"
    )
