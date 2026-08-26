from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


# Use a real geometry seat so the production stack-region gate is
# exercised. Numeric values and timestamps remain entirely synthetic.
SEAT = "seat_lower_left"
BASELINE = 100.0
CHANGED = 95.0

# Recorded semantic time. These are deliberately synthetic.
FRAME_TS = {
    1: 1000.00,
    2: 1000.25,
    3: 1000.50,
    4: 1000.75,
    5: 1001.00,
    6: 1001.25,
    7: 1001.50,
    8: 1001.75,
}

REPLAY_RECORDS = [
    {
        "index": frame,
        "ts": ts,
        "frame_path": Path(
            f"/tmp/{frame:04d}_full.png"
        ),
    }
    for frame, ts in FRAME_TS.items()
]


def read_jsonl(path):
    if not path.exists():
        return []

    result = []

    for raw in path.read_text().splitlines():
        if not raw.strip():
            continue
        result.append(json.loads(raw))

    return result


def value_for_request(request):
    frame = int(
        Path(request["frame"]).stem.split("_")[0]
    )

    # The physical stack transition becomes visible only in
    # later prerecorded evidence.
    if frame >= 6:
        return CHANGED

    return BASELINE


def make_result(request):
    value = value_for_request(request)

    return {
        "type": "stack_result",
        "request_id": request["request_id"],
        "hand_token": "synthetic-hand",
        "seat": SEAT,
        "street": "FLOP",
        "frame": request["frame"],
        "purpose": "settled",
        "ok": True,
        "reading": {
            "stack_bb": value,
            "stack_text": f"{value:g} BB",
            "confidence": 0.99,
            "votes": 3,
            "mode": "agreement_verified",
            "raw": [
                {
                    "stack_bb": value,
                    "confidence": 0.99,
                }
            ],
        },
        "independent": {
            "stack_bb": value,
            "stack_text": f"{value:g} BB",
            "confidence": 0.99,
            "votes": 5,
            "mode": "independent_segmentation",
            "raw": [],
        },
    }


