import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import src.api.api_event_coordinator as coord


def read_events(path):
    if not path.exists():
        return []

    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def main():
    old_event_log = coord.EVENT_LOG

    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            coord.EVENT_LOG = root / "api_events.jsonl"
            coord.EVENT_LOG.write_text("")

            # ========================================================
            # Transition result: numeric read arrives first.
            # It must NOT publish yet.
            # ========================================================

            state = coord.fresh_state()
            state["hand_token"] = "hand-test"
            state["phase"] = "RIVER"

            request_id = "transition-request"

            state[
                "pending_bet_amount_requests"
            ][request_id] = {
                "seat": "seat_lower_left",
                "street": "RIVER",
                "frame": "frame.png",
                "source": "transition",
                "hand_token": "hand-test",
                "queued_ts": 1.0,
            }

            result = {
                "type": "bet_amount_result",
                "request_id": request_id,
                "hand_token": "hand-test",
                "seat": "seat_lower_left",
                "street": "RIVER",
                "frame": "frame.png",
                "ok": True,
                "bet_bb": 6.75,
                "elapsed_ms": 100.0,
                "ts": 2.0,
            }

            state, consumed = (
                coord.apply_bet_amount_result(
                    state,
                    result,
                )
            )

            assert consumed is True
            assert read_events(
                coord.EVENT_LOG
            ) == []

            assert (
                request_id
                in state[
                    "deferred_bet_amount_results"
                ]
            )

            # ========================================================
            # No stack commitment yet -> still no publication.
            # ========================================================

            changes = SimpleNamespace(
                stack_changed_seats=[],
                stack_change_details={},
            )

            state = (
                coord.release_corroborated_bet_amount_results(
                    state,
                    changes,
                )
            )

            assert read_events(
                coord.EVENT_LOG
            ) == []

            # ========================================================
            # Same-seat/same-street positive stack delta releases it.
            # ========================================================

            changes = SimpleNamespace(
                stack_changed_seats=[
                    "seat_lower_left"
                ],
                stack_change_details={
                    "seat_lower_left": {
                        "origin_street": "RIVER",
                        "delta_bb": 6.75,
                    }
                },
            )

            state = (
                coord.release_corroborated_bet_amount_results(
                    state,
                    changes,
                )
            )

            events = read_events(
                coord.EVENT_LOG
            )

            assert len(events) == 1
            assert (
                events[0]["type"]
                == "bet_amount_observation"
            )
            assert events[0]["bet_bb"] == 6.75
            assert (
                events[0]["source"]
                == "transition"
            )

            assert (
                state[
                    "deferred_bet_amount_results"
                ]
                == {}
            )

            # ========================================================
            # Initial inventory remains immediately publishable.
            # ========================================================

            coord.EVENT_LOG.write_text("")

            initial_id = "initial-request"

            state[
                "pending_bet_amount_requests"
            ][initial_id] = {
                "seat": "seat_lower_left",
                "street": "PREFLOP",
                "frame": "initial.png",
                "source": "initial_inventory",
                "hand_token": "hand-test",
                "queued_ts": 3.0,
            }

            initial_result = {
                "type": "bet_amount_result",
                "request_id": initial_id,
                "hand_token": "hand-test",
                "seat": "seat_lower_left",
                "street": "PREFLOP",
                "frame": "initial.png",
                "ok": True,
                "bet_bb": 1.0,
                "elapsed_ms": 90.0,
                "ts": 4.0,
            }

            state, consumed = (
                coord.apply_bet_amount_result(
                    state,
                    initial_result,
                )
            )

            assert consumed is True

            events = read_events(
                coord.EVENT_LOG
            )

            assert len(events) == 1
            assert events[0]["bet_bb"] == 1.0
            assert (
                events[0]["source"]
                == "initial_inventory"
            )

            # ========================================================
            # No-active-hand result must be rejected.
            # ========================================================

            coord.EVENT_LOG.write_text("")

            stale_id = "stale-request"

            state[
                "pending_bet_amount_requests"
            ][stale_id] = {
                "seat": "seat_mid_right",
                "street": "RIVER",
                "frame": "stale.png",
                "source": "transition",
                "hand_token": "old-hand",
                "queued_ts": 5.0,
            }

            state["hand_token"] = None
            state["phase"] = "WAITING"

            stale_result = {
                "type": "bet_amount_result",
                "request_id": stale_id,
                "hand_token": "old-hand",
                "seat": "seat_mid_right",
                "street": "RIVER",
                "frame": "stale.png",
                "ok": True,
                "bet_bb": 16.8,
                "elapsed_ms": 100.0,
                "ts": 6.0,
            }

            state, consumed = (
                coord.apply_bet_amount_result(
                    state,
                    stale_result,
                )
            )

            assert consumed is False
            assert read_events(
                coord.EVENT_LOG
            ) == []

            print(
                "PASS bet amount evidence gate: "
                "transition reads require positive stack "
                "corroboration; initial inventory is immediate; "
                "inactive-hand results are rejected"
            )

    finally:
        coord.EVENT_LOG = old_event_log


if __name__ == "__main__":
    main()
