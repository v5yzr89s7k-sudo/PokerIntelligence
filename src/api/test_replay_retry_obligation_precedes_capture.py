"""
Replay invariant:

When a settled-stack result is reconciled before capture and produces another
deterministic retry obligation, that retry must become transport ownership
before the eligible recorded frame can enter perception.

This specifically models the observed Replay 0002 Hero RIVER tail:

    0136 result -> unchanged/retrying
    0137 too early
    0138 first eligible retry frame

Worker wall-clock completion must not decide whether 0138 is requested.
"""

from pathlib import Path

from src.api import api_event_coordinator as c


SEAT = "hero"

TS_0136 = 1784748168.001245
TS_0137 = 1784748168.3679879
TS_0138 = 1784748168.884898


def main():
    state = c.fresh_state()

    state["hand_token"] = "hand-1"
    state["phase"] = "RIVER"

    # 0136 is already owned by transport and semantic candidate.
    state["pending_stack_worker_requests"] = {
        "request-0136": {
            "seat": SEAT,
            "street": "RIVER",
            "frame": "/tmp/0136_full.png",
            "purpose": "settled",
            "hand_token": "hand-1",
            "queued_ts": 1.0,
        }
    }

    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": TS_0136 - 2.0,
            "last_change_ts": TS_0136 - 2.0,
            "origin_street": "RIVER",
            "trigger_sources": [
                "stack_motion",
            ],
            "stack_worker_request_id": "request-0136",
            "last_stack_sample_ts": TS_0136,
            "hand_token": "hand-1",
        }
    }

    replay_records = [
        {
            "ts": TS_0136,
            "frame_path": "/tmp/0136_full.png",
        },
        {
            "ts": TS_0137,
            "frame_path": "/tmp/0137_full.png",
        },
        {
            "ts": TS_0138,
            "frame_path": "/tmp/0138_full.png",
        },
    ]

    old_release = c._replay_stack_request_release_ts
    old_find = c.find_stack_worker_result
    old_collect = c.collect_ready_stack_worker_results
    old_process = c.process_stack_change_measurements_async
    old_queue = c.queue_stack_worker_request
    old_imread = c.cv2.imread

    queued = []

    try:
        # Existing 0136 result becomes semantically available at 0138.
        c._replay_stack_request_release_ts = (
            lambda state, request_id, request, records:
                TS_0138
                if request_id == "request-0136"
                else None
        )

        result_0136 = {
            "type": "stack_result",
            "request_id": "request-0136",
            "seat": SEAT,
            "street": "RIVER",
            "purpose": "settled",
            "hand_token": "hand-1",
            "ok": True,
        }

        c.find_stack_worker_result = (
            lambda request_id:
                result_0136
                if request_id == "request-0136"
                else None
        )

        c.collect_ready_stack_worker_results = (
            lambda state, **kwargs: {
                SEAT: {
                    "request_id": "request-0136",
                    "request": state[
                        "pending_stack_worker_requests"
                    ]["request-0136"],
                    "result": result_0136,
                }
            }
        )

        # Model normal semantic reconciliation of an unchanged result:
        # old transport is acknowledged, candidate survives, and deterministic
        # retry metadata says 0138 is the next sample.
        def fake_process(
            changes,
            img,
            state,
            *,
            stack_worker_results,
            **kwargs,
        ):
            state[
                "pending_stack_worker_requests"
            ].pop(
                "request-0136",
                None,
            )

            entry = state[
                "pending_stack_reads"
            ][SEAT]

            entry["stack_worker_request_id"] = None
            entry["retry_not_before_ts"] = (
                TS_0136 + 0.45
            )
            entry["retry_frame_path"] = (
                "/tmp/0138_full.png"
            )
            entry["retry_frame_ts"] = TS_0138
            entry["unchanged_stack_reads"] = 1

        c.process_stack_change_measurements_async = (
            fake_process
        )

        def fake_queue(
            state,
            *,
            seat,
            street,
            frame_path,
            purpose,
        ):
            request_id = "request-0138"

            queued.append(
                (
                    seat,
                    street,
                    Path(frame_path).name,
                    purpose,
                )
            )

            state[
                "pending_stack_worker_requests"
            ][request_id] = {
                "seat": seat,
                "street": street,
                "frame": frame_path,
                "purpose": purpose,
                "hand_token": "hand-1",
            }

            return request_id

        c.queue_stack_worker_request = fake_queue

        # The helper only needs a readable current-frame image.
        class FakeImage:
            shape = (696, 934, 3)

        c.cv2.imread = lambda path: FakeImage()

        result = (
            c.reconcile_replay_stack_before_capture(
                state,
                current_frame_ts=TS_0137,
                next_frame_ts=TS_0138,
                replay_records=replay_records,
            )
        )

        print("result:", result)
        print("queued:", queued)
        print(
            "candidate:",
            state["pending_stack_reads"][SEAT],
        )
        print(
            "transport:",
            state["pending_stack_worker_requests"],
        )

        assert queued == [
            (
                SEAT,
                "RIVER",
                "0138_full.png",
                "settled",
            )
        ], (
            "RED: deterministic retry obligation did not become "
            "transport ownership before 0138 capture"
        )

        assert (
            state[
                "pending_stack_reads"
            ][SEAT].get(
                "stack_worker_request_id"
            )
            == "request-0138"
        ), (
            "RED: candidate does not own the deterministic "
            "0138 retry before capture"
        )

        assert (
            "request-0138"
            in state[
                "pending_stack_worker_requests"
            ]
        ), (
            "RED: transport does not own 0138 before capture"
        )

        print(
            "PASS replay retry obligation becomes transport "
            "ownership before eligible frame capture"
        )

    finally:
        c._replay_stack_request_release_ts = old_release
        c.find_stack_worker_result = old_find
        c.collect_ready_stack_worker_results = old_collect
        c.process_stack_change_measurements_async = old_process
        c.queue_stack_worker_request = old_queue
        c.cv2.imread = old_imread


if __name__ == "__main__":
    main()