def run_schedule(write_delay_cycles):
    """
    Exercise the NORMAL production ownership path:

        queue request
        -> worker result appears in STACK_RESULTS
        -> collect_ready_stack_worker_results()
        -> process_stack_change_measurements_async()
        -> semantic retry scheduling

    The only variable is when wall-clock worker completion becomes
    durable in STACK_RESULTS.

    Required deterministic replay invariant:
    that wall-clock variation may not alter which prerecorded stack
    samples are ultimately requested.
    """

    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        old_requests = c.STACK_REQUESTS
        old_results = c.STACK_RESULTS

        emitted = []

        try:
            c.STACK_REQUESTS = (
                root / "stack_requests.jsonl"
            )
            c.STACK_RESULTS = (
                root / "stack_results.jsonl"
            )

            state = c.fresh_state()
            state["hand_token"] = "synthetic-hand"
            state["phase"] = "FLOP"

            # Candidate begins from genuine physical commitment
            # evidence before its numeric stack value changes.
            state["pending_stack_reads"] = {
                SEAT: {
                    "first_change_ts": FRAME_TS[1],
                    "last_change_ts": FRAME_TS[1],
                    "max_mean_diff": 5.0,
                    "origin_street": "FLOP",
                    "trigger_sources": [
                        "bet_region_appeared",
                    ],
                }
            }

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            seen_requests = set()

            # request_id -> {
            #     result,
            #     write_cycle,
            # }
            scheduled_results = {}

            for cycle in range(1, 9):
                frame_ts = FRAME_TS[cycle]
                frame_path = (
                    f"/tmp/{cycle:04d}_full.png"
                )

                # ------------------------------------------------
                # Simulate the real asynchronous worker transport.
                #
                # The result is NOT injected into reconciliation.
                # It first becomes durable in STACK_RESULTS.
                # ------------------------------------------------
                for request_id, item in list(
                    scheduled_results.items()
                ):
                    if cycle < item["write_cycle"]:
                        continue

                    c.append_jsonl(
                        c.STACK_RESULTS,
                        item["result"],
                    )

                    del scheduled_results[request_id]

                # ------------------------------------------------
                # NORMAL PRODUCTION ORDER:
                # collector first...
                # ------------------------------------------------
                ready = c.collect_ready_stack_worker_results(
                    state,
                    replay_frame_ts=frame_ts,
                    replay_records=REPLAY_RECORDS,
                )

                settled = {
                    seat: item
                    for seat, item in ready.items()
                    if (
                        (item.get("request") or {}).get(
                            "purpose"
                        )
                        == "settled"
                    )
                }

                # ...then reconciliation.
                changes = ChangeSet()

                with patch.object(
                    c,
                    "_canonical_stack_values",
                    return_value={
                        SEAT: BASELINE,
                    },
                ), patch.object(
                    c,
                    "emit",
                    side_effect=lambda event: emitted.append(
                        dict(event)
                    ),
                ):
                    c.process_stack_change_measurements_async(
                        changes,
                        img,
                        state,
                        stack_worker_results=settled,
                        prior_occupied_bet_regions={
                            SEAT,
                        },
                        event_street="FLOP",
                        frame_path=frame_path,
                        frame_ts=frame_ts,
                        replay_records=REPLAY_RECORDS,
                    )

                # ------------------------------------------------
                # Observe newly queued transport work and assign
                # only its wall-clock completion schedule.
                # ------------------------------------------------
                requests = read_jsonl(
                    c.STACK_REQUESTS
                )

                for request in requests:
                    request_id = request["request_id"]

                    if request_id in seen_requests:
                        continue

                    seen_requests.add(request_id)

                    scheduled_results[request_id] = {
                        "result": make_result(request),
                        "write_cycle": (
                            cycle + write_delay_cycles
                        ),
                    }

            # ------------------------------------------------
            # PRODUCTION EOF TRANSPORT DRAIN
            #
            # Perception is now frozen. Continue only finite
            # asynchronous transport/reconciliation work exactly
            # as production replay does.
            # ------------------------------------------------
            eof_cycle = 8
            eof_guard = 0

            final_record = REPLAY_RECORDS[-1]

            while True:
                eof_guard += 1

                if eof_guard > 100:
                    raise AssertionError(
                        "HARNESS INVALID: EOF drain did not converge"
                    )

                # Advance synthetic wall-clock transport only.
                eof_cycle += 1

                for request_id, item in list(
                    scheduled_results.items()
                ):
                    if eof_cycle < item["write_cycle"]:
                        continue

                    c.append_jsonl(
                        c.STACK_RESULTS,
                        item["result"],
                    )

                    del scheduled_results[request_id]

                with patch.object(
                    c,
                    "_canonical_stack_values",
                    return_value={
                        SEAT: BASELINE,
                    },
                ), patch.object(
                    c,
                    "emit",
                    side_effect=lambda event: emitted.append(
                        dict(event)
                    ),
                ), patch.object(
                    c.cv2,
                    "imread",
                    return_value=np.zeros(
                        (696, 934, 3),
                        dtype=np.uint8,
                    ),
                ):
                    state, _, _ = (
                        c.drain_replay_stack_candidates_once(
                            state,
                            final_frame_path=(
                                final_record["frame_path"]
                            ),
                            final_frame_ts=(
                                final_record["ts"]
                            ),
                            replay_records=REPLAY_RECORDS,
                        )
                    )

                # Discover requests created by the real EOF drain
                # and assign only their asynchronous completion
                # schedule. Do not inject results directly.
                requests = read_jsonl(
                    c.STACK_REQUESTS
                )

                for request in requests:
                    request_id = request["request_id"]

                    if request_id in seen_requests:
                        continue

                    seen_requests.add(request_id)

                    scheduled_results[request_id] = {
                        "result": make_result(request),
                        "write_cycle": (
                            eof_cycle + write_delay_cycles
                        ),
                    }

                outstanding_transport = bool(
                    state.get(
                        "pending_stack_worker_requests"
                    )
                    or {}
                )

                pending_candidates = bool(
                    c.replay_pending_stack_candidates(
                        state
                    )
                )

                if (
                    not outstanding_transport
                    and not pending_candidates
                    and not scheduled_results
                ):
                    break

            request_frames = [
                Path(item["frame"]).name
                for item in read_jsonl(
                    c.STACK_REQUESTS
                )
            ]

            stack_updates = [
                item
                for item in emitted
                if (
                    item.get("type")
                    == "stack_update"
                    and item.get("seat") == SEAT
                )
            ]

            return {
                "request_frames": request_frames,
                "stack_updates": stack_updates,
                "candidate_alive": (
                    SEAT
                    in (
                        state.get(
                            "pending_stack_reads"
                        )
                        or {}
                    )
                ),
                "pending_transport": list(
                    (
                        state.get(
                            "pending_stack_worker_requests"
                        )
                        or {}
                    ).keys()
                ),
                "scheduled_transport": sorted(
                    scheduled_results.keys()
                ),
                "eof_cycles": eof_guard,
            }

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


def main():
    # Fast and slow differ ONLY in when the asynchronous worker
    # result becomes durable. Recorded frames/timestamps and OCR
    # answers are identical.
    fast = run_schedule(
        write_delay_cycles=1,
    )

    slow = run_schedule(
        write_delay_cycles=3,
    )

    print("FAST:")
    print(
        json.dumps(
            fast,
            indent=2,
            sort_keys=True,
        )
    )

    print()
    print("SLOW:")
    print(
        json.dumps(
            slow,
            indent=2,
            sort_keys=True,
        )
    )

    # --------------------------------------------------------
    # HARNESS VALIDITY
    #
    # Never allow an empty transport schedule to masquerade as
    # determinism. Both schedules must actually exercise production
    # request ownership and result collection.
    # --------------------------------------------------------
    assert fast["request_frames"], (
        "HARNESS INVALID: FAST queued no stack requests"
    )

    assert slow["request_frames"], (
        "HARNESS INVALID: SLOW queued no stack requests"
    )

    # --------------------------------------------------------
    # REQUIRED INVARIANT
    #
    # These assertions are intentionally expected to expose the
    # production collector/ownership race if it still exists.
    # --------------------------------------------------------
    assert (
        fast["request_frames"]
        == slow["request_frames"]
    ), (
        "RED: real collector path allows worker completion "
        "timing to change prerecorded retry sampling: "
        f"fast={fast['request_frames']} "
        f"slow={slow['request_frames']}"
    )

    assert (
        fast["stack_updates"]
        == slow["stack_updates"]
    ), (
        "RED: real collector path allows worker completion "
        "timing to change semantic stack transitions"
    )

    print(
        "PASS: real collector replay retry schedule is "
        "independent of asynchronous worker completion"
    )


if __name__ == "__main__":
    main()
