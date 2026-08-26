"""
A stack candidate must retain authoritative semantic commitment evidence.

Async worker completion may occur on a later coordinator frame where the
transient commitment tracker no longer reports the seat. Candidate semantics
must not depend on that worker wall-clock timing.
"""

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "hero"


def make_result():
    return {
        "request_id": "request-0102",
        "request": {
            "request_id": "request-0102",
            "seat": SEAT,
            "street": "FLOP",
            "purpose": "settled",
            "hand_token": "hand-1",
            "frame": "/tmp/0102_full.png",
        },
        "result": {
            "type": "stack_result",
            "request_id": "request-0102",
            "hand_token": "hand-1",
            "seat": SEAT,
            "street": "FLOP",
            "frame": "/tmp/0102_full.png",
            "purpose": "settled",
            "ok": True,
            "reading": {
                "raw": [
                    {
                        "variant": "green",
                        "raw": "6.9BB",
                        "stack_bb": 6.9,
                    },
                    {
                        "variant": "plain",
                        "raw": "c 6.9 BB",
                        "stack_bb": 6.9,
                    },
                    {
                        "variant": "psm13_t130",
                        "raw": "69BB",
                        "stack_bb": 69.0,
                    },
                ],
                "stack_bb": 6.9,
                "stack_text": "6.9 BB",
                "confidence": 0.5,
                "votes": 1,
                "mode": "segmentation_disagreement",
            },
            "independent": {
                "stack_bb": 69.0,
                "stack_text": "69 BB",
                "confidence": 0.98,
                "votes": 5,
                "mode": "independent_segmentation",
                "raw": [],
            },
        },
    }


def main():
    old_canonical = c._canonical_stack_values

    try:
        c._canonical_stack_values = (
            lambda: {
                SEAT: 10.28,
            }
        )

        state = c.fresh_state()
        state["hand_token"] = "hand-1"
        state["phase"] = "FLOP"

        # The candidate has already observed authoritative semantic
        # commitment evidence while FLOP is current.
        state["pending_stack_reads"] = {
            SEAT: {
                "first_change_ts": 100.0,
                "last_change_ts": 100.0,
                "origin_street": "FLOP",
                "trigger_sources": [
                    "stack_motion",
                ],
                "stack_worker_request_id": "request-0102",
                "last_stack_sample_ts": 101.0,
                "hand_token": "hand-1",

                # REQUIRED durable candidate semantic.
                #
                # Production does not consume this yet. This test should
                # therefore be RED until candidate-owned semantic commitment
                # is implemented.
                "semantic_commitment_confirmed": True,
            }
        }

        changes = ChangeSet()

        # Simulate delayed worker reconciliation on a frame where transient
        # commitment_tracker state no longer contains Hero.
        c.process_stack_change_measurements_async(
            changes,
            None,
            state,
            stack_worker_results={
                SEAT: make_result(),
            },
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            response_to_aggression_seats=set(),
            event_street="FLOP",
            frame_path="/tmp/0102_full.png",
            frame_ts=101.0,
        )

        print(
            "settled seats:",
            changes.stack_changed_seats,
        )
        print(
            "details:",
            changes.stack_change_details,
        )
        print(
            "candidate alive:",
            SEAT in state["pending_stack_reads"],
        )

        assert SEAT in changes.stack_changed_seats, (
            "RED: candidate-owned semantic commitment was lost "
            "when transient reconciliation-frame commitment was empty"
        )

        detail = changes.stack_change_details[SEAT]

        assert detail["previous_stack_bb"] == 10.28, detail
        assert detail["current_stack_bb"] == 6.9, detail

        assert SEAT not in state["pending_stack_reads"], (
            "validated candidate should close"
        )

        print(
            "PASS candidate semantic commitment survives "
            "asynchronous reconciliation timing"
        )

    finally:
        c._canonical_stack_values = old_canonical


if __name__ == "__main__":
    main()
