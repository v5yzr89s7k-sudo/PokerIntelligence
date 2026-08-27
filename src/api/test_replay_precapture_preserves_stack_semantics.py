from pathlib import Path
import tempfile

from src.api import api_event_coordinator as c


SEAT = "seat_lower_left"


def main():
    """
    Contract:

    A settled stack result reconciled before capture is semantic evidence.

    reconcile_replay_stack_before_capture() may consume that result before the
    next recorded perception frame, but the resulting quantitative transition
    must not disappear with its temporary ChangeSet.

    This test is intentionally RED until pre-capture reconciliation exposes
    the validated ChangeSet (or an equivalent durable semantic handoff).
    """

    state = c.fresh_state()

    state["hand_token"] = "hand-1"
    state["phase"] = "FLOP"

    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": 10.0,
            "last_change_ts": 10.0,
            "origin_street": "FLOP",
            "trigger_sources": [
                "stack_motion",
                "bet_region_appeared",
            ],
            "semantic_commitment_confirmed": True,
            "stack_worker_request_id": "request-1",
            "last_stack_sample_ts": 10.0,
            "ocr_attempts": 1,
            "hand_token": "hand-1",
        }
    }

    state["pending_stack_worker_requests"] = {
        "request-1": {
            "seat": SEAT,
            "street": "FLOP",
            "frame": "/tmp/0010_full.png",
            "purpose": "settled",
            "hand_token": "hand-1",
            "queued_ts": 10.0,
        }
    }

    replay_records = [
        {
            "ts": 10.0,
            "frame_path": "/tmp/0010_full.png",
        },
        {
            "ts": 11.0,
            "frame_path": "/tmp/0011_full.png",
        },
    ]

    old_collect = c.collect_ready_stack_worker_results
    old_process = c.process_stack_change_measurements_async
    old_imread = c.cv2.imread

    captured = {}

    class FakeImage:
        shape = (696, 934, 3)

    def fake_collect(
        state_arg,
        *,
        replay_frame_ts=None,
        replay_records=None,
        replay_eof=False,
    ):
        return {
            SEAT: {
                "request_id": "request-1",
                "request": state_arg[
                    "pending_stack_worker_requests"
                ]["request-1"],
                "reading": {
                    "stack_bb": 44.2,
                },
            }
        }

    def fake_process(
        changes,
        img,
        state_arg,
        **kwargs,
    ):
        # Model the semantic output contract of the real stack processor:
        # accepted quantitative evidence is written onto its ChangeSet.
        changes.stack_changed_seats = [SEAT]
        changes.stack_change_details = {
            SEAT: {
                "origin_street": "FLOP",
                "previous_stack_bb": 47.57,
                "current_stack_bb": 44.2,
                "delta_bb": 3.37,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "agreement_verified",
                "stack_text": "44.2 BB",
            }
        }

        captured["changes"] = changes

        state_arg["pending_stack_reads"].pop(
            SEAT,
            None,
        )

    try:
        c.collect_ready_stack_worker_results = fake_collect
        c.process_stack_change_measurements_async = fake_process
        c.cv2.imread = lambda path: FakeImage()

        result = c.reconcile_replay_stack_before_capture(
            state,
            current_frame_ts=10.0,
            next_frame_ts=11.0,
            replay_records=replay_records,
        )

    finally:
        c.collect_ready_stack_worker_results = old_collect
        c.process_stack_change_measurements_async = old_process
        c.cv2.imread = old_imread

    produced = captured.get("changes")

    print("result:", result)
    print(
        "processor produced:",
        getattr(
            produced,
            "stack_changed_seats",
            None,
        ),
    )

    semantic_changes = result.get(
        "semantic_changes"
    )

    print(
        "returned semantic changes:",
        getattr(
            semantic_changes,
            "stack_changed_seats",
            None,
        ),
    )

    assert produced is not None
    assert (
        getattr(
            produced,
            "stack_changed_seats",
            [],
        )
        == [SEAT]
    )

    assert semantic_changes is produced, (
        "RED: replay pre-capture reconciliation validated "
        "quantitative stack semantics into a temporary ChangeSet "
        "but discarded that ChangeSet before observer ingestion"
    )

    assert (
        semantic_changes.stack_change_details[
            SEAT
        ]["delta_bb"]
        == 3.37
    )

    assert (
        semantic_changes.stack_change_details[
            SEAT
        ]["origin_street"]
        == "FLOP"
    ), (
        "RED: pre-capture semantic handoff lost the "
        "quantitative transition's originating street"
    )

    print(
        "PASS replay pre-capture reconciliation preserves "
        "validated stack semantics for downstream ingestion"
    )


if __name__ == "__main__":
    main()
