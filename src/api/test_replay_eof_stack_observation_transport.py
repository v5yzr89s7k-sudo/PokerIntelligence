from unittest.mock import patch

from src.api import api_event_coordinator as c


SEAT = "seat_lower_right"


def main():
    """
    Contract:

    A validated settled-stack transition produced during replay EOF
    drain must remain available for semantic observation transport.

    The EOF drain may not terminate the quantitative path at:

        stack_update
        stack_candidate_closed

    while silently discarding the corresponding ChangeSet
    stack_changed_* payload needed by:

        ContinuousObserver
        -> STACK_CHANGED
        -> ActionEpisodeManager
        -> inference
    """

    state = c.fresh_state()

    state["hand_token"] = "gate-2g-hand"
    state["phase"] = "PREFLOP"

    state["pending_stack_reads"] = {
        SEAT: {
            "hand_token": "gate-2g-hand",
            "origin_street": "PREFLOP",
            "trigger_sources": [
                "bet_region_appeared",
                "stack_motion",
            ],
            "stack_worker_request_id": "btn-request",
            "last_stack_sample_ts": 10.0,
            "ocr_attempts": 1,
        }
    }

    state["pending_stack_worker_requests"] = {
        "btn-request": {
            "seat": SEAT,
            "street": "PREFLOP",
            "frame": "/tmp/0052_full.png",
            "purpose": "settled",
            "hand_token": "gate-2g-hand",
            "queued_ts": 10.0,
        }
    }

    ready = {
        SEAT: {
            "request_id": "btn-request",
            "request": {
                "seat": SEAT,
                "street": "PREFLOP",
                "frame": "/tmp/0052_full.png",
                "purpose": "settled",
                "hand_token": "gate-2g-hand",
            },
            "result": {
                "request_id": "btn-request",
                "hand_token": "gate-2g-hand",
                "seat": SEAT,
                "street": "PREFLOP",
                "purpose": "settled",
                "ok": True,
                "reading": {
                    "stack_bb": 56.55,
                    "stack_text": "56.55 BB",
                    "confidence": 0.95,
                    "votes": 2,
                    "mode": "agreement_verified",
                    "raw": [],
                },
                "independent": {
                    "stack_bb": 56.55,
                    "stack_text": "56.55 BB",
                    "confidence": 0.98,
                    "votes": 5,
                    "mode": "independent_segmentation",
                    "raw": [],
                },
            },
        }
    }

    captured = {}

    def fake_process(
        changes,
        img,
        coordinator_state,
        **kwargs,
    ):
        changes.stack_changed_seats = [
            SEAT
        ]

        changes.stack_change_details = {
            SEAT: {
                "previous_stack_bb": 58.55,
                "current_stack_bb": 56.55,
                "delta_bb": 2.0,
                "origin_street": "PREFLOP",
                "stack_read_confidence": 0.95,
                "stack_read_mode": "continuity",
            }
        }

        captured["changes"] = changes

        coordinator_state[
            "pending_stack_reads"
        ] = {}

        coordinator_state[
            "pending_stack_worker_requests"
        ] = {}

        return changes

    fake_image = __import__("numpy").zeros(
        (696, 934, 3),
        dtype="uint8",
    )

    with patch.object(
        c,
        "collect_ready_stack_worker_results",
        return_value=ready,
    ), patch.object(
        c.cv2,
        "imread",
        return_value=fake_image,
    ), patch.object(
        c,
        "process_stack_change_measurements_async",
        side_effect=fake_process,
    ):
        result = (
            c.drain_replay_stack_candidates_once(
                state,
                final_frame_path="/tmp/0052_full.png",
                final_frame_ts=20.0,
                replay_records=[
                    {
                        "frame_path": "/tmp/0052_full.png",
                        "ts": 20.0,
                    }
                ],
            )
        )

    print(
        "drain return:",
        result,
    )

    changes = captured.get("changes")

    assert changes is not None

    print(
        "produced stack_changed_seats:",
        changes.stack_changed_seats,
    )

    print(
        "produced stack_change_details:",
        changes.stack_change_details,
    )

    # Current API returns only:
    #
    #     (state, progressed)
    #
    # Therefore the semantic ChangeSet produced above has no caller-visible
    # ownership after drain_replay_stack_candidates_once returns.
    #
    # This is the exact Replay July 22 BTN failure:
    #
    #     58.55 -> 56.55
    #     stack_update emitted
    #     candidate closed
    #     STACK_CHANGED observation absent
    #
    # Require the drain boundary to return semantic changes as a third value.
    assert (
        isinstance(result, tuple)
        and len(result) == 3
    ), (
        "REPRODUCED: replay EOF drain validated "
        "BTN stack transition but discarded its "
        "semantic ChangeSet before observer ingestion"
    )

    returned_state, progressed, semantic_changes = result

    assert returned_state is state
    assert progressed is True

    assert semantic_changes is changes

    assert semantic_changes.stack_changed_seats == [
        SEAT
    ]

    detail = (
        semantic_changes
        .stack_change_details[
            SEAT
        ]
    )

    assert detail["previous_stack_bb"] == 58.55
    assert detail["current_stack_bb"] == 56.55
    assert detail["delta_bb"] == 2.0
    assert detail["origin_street"] == "PREFLOP"

    print(
        "PASS replay EOF stack observation transport: "
        "validated quantitative ChangeSet remains "
        "caller-owned for semantic ingestion"
    )


if __name__ == "__main__":
    main()
