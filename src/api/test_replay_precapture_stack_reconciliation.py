from pathlib import Path

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_left"

FRAME_TS = {
    50: 1784748140.000,
    51: 1784748140.340,
    52: 1784748140.680,
    53: 1784748141.020,
    54: 1784748141.360,
}

REPLAY_RECORDS = [
    {
        "index": index,
        "ts": ts,
        "frame_path": Path(
            "runtime/debug/action_sequence/"
            "20260722_152155/"
            f"{index:04d}_full.png"
        ),
    }
    for index, ts in FRAME_TS.items()
]


def unchanged_result(request_id):
    return {
        "type": "stack_result",
        "request_id": request_id,
        "hand_token": "hand-1",
        "seat": SEAT,
        "street": "PREFLOP",
        "frame": "/tmp/0050_full.png",
        "purpose": "settled",
        "ok": True,
        "reading": {
            "stack_bb": 48.57,
            "stack_text": "48.57 BB",
            "confidence": 0.98,
            "votes": 3,
            "mode": "agreement_verified",
            "raw": [],
        },
        "independent": {
            "stack_bb": 48.87,
            "stack_text": "48.87 BB",
            "confidence": 0.98,
            "votes": 5,
            "mode": "independent_segmentation",
            "raw": [],
        },
    }


def make_state():
    state = c.fresh_state()

    state["hand_token"] = "hand-1"
    state["phase"] = "PREFLOP"

    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": FRAME_TS[48]
            if 48 in FRAME_TS
            else FRAME_TS[50] - 0.70,
            "last_change_ts": FRAME_TS[50] - 0.70,
            "origin_street": "PREFLOP",
            "trigger_sources": [
                "stack_motion",
            ],
            "stack_worker_request_id": "request-1",
            "last_stack_sample_ts": FRAME_TS[50],
            "retry_not_before_ts": None,
            "retry_count": 0,
            "hand_token": "hand-1",
        },
    }

    state["pending_stack_worker_requests"] = {
        "request-1": {
            "seat": SEAT,
            "street": "PREFLOP",
            "frame": "/tmp/0050_full.png",
            "purpose": "settled",
            "hand_token": "hand-1",
            "queued_ts": 0.0,
        },
    }

    return state


def main():
    state = make_state()

    old_finder = c.find_stack_worker_result

    try:
        c.find_stack_worker_result = (
            lambda request_id: (
                unchanged_result(request_id)
                if request_id == "request-1"
                else None
            )
        )

        # This helper does not exist yet.
        #
        # Required behavior:
        #
        # - current semantic frame is 51
        # - next replay frame 52 reaches/crosses the release boundary
        # - request-1 physically exists
        # - consume and reconcile request-1 BEFORE capture(52)
        # - unchanged validation preserves the candidate
        # - deterministic retry ownership is established
        # - therefore frame 52 is NOT yet eligible for perception
        result = (
            c.reconcile_replay_stack_before_capture(
                state,
                current_frame_ts=FRAME_TS[51],
                next_frame_ts=FRAME_TS[52],
                replay_records=REPLAY_RECORDS,
            )
        )

    finally:
        c.find_stack_worker_result = old_finder

    print("result:", result)

    assert result["advance"] is True, (
        "REPRODUCED: replay remained blocked after "
        "boundary result was reconciled and deterministic "
        "retry ownership was established"
    )

    assert result["reconciled"] is True, (
        "REPRODUCED: boundary-ready stack result "
        "was not reconciled before capture"
    )

    entry = state[
        "pending_stack_reads"
    ][SEAT]

    new_request_id = entry.get(
        "stack_worker_request_id"
    )

    assert new_request_id, entry
    assert new_request_id != "request-1", entry

    assert (
        "request-1"
        not in state[
            "pending_stack_worker_requests"
        ]
    )

    assert (
        new_request_id
        in state[
            "pending_stack_worker_requests"
        ]
    )

    assert (
        entry.get("retry_not_before_ts")
        is None
    ), entry

    assert (
        Path(
            state[
                "pending_stack_worker_requests"
            ][new_request_id]["frame"]
        ).name
        == "0052_full.png"
    ), state[
        "pending_stack_worker_requests"
    ]

    print(
        "PASS pre-capture reconciliation contract: "
        "unchanged boundary-ready result mutates candidate "
        "ownership before the next replay frame can enter perception"
    )


if __name__ == "__main__":
    main()
