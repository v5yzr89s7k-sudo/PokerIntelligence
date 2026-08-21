from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_left"   # July 22 BB / Birkam. Hero is always "hero".
BASELINE = 47.57
CHANGED = 44.20
EXPECTED_DELTA = 3.37

# Synthetic recorded timeline preserving the important July 22 shape:
# commitment evidence exists before the displayed stack reaches its final
# post-bet value.
FRAME_TS = {
    90: 1784748174.000,
    91: 1784748174.340,
    92: 1784748174.680,
    93: 1784748175.020,
    94: 1784748175.360,
    95: 1784748175.700,
    96: 1784748176.040,
    97: 1784748176.380,
    98: 1784748176.720,
    99: 1784748177.060,
    100: 1784748177.400,
    101: 1784748177.740,
    102: 1784748178.080,
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


def read_requests():
    if not c.STACK_REQUESTS.exists():
        return []

    return [
        json.loads(line)
        for line in c.STACK_REQUESTS.read_text().splitlines()
        if line.strip()
    ]


def worker_item(request, value):
    return {
        "request_id": request["request_id"],
        "request": dict(request),
        "result": {
            "type": "stack_result",
            "request_id": request["request_id"],
            "hand_token": "july22-bb",
            "seat": SEAT,
            "street": "FLOP",
            "frame": request["frame"],
            "purpose": "settled",
            "ok": True,
            "reading": {
                "stack_bb": value,
                "stack_text": f"{value:g} BB",
                "confidence": 0.98,
                "votes": 3,
                "mode": "agreement_verified",
                "raw": [],
            },
            "independent": {
                "stack_bb": value,
                "stack_text": f"{value:g} BB",
                "confidence": 0.98,
                "votes": 5,
                "mode": "independent_segmentation",
                "raw": [],
            },
        },
    }


def value_for_request(request):
    frame = int(
        Path(request["frame"]).stem.split("_")[0]
    )

    # The actual post-bet stack is not visible until later in the recorded
    # evidence window.
    if frame >= 99:
        return CHANGED

    return BASELINE


def run_schedule(completion_delay_frames):
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
            state["hand_token"] = "july22-bb"
            state["phase"] = "FLOP"

            # Open from independent commitment evidence, matching the real
            # BB action episode.
            state["pending_stack_reads"] = {
                SEAT: {
                    "first_change_ts": FRAME_TS[90],
                    "last_change_ts": FRAME_TS[90],
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

            # Production EOF requires a genuine prerecorded frame path.
            # Materialize only the synthetic test session's final frame;
            # request-frame semantics remain governed by REPLAY_RECORDS.
            final_frame_path = (
                root / "0102_full.png"
            )

            import cv2

            assert cv2.imwrite(
                str(final_frame_path),
                img,
            )

            pending_result = None
            due_frame = None
            seen_request_ids = set()

            # Normal replay perception runs only through the final recorded
            # frame. Any remaining quantitative work after that point must be
            # advanced through the production EOF helper rather than by
            # pretending additional perception frames exist.
            for cycle in range(90, 103):
                frame = cycle

                ready = {}

                if (
                    pending_result is not None
                    and due_frame is not None
                    and cycle >= due_frame
                ):
                    ready = {
                        SEAT: pending_result
                    }
                    pending_result = None
                    due_frame = None

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
                        stack_worker_results=ready,
                        prior_occupied_bet_regions={
                            SEAT,
                        },
                        event_street="FLOP",
                        frame_path=(
                            f"/tmp/{frame:04d}_full.png"
                        ),
                        frame_ts=FRAME_TS[frame],
                        replay_records=REPLAY_RECORDS,
                    )

                rows = read_requests()

                new_requests = [
                    row
                    for row in rows
                    if row["request_id"]
                    not in seen_request_ids
                ]

                for request in new_requests:
                    seen_request_ids.add(
                        request["request_id"]
                    )

                    # Only one request may be outstanding for this seat.
                    assert pending_result is None, (
                        "duplicate outstanding stack request"
                    )

                    pending_result = worker_item(
                        request,
                        value_for_request(request),
                    )

                    due_frame = (
                        cycle
                        + completion_delay_frames
                    )

                # Once the quantitative transition is emitted the test case is
                # complete.
                stack_updates = [
                    event
                    for event in emitted
                    if (
                        event.get("type")
                        == "stack_update"
                        and event.get("seat") == SEAT
                    )
                ]

                if stack_updates:
                    break

                for request in read_requests():
                    request_frame = int(
                        Path(
                            request["frame"]
                        ).stem.split("_")[0]
                    )

                    assert request_frame <= 102, (
                        "normal replay invented a non-recorded "
                        "stack sample"
                    )

            # ------------------------------------------------------------
            # Production EOF drain
            # ------------------------------------------------------------
            #
            # Frame release is now exhausted. Do not run LocalEventDetector or
            # another synthetic perception frame. Complete only finite
            # prerecorded quantitative work through the actual production
            # helper.
            eof_cycle = 103

            while (
                SEAT
                in (
                    state.get("pending_stack_reads")
                    or {}
                )
                and eof_cycle < 130
            ):
                if (
                    pending_result is not None
                    and due_frame is not None
                    and eof_cycle >= due_frame
                ):
                    # The real worker would have written this result to the
                    # durable result transport. Reproduce that exact ownership
                    # contract here so the production collector/helper sees it.
                    c.append_jsonl(
                        c.STACK_RESULTS,
                        pending_result["result"],
                    )

                    pending_result = None
                    due_frame = None

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
                    state, _, _semantic_changes = (
                        c.drain_replay_stack_candidates_once(
                            state,
                            final_frame_path=(
                                final_frame_path
                            ),
                            final_frame_ts=(
                                REPLAY_RECORDS[-1]["ts"]
                            ),
                            replay_records=REPLAY_RECORDS,
                        )
                    )

                rows = read_requests()

                new_requests = [
                    row
                    for row in rows
                    if row["request_id"]
                    not in seen_request_ids
                ]

                for request in new_requests:
                    seen_request_ids.add(
                        request["request_id"]
                    )

                    assert pending_result is None, (
                        "production EOF drain queued duplicate "
                        "outstanding stack work"
                    )

                    pending_result = worker_item(
                        request,
                        value_for_request(request),
                    )

                    due_frame = (
                        eof_cycle
                        + completion_delay_frames
                    )

                for request in read_requests():
                    request_frame = int(
                        Path(
                            request["frame"]
                        ).stem.split("_")[0]
                    )

                    assert request_frame <= 102, (
                        "production EOF drain invented "
                        "a non-recorded stack sample"
                    )

                if any(
                    event.get("type") == "stack_update"
                    and event.get("seat") == SEAT
                    for event in emitted
                ):
                    break

                eof_cycle += 1

            stack_updates = [
                event
                for event in emitted
                if (
                    event.get("type")
                    == "stack_update"
                    and event.get("seat") == SEAT
                )
            ]

            request_frames = [
                Path(row["frame"]).name
                for row in read_requests()
            ]

            return {
                "request_frames": request_frames,
                "stack_updates": stack_updates,
                "candidate_alive": (
                    SEAT
                    in (
                        state.get("pending_stack_reads")
                        or {}
                    )
                ),
            }

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


def main():
    fast = run_schedule(
        completion_delay_frames=1
    )

    slow = run_schedule(
        completion_delay_frames=3
    )

    print(
        "fast request frames:",
        fast["request_frames"],
    )
    print(
        "slow request frames:",
        slow["request_frames"],
    )

    print(
        "fast stack updates:",
        fast["stack_updates"],
    )
    print(
        "slow stack updates:",
        slow["stack_updates"],
    )

    # Required replay invariant:
    #
    # Worker completion speed cannot determine whether the real later
    # quantitative transition is ever sampled.
    assert fast["request_frames"] == slow[
        "request_frames"
    ], (
        "REPRODUCED: multi-retry stack sampling still "
        "depends on asynchronous worker completion"
    )

    assert len(
        fast["stack_updates"]
    ) == 1, (
        "REPRODUCED: fast schedule failed to reach "
        "the eventual 44.20 BB transition"
    )

    assert len(
        slow["stack_updates"]
    ) == 1, (
        "REPRODUCED: slow schedule failed to reach "
        "the eventual 44.20 BB transition"
    )

    for result in (fast, slow):
        update = result["stack_updates"][0]

        assert abs(
            float(update["previous_stack_bb"])
            - BASELINE
        ) < 1e-9

        assert abs(
            float(update["current_stack_bb"])
            - CHANGED
        ) < 1e-9

        assert abs(
            float(update["delta_bb"])
            - EXPECTED_DELTA
        ) < 1e-9

    print(
        "PASS eventual stack transition determinism: "
        "different worker completion schedules sample "
        "the same recorded evidence and emit the same "
        "3.37 BB transition"
    )


if __name__ == "__main__":
    main()
