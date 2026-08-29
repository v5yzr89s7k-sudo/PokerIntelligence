"""
Coordinator routing contract:

After the state-machine cursor acknowledges a physical postflop boundary,
authoritative betting status may explicitly certify that retrospective stack
OCR is unnecessary.

In that case:
- no boundary stack worker request is queued;
- a zero-observation boundary result is returned for normal state-machine
  passive reconciliation;
- PREFLOP / quantitative boundaries continue through the OCR path.
"""

import inspect

import src.api.api_event_coordinator as c


def main():

    source = inspect.getsource(
        c.maybe_route_acknowledged_boundary
    )

    print("===== ROUTING CONTRACT =====")

    has_flag = (
        "boundary_can_skip_stack_ocr"
        in source
    )

    has_fast_log = (
        "BOUNDARY_STACK_OCR_SKIP"
        in source
    )

    has_empty_observations = (
        '"observations": []'
        in source
        or "'observations': []"
        in source
    )

    print(
        "reads authoritative skip flag:",
        has_flag,
    )

    print(
        "has explicit skip telemetry:",
        has_fast_log,
    )

    print(
        "routes zero observations:",
        has_empty_observations,
    )

    assert has_flag, (
        "RED: acknowledged boundary routing ignores the "
        "state-machine zero-OCR authorization"
    )

    assert has_fast_log, (
        "RED: zero-OCR boundary routing has no explicit telemetry"
    )

    assert has_empty_observations, (
        "RED: zero-OCR boundary does not feed the existing "
        "state-machine passive reconciliation path"
    )

    print()
    print(
        "PASS acknowledged clean postflop boundary "
        "bypasses retrospective stack OCR"
    )


if __name__ == "__main__":
    main()
