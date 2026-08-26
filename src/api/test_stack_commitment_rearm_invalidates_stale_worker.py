"""
RED structural contract.

Fresh commitment evidence is a newer semantic epoch than any stack
worker queued before that commitment became visible.

If a pre-commitment worker is still in flight when the candidate is
rearmed, its result must not continue the old retry-frame lineage.

Production must explicitly record or invalidate worker ownership at
fresh_commitment_evidence so the next sample starts from the newer
commitment-era evidence.
"""

from pathlib import Path


def main():
    source = Path(
        "src/api/api_event_coordinator.py"
    ).read_text()

    start = source.index(
        "fresh_commitment_evidence = bool("
    )

    region = source[
        start:
        start + 2600
    ]

    print(
        "===== FRESH COMMITMENT REARM REGION ====="
    )
    print(region)

    assert (
        'entry["unchanged_stack_reads"] = 0'
        in region
    ), (
        "baseline rearm counter reset missing"
    )

    assert (
        'entry.pop('
        in region
        and '"retry_frame_path"' in region
        and '"retry_frame_ts"' in region
    ), (
        "baseline retry-frame reset missing"
    )

    # Missing Gate 6Y requirement:
    #
    # The worker that was queued before fresh commitment must also
    # lose semantic authority. Merely clearing retry_frame_path does
    # not help if stack_worker_request_id still points at an older
    # frame and its eventual result drives the next retry.
    assert (
        'entry["sampling_floor_ts"] = now'
        in region
    ), (
        "RED: fresh commitment does not establish "
        "a new semantic sampling floor"
    )

    assert (
        'entry["sampling_floor_frame_path"] = str('
        in region
        and "frame_path" in region
    ), (
        "RED: fresh commitment does not retain "
        "the commitment-era frame floor"
    )

    print()
    print(
        "PASS: fresh commitment establishes a new "
        "stack-worker sampling epoch"
    )


if __name__ == "__main__":
    main()
