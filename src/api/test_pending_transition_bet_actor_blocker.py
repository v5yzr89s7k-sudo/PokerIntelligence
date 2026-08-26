import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import src.api.api_event_coordinator as coordinator


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        event_log = root / "api_events.jsonl"

        original_event_log = coordinator.EVENT_LOG

        try:
            coordinator.EVENT_LOG = event_log

            state = coordinator.fresh_state()

            state["phase"] = "PREFLOP"
            state["hand_token"] = "hand-test"
            state["terminal_action_frozen"] = False

            # BTN has already produced transition evidence and its
            # asynchronous bet-amount read is in flight.
            #
            # The worker result has NOT returned yet, so there is no
            # deferred_bet_amount_result and no provisional_bet_opened
            # lifecycle event yet.
            state["pending_bet_amount_requests"] = {
                "btn-request": {
                    "request_id": "btn-request",
                    "hand_token": "hand-test",
                    "seat": "btn",
                    "street": "PREFLOP",
                    "source": "transition",
                    "frame": "frame-1.png",
                }
            }

            state["deferred_bet_amount_results"] = {}

            # A later actor now becomes physically visible.
            #
            # There is no same-frame stack motion for BTN on this later
            # frame. The only surviving commitment ownership is the
            # in-flight transition request above.
            changes = SimpleNamespace(
                bet_region_appeared=["hero"],
                stack_changed_seats=[],
            )

            coordinator.emit_fast_actor_observations(
                state,
                changes,
                street="PREFLOP",
            )

            events = []

            if event_log.exists():
                for raw in event_log.read_text().splitlines():
                    if raw.strip():
                        events.append(json.loads(raw))

            print(
                json.dumps(
                    events,
                    indent=2,
                    sort_keys=True,
                )
            )

            actor_events = [
                event
                for event in events
                if (
                    event.get("type") == "actor_observed"
                    and event.get("seat") == "hero"
                    and event.get("street") == "PREFLOP"
                )
            ]

            assert len(actor_events) == 1

            blockers = set(
                actor_events[0].get("blocked_seats")
                or []
            )

            print()
            print("Hero actor blockers:", sorted(blockers))

            assert "btn" in blockers, (
                "REGRESSION REPRODUCED: BTN has an in-flight "
                "same-hand/same-street transition bet request, but "
                "the later Hero actor_observed event does not carry "
                "BTN as a chronology blocker. This permits the state "
                "machine to manufacture a passive PREFLOP fold before "
                "the asynchronous quantitative result arrives."
            )

            print()
            print(
                "PASS: in-flight transition bet transport "
                "blocks later actor chronology"
            )

        finally:
            coordinator.EVENT_LOG = original_event_log


if __name__ == "__main__":
    main()
