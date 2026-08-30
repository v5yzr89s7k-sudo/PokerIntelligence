"""
Regression contract:

A trusted unchanged stack read on a candidate with independent commitment
evidence must not destroy the semantic candidate, because the displayed
numeric stack may lag the physical commitment.

But candidate lifetime and OCR polling lifetime are different.

After that trusted unchanged read:

    - the candidate remains alive;
    - no automatic retry deadline/frame remains armed;
    - a later quiet coordinator cycle must queue no additional stack OCR.

Fresh physical commitment evidence must be able to re-arm quantitative
sampling for the existing candidate.

This is the evidence-driven replacement for repeated level-triggered OCR.
"""

from types import SimpleNamespace
from unittest.mock import patch

import src.api.api_event_coordinator as c


SEAT = "seat_upper_left"
STREET = "FLOP"
STACK = 59.08
REQUEST_ID = "trusted-unchanged-request"


def changes(*, appeared=False):
    return SimpleNamespace(
        stack_changed_seats=[],
        stack_change_details={},
        ui_activity_seats=[],
        bet_region_appeared=(
            [SEAT]
            if appeared
            else []
        ),
        bet_region_cleared=[],
        bet_region_occupancy={},
        bet_region_transitions={},
    )


def trusted_unchanged_worker_item():
    return {
        "request_id": REQUEST_ID,
        "request": {
            "request_id": REQUEST_ID,
            "hand_token": "polling-disarm-test",
            "seat": SEAT,
            "street": STREET,
            "purpose": "settled",
        },
        "result": {
            "request_id": REQUEST_ID,
            "hand_token": "polling-disarm-test",
            "seat": SEAT,
            "street": STREET,
            "purpose": "settled",
            "ok": True,
            "reading": {
                "stack_bb": STACK,
                "stack_text": f"{STACK:g} BB",
                "confidence": 0.98,
                "votes": 2,
                "mode": "agreement",
                "raw": [
                    {"stack_bb": STACK},
                    {"stack_bb": STACK},
                ],
            },
            "independent": {},
        },
    }


def process(
    state,
    frame_ts,
    *,
    appeared=False,
    worker_results=None,
    queued=None,
):
    if queued is None:
        queued = []

    def fake_queue(
        queue_state,
        *,
        seat,
        street,
        frame_path,
        purpose,
    ):
        request_id = (
            f"request-{len(queued) + 1}"
        )

        queued.append(
            (
                seat,
                street,
                frame_path,
                purpose,
            )
        )

        queue_state.setdefault(
            "pending_stack_worker_requests",
            {},
        )[request_id] = {
            "seat": seat,
            "street": street,
            "frame": frame_path,
            "purpose": purpose,
            "hand_token": queue_state.get(
                "hand_token"
            ),
        }

        return request_id

    with patch.object(
        c,
        "_canonical_stack_values",
        return_value={SEAT: STACK},
    ), patch.object(
        c,
        "queue_stack_worker_request",
        side_effect=fake_queue,
    ), patch.object(
        c,
        "emit",
    ):
        c.enrich_stack_change_measurements(
            changes(appeared=appeared),
            img=None,
            state=state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            response_to_aggression_seats=set(),
            event_street=STREET,
            old_street_owing_seats=set(),
            frame_path=(
                f"/tmp/{int(frame_ts):04d}_full.png"
            ),
            frame_ts=frame_ts,
            stack_worker_results=(
                worker_results or {}
            ),
            queue_stack_ocr=True,
            replay_records=None,
        )

    return queued


