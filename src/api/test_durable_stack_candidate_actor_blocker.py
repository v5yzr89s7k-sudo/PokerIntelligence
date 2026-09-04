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


def emit_one(state):
    changes = SimpleNamespace(
        bet_region_appeared=["btn"],
        stack_changed_seats=[],
    )

    coord.emit_fast_actor_observations(
        state,
        changes,
        street="FLOP",
    )

    events = read_events(coord.EVENT_LOG)

    assert len(events) == 1

    event = events[0]

    assert event["type"] == "actor_observed"
    assert event["seat"] == "btn"
    assert event["street"] == "FLOP"

    return set(event.get("blocked_seats") or [])


def main():
    old_event_log = coord.EVENT_LOG

    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            coord.EVENT_LOG = (
                root / "api_events.jsonl"
            )

            # ------------------------------------------------
            # Positive case:
            #
            # BB's physical commitment appeared on an earlier
            # frame. There is no same-frame stack motion and no
            # pending/deferred bet transport anymore, but the
            # independently evidenced stack candidate is still
            # unresolved.
            #
            # BTN appearing now must carry BB as a chronology
            # blocker.
            # ------------------------------------------------

            coord.EVENT_LOG.write_text("")

            state = coord.fresh_state()
            state["hand_token"] = "hand-test"
            state["phase"] = "FLOP"

            state["pending_stack_reads"] = {
                "bb": {
                    "first_change_ts": 1.0,
                    "last_change_ts": 1.0,
                    "origin_street": "FLOP",
                    "trigger_sources": [
                        "bet_region_appeared",
                    ],
                }
            }

            blockers = emit_one(state)

            print(
                "durable physical blockers:",
                sorted(blockers),
            )

            assert "bb" in blockers, (
                "RED: unresolved same-street "
                "bet-region-backed stack candidate "
                "was forgotten between frames"
            )

            # ------------------------------------------------
            # Negative control 1:
            # motion-only candidates are not durable blockers.
            # ------------------------------------------------

            coord.EVENT_LOG.write_text("")

            state["pending_stack_reads"] = {
                "bb": {
                    "first_change_ts": 1.0,
                    "last_change_ts": 1.0,
                    "origin_street": "FLOP",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                }
            }

            blockers = emit_one(state)

            print(
                "motion-only blockers:",
                sorted(blockers),
            )

            assert "bb" not in blockers, (
                "motion-only stack candidate became "
                "an immortal chronology blocker"
            )

            # ------------------------------------------------
            # Negative control 2:
            # another street cannot contaminate FLOP.
            # ------------------------------------------------

            coord.EVENT_LOG.write_text("")

            state["pending_stack_reads"] = {
                "bb": {
                    "first_change_ts": 1.0,
                    "last_change_ts": 1.0,
                    "origin_street": "TURN",
                    "trigger_sources": [
                        "bet_region_appeared",
                    ],
                }
            }

            blockers = emit_one(state)

            print(
                "wrong-street blockers:",
                sorted(blockers),
            )

            assert "bb" not in blockers, (
                "durable candidate from another street "
                "contaminated FLOP chronology"
            )

            # ------------------------------------------------
            # Negative control 3:
            # ordinary empty state remains unchanged.
            # ------------------------------------------------

            coord.EVENT_LOG.write_text("")

            state["pending_stack_reads"] = {}

            blockers = emit_one(state)

            print(
                "empty-state blockers:",
                sorted(blockers),
            )

            assert "bb" not in blockers

            print(
                "PASS durable stack candidate actor blocker: "
                "same-street bet-region-backed unresolved "
                "candidates survive across frames without "
                "promoting motion-only or wrong-street noise"
            )

    finally:
        coord.EVENT_LOG = old_event_log


if __name__ == "__main__":
    main()
