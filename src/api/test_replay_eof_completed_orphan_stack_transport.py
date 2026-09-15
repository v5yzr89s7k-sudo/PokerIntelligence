"""
Regression contract:

A completed settled-stack worker request can survive until replay EOF
after its semantic stack candidate has already been legitimately retired.

During live capture and ordinary replay, an ownerless completed result
must remain transport-owned: semantic ownership is required before the
collector may consume it.

At finite replay EOF there is no future semantic owner or perception
frame that can acknowledge that result. The completed request must
therefore be retired from transport WITHOUT:

    - exposing it as a ready semantic stack result,
    - reopening a stack candidate,
    - emitting a quantitative transition,
    - changing canonical state.

This reproduces the shutdown hang where every stack request had a
physical result but completed ownerless requests remained forever in
pending_stack_worker_requests.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_coordinator as c


REQUEST_ID = "completed-orphan-request"
SEAT = "hero"
HAND_TOKEN = "synthetic-hand"


def result_row():
    return {
        "type": "stack_result",
        "request_id": REQUEST_ID,
        "hand_token": HAND_TOKEN,
        "seat": SEAT,
        "street": "WAITING",
        "frame": "/tmp/4336_full.png",
        "purpose": "settled",
        "ok": True,
        "reading": {
            "stack_bb": 10.0,
            "stack_text": "10 BB",
            "confidence": 0.99,
            "votes": 5,
            "mode": "test",
            "raw": [],
        },
        "independent": {
            "stack_bb": 10.0,
            "stack_text": "10 BB",
            "confidence": 0.99,
            "votes": 5,
            "mode": "test",
            "raw": [],
        },
        "elapsed_ms": 1.0,
    }


def make_state():
    state = c.fresh_state()
    state["hand_token"] = HAND_TOKEN

    state["pending_stack_worker_requests"] = {
        REQUEST_ID: {
            "seat": SEAT,
            "street": "WAITING",
            "frame": "/tmp/4336_full.png",
            "purpose": "settled",
            "hand_token": HAND_TOKEN,
            "queued_ts": 1.0,
        }
    }

    # Critical production condition:
    #
    # The asynchronous transport request still exists, but its semantic
    # candidate has already closed. Therefore no entry owns REQUEST_ID.
    state["pending_stack_reads"] = {}

    return state


def main():
    with TemporaryDirectory() as tmp:
        old_results = c.STACK_RESULTS

        try:
            c.STACK_RESULTS = (
                Path(tmp) / "stack_results.jsonl"
            )

            c.append_jsonl(
                c.STACK_RESULTS,
                result_row(),
            )

            # ---------------------------------------------------------
            # CONTROL: ordinary replay/live behavior must NOT consume
            # an ownerless settled result.
            # ---------------------------------------------------------
            normal_state = make_state()

            normal_ready = (
                c.collect_ready_stack_worker_results(
                    normal_state,
                )
            )

            assert normal_ready == {}, normal_ready

            assert (
                REQUEST_ID
                in normal_state[
                    "pending_stack_worker_requests"
                ]
            ), (
                "REGRESSION: ordinary collector retired "
                "ownerless settled transport"
            )

            # ---------------------------------------------------------
            # TARGET: finite replay EOF must retire only the completed
            # transport envelope. It must NOT expose semantic evidence.
            # ---------------------------------------------------------
            eof_state = make_state()

            eof_ready = (
                c.collect_ready_stack_worker_results(
                    eof_state,
                    replay_frame_ts=100.0,
                    replay_records=[
                        {
                            "ts": 100.0,
                            "frame_path": "/tmp/4336_full.png",
                        }
                    ],
                    replay_eof=True,
                )
            )

            assert eof_ready == {}, (
                "EOF orphan result was incorrectly exposed "
                f"as semantic evidence: {eof_ready}"
            )

            assert (
                REQUEST_ID
                not in eof_state[
                    "pending_stack_worker_requests"
                ]
            ), (
                "RED: completed ownerless settled-stack transport "
                "survives finite replay EOF forever"
            )

            assert (
                eof_state.get("pending_stack_reads")
                or {}
            ) == {}, (
                "EOF orphan retirement manufactured "
                "semantic candidate ownership"
            )

            print(
                "PASS replay EOF completed orphan stack transport: "
                "ordinary replay preserves semantic ownership guard; "
                "finite EOF retires completed ownerless transport only"
            )

        finally:
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