def main():
    state = c.fresh_state()

    state["hand_token"] = "polling-disarm-test"
    state["phase"] = STREET

    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": 100.0,
            "last_change_ts": 100.0,
            "last_stack_sample_ts": 101.0,
            "max_mean_diff": 12.0,
            "origin_street": STREET,
            "trigger_sources": [
                "stack_motion",
                "bet_region_appeared",
            ],
            "stack_worker_request_id": (
                REQUEST_ID
            ),
            "hand_token": state["hand_token"],
        },
    }

    state["pending_stack_worker_requests"] = {}

    print(
        "===== TRUSTED UNCHANGED RESULT ====="
    )

    queued = []

    process(
        state,
        102.0,
        worker_results={
            SEAT: trusted_unchanged_worker_item(),
        },
        queued=queued,
    )

    entry = (
        state.get("pending_stack_reads")
        or {}
    ).get(SEAT)

    print("candidate:", entry)
    print("queued during result:", queued)

    assert entry is not None, (
        "RED: trusted unchanged read destroyed "
        "independently evidenced candidate"
    )

    assert not entry.get(
        "stack_worker_request_id"
    ), (
        "RED: trusted unchanged result immediately "
        "retained worker ownership"
    )

    assert entry.get(
        "retry_not_before_ts"
    ) is None, (
        "RED: trusted unchanged result armed "
        "another retry deadline"
    )

    assert entry.get(
        "retry_frame_path"
    ) is None, (
        "RED: trusted unchanged result selected "
        "another retry frame"
    )

    assert entry.get(
        "retry_frame_ts"
    ) is None, (
        "RED: trusted unchanged result retained "
        "another retry timestamp"
    )

    assert entry.get(
        "trusted_unchanged_polling_disarmed"
    ) is True, (
        "RED: trusted unchanged result did not "
        "explicitly disarm automatic OCR polling"
    )

    print()
    print("===== QUIET SUBSEQUENT CYCLE =====")

    queued.clear()

    process(
        state,
        103.0,
        queued=queued,
    )

    entry = state["pending_stack_reads"][SEAT]

    print("queued:", queued)
    print("candidate:", entry)

    assert queued == [], (
        "RED: dormant trusted-unchanged candidate "
        "automatically queued another OCR read"
    )

    assert not entry.get(
        "stack_worker_request_id"
    ), (
        "RED: quiet cycle recreated worker ownership "
        "without fresh evidence"
    )

    print()
    print("===== FRESH COMMITMENT EVIDENCE =====")

    queued.clear()

    process(
        state,
        104.0,
        appeared=True,
        queued=queued,
    )

    entry = state["pending_stack_reads"][SEAT]

    print("queued:", queued)
    print("candidate:", entry)

    assert entry.get(
        "trusted_unchanged_polling_disarmed"
    ) is not True, (
        "RED: fresh commitment evidence did not "
        "re-arm dormant quantitative sampling"
    )

    # Rearming establishes a new sampling epoch. The physical
    # edge frame itself must not be OCR'd as the settled sample.
    assert queued == [], (
        "REGRESSION: fresh commitment edge was OCR'd "
        "before a later settled frame existed"
    )

    assert entry.get(
        "sampling_floor_ts"
    ) == 104.0, (
        "RED: fresh commitment evidence did not establish "
        "the new quantitative sampling floor"
    )

    assert entry.get(
        "sampling_floor_frame_path"
    ) == "/tmp/0104_full.png", (
        "RED: fresh commitment evidence did not preserve "
        "the physical edge frame as the sampling floor"
    )

    print()
    print("===== LATER SETTLED FRAME =====")

    queued.clear()

    process(
        state,
        105.0,
        queued=queued,
    )

    entry = state["pending_stack_reads"][SEAT]

    print("queued:", queued)
    print("candidate:", entry)

    assert len(queued) == 1, (
        "RED: re-armed candidate did not queue exactly "
        "one quantitative read on a later settled frame"
    )

    assert queued[0][0] == SEAT
    assert queued[0][1] == STREET
    assert queued[0][3] == "settled"

    assert entry.get(
        "stack_worker_request_id"
    ), (
        "RED: re-armed candidate does not own "
        "the newly queued worker"
    )

    print()
    print(
        "PASS evidence-driven stack polling: "
        "trusted unchanged retains semantic candidate "
        "but disarms OCR; quiet cycles remain dormant; "
        "fresh commitment evidence establishes a new "
        "sampling epoch and exactly one later settled "
        "frame is queued"
    )


if __name__ == "__main__":
    main()
