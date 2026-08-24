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

            coord.EVENT_LOG = (
                root / "api_events.jsonl"
            )

            coord.EVENT_LOG.write_text("")

            state = coord.fresh_state()

            state["hand_token"] = "hand-test"
            state["phase"] = "FLOP"

            # Reproduce the semantic state AFTER BB's absolute
            # transition bet read has completed:
            #
            # - numeric 3.37 BB exists,
            # - it has NOT passed stack corroboration,
            # - therefore it must remain unpublished,
            # - but BB cannot safely be inferred CHECK.
            state[
                "deferred_bet_amount_results"
            ] = {
                "bb-request": {
                    "request": {
                        "request_id": "bb-request",
                        "hand_token": "hand-test",
                        "seat": "bb",
                        "street": "FLOP",
                        "frame": "0091_full.png",
                        "source": "transition",
                    },
                    "result": {
                        "type": "bet_amount_result",
                        "request_id": "bb-request",
                        "hand_token": "hand-test",
                        "seat": "bb",
                        "street": "FLOP",
                        "frame": "0091_full.png",
                        "ok": True,
                        "bet_bb": 3.37,
                    },
                    "bet_bb": 3.37,
                    "seat": "bb",
                    "street": "FLOP",
                }
            }

            # A later BTN bet-region appearance is chronology
            # evidence. There is no same-frame stack motion,
            # so under current production same_frame_blockers
            # is empty.
            changes = SimpleNamespace(
                bet_region_appeared=[
                    "btn",
                ],
                stack_changed_seats=[],
            )

            coord.emit_fast_actor_observations(
                state,
                changes,
                street="FLOP",
            )

            events = read_events(
                coord.EVENT_LOG
            )

            print(
                "events:",
                json.dumps(
                    events,
                    indent=2,
                ),
            )

            assert len(events) == 1

            event = events[0]

            assert event["type"] == "actor_observed"
            assert event["seat"] == "btn"
            assert event["street"] == "FLOP"

            blockers = set(
                event.get("blocked_seats")
                or []
            )

            print(
                "BTN blockers:",
                sorted(blockers),
            )

            assert "bb" in blockers, (
                "REGRESSION REPRODUCED: same-hand/same-street "
                "transition bet evidence for BB is deferred "
                "awaiting stack corroboration, but the later "
                "BTN actor_observed event does not carry BB "
                "as a chronology blocker; downstream may "
                "therefore fabricate BB CHECK"
            )

            # Negative controls: stale-hand and other-street
            # provisional evidence must not contaminate this
            # FLOP actor event.
            coord.EVENT_LOG.write_text("")

            state[
                "deferred_bet_amount_results"
            ] = {
                "old-hand": {
                    "request": {
                        "hand_token": "old-hand",
                        "seat": "old",
                        "street": "FLOP",
                        "source": "transition",
                    },
                    "result": {
                        "hand_token": "old-hand",
                        "seat": "old",
                        "street": "FLOP",
                        "ok": True,
                        "bet_bb": 8.0,
                    },
                    "bet_bb": 8.0,
                    "seat": "old",
                    "street": "FLOP",
                },
                "old-street": {
                    "request": {
                        "hand_token": "hand-test",
                        "seat": "turn-seat",
                        "street": "TURN",
                        "source": "transition",
                    },
                    "result": {
                        "hand_token": "hand-test",
                        "seat": "turn-seat",
                        "street": "TURN",
                        "ok": True,
                        "bet_bb": 4.0,
                    },
                    "bet_bb": 4.0,
                    "seat": "turn-seat",
                    "street": "TURN",
                },
            }

            coord.emit_fast_actor_observations(
                state,
                changes,
                street="FLOP",
            )

            event = read_events(
                coord.EVENT_LOG
            )[0]

            blockers = set(
                event.get("blocked_seats")
                or []
            )

            print(
                "negative-control blockers:",
                sorted(blockers),
            )

            assert "old" not in blockers
            assert "turn-seat" not in blockers

            print(
                "PASS deferred transition bet evidence "
                "is transported as a conservative "
                "same-hand/same-street actor blocker"
            )

    finally:
        coord.EVENT_LOG = old_event_log


if __name__ == "__main__":
    main()
