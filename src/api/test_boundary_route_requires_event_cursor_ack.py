from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import src.api.api_event_coordinator as c


HAND = "synthetic-hand"


def fresh_pending_state():
    state = c.fresh_state()
    state["hand_token"] = HAND
    state["pending_boundary_route"] = {
        "hand_token": HAND,
        "previous_street": "FLOP",
        "next_street": "TURN",
        "required_event_cursor": 12,
        "frames": [
            {
                "ts": 1.0,
                "frame_path": "/tmp/0001_full.png",
                "local_board_count": 4,
            }
        ],
    }
    return state


def main():
    with TemporaryDirectory() as tmp:
        request_path = (
            Path(tmp)
            / "boundary_stack_requests.jsonl"
        )

        # ----------------------------------------------------
        # STALE STATUS:
        # state machine has NOT consumed through the causal
        # event watermark. No ownership may be frozen yet.
        # ----------------------------------------------------
        state = fresh_pending_state()

        with patch.object(
            c,
            "BOUNDARY_STACK_REQUESTS",
            request_path,
        ), patch.object(
            c,
            "load_betting_round_status",
            return_value={
                "hand_token": HAND,
                "street": "FLOP",
                "players_owing_action": [
                    "hero",
                    "seat_lower_left",
                ],
                "processed_event_cursor": 11,
            },
        ):
            state, payload = (
                c.maybe_route_acknowledged_boundary(
                    state
                )
            )

        assert payload is None
        assert state["pending_boundary_route"] is not None
        assert not request_path.exists()

        # ----------------------------------------------------
        # ACKNOWLEDGED STATUS:
        # state machine now reflects every event through cursor
        # 12. Use THIS authoritative owing set.
        # ----------------------------------------------------
        with patch.object(
            c,
            "BOUNDARY_STACK_REQUESTS",
            request_path,
        ), patch.object(
            c,
            "load_betting_round_status",
            return_value={
                "hand_token": HAND,
                "street": "FLOP",
                "complete": False,
                "betting_open": True,
                "players_owing_action": [
                    "seat_lower_left",
                ],
                "canonical_players_to_act": [
                    "seat_lower_left",
                ],
                "processed_event_cursor": 12,
            },
        ):
            state, payload = (
                c.maybe_route_acknowledged_boundary(
                    state
                )
            )

        assert payload is not None
        assert payload["seats"] == [
            "seat_lower_left"
        ]
        assert state["pending_boundary_route"] is not None
        assert set(
            state["pending_boundary_route"].get(
                "old_street_owing_seats"
            )
            or []
        ) == {
            "seat_lower_left",
        }
        assert (
            state["pending_boundary_route"].get(
                "required_event_cursor"
            )
            is None
        )

        written = [
            json.loads(raw)
            for raw in request_path.read_text().splitlines()
            if raw.strip()
        ]

        assert len(written) == 1
        assert written[0]["seats"] == [
            "seat_lower_left"
        ]

        # ----------------------------------------------------
        # EMPTY ACKNOWLEDGED OWING SET:
        # authoritative state may determine no retrospective
        # boundary OCR is needed. Pending ownership must still
        # retire rather than waiting forever.
        # ----------------------------------------------------
        state = fresh_pending_state()

        request_path.unlink(missing_ok=True)

        with patch.object(
            c,
            "BOUNDARY_STACK_REQUESTS",
            request_path,
        ), patch.object(
            c,
            "load_betting_round_status",
            return_value={
                "hand_token": HAND,
                "street": "FLOP",
                "complete": True,
                "betting_open": False,
                "players_owing_action": [],
                "canonical_players_to_act": [],
                "processed_event_cursor": 12,
            },
        ):
            state, payload = (
                c.maybe_route_acknowledged_boundary(
                    state
                )
            )

        assert payload is None
        assert state["pending_boundary_route"] is None
        assert not request_path.exists()

    print(
        "PASS boundary event-cursor ACK: stale status waits; "
        "acknowledged open rounds route and retain authoritative "
        "owing ownership; authoritative completed empty rounds "
        "retire the pending boundary cleanly"
    )


if __name__ == "__main__":
    main()
