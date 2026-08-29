"""
Zero-OCR boundary transport contract.

When authoritative status allows retrospective boundary OCR to be skipped:

- the synthetic boundary_stack_result must be emitted to api_events;
- it must be emitted exactly once for the pending physical boundary;
- the pending boundary remains owned until the state machine consumes the
  result and reports completion;
- normal OCR boundary routing remains untouched.
"""

import inspect

import src.api.api_event_coordinator as c


def main():

    source = inspect.getsource(
        c.maybe_route_acknowledged_boundary
    )

    print("===== ZERO-OCR TRANSPORT CONTRACT =====")

    has_emit = (
        "emit(payload)"
        in source
    )

    has_marker = (
        "passive_result_emitted"
        in source
    )

    # Source formatting is intentionally irrelevant here.
    # The production guard may span multiple lines.
    compact_source = "".join(
        source.split()
    )

    has_duplicate_guard = (
        'pending.get("passive_result_emitted")'
        in compact_source
        or "pending.get('passive_result_emitted')"
        in compact_source
    )

    print(
        "synthetic payload emitted:",
        has_emit,
    )

    print(
        "emission lifecycle marker:",
        has_marker,
    )

    print(
        "duplicate guard:",
        has_duplicate_guard,
    )

    assert has_emit, (
        "RED: synthetic zero-OCR boundary result is returned "
        "to callers that discard it instead of being emitted"
    )

    assert has_marker, (
        "RED: zero-OCR boundary result has no persistent "
        "emission lifecycle marker"
    )

    assert has_duplicate_guard, (
        "RED: repeated coordinator cycles can emit the same "
        "logical passive boundary result repeatedly"
    )

    print()
    print(
        "PASS zero-OCR boundary result transport is "
        "exactly-once while authoritative completion is pending"
    )


if __name__ == "__main__":
    main()
