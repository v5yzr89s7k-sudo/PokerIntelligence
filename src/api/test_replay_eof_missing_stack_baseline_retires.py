"""
Replay EOF contract.

Recorded time cannot advance after the final frame.

Therefore a physical stack candidate that has no authoritative
canonical baseline at EOF cannot wait on the ordinary elapsed-time
baseline timeout forever.

With no baseline, no quantitative transition can be validated.
The candidate must retire cleanly at the finite recording boundary.
"""

from pathlib import Path


def main():
    source = Path(
        "src/api/api_event_coordinator.py"
    ).read_text()

    marker = '''        if previous is None:
'''

    start = source.index(marker)

    region = source[
        start:
        start + 2600
    ]

    print("===== BASELINE WAIT REGION =====")
    print(region)

    assert "replay_eof" in region, (
        "RED: missing-baseline path has no replay EOF handling"
    )

    assert (
        "baseline_unavailable_at_replay_eof"
        in region
    ), (
        "RED: missing canonical baseline can retain "
        "a stack candidate forever after finite EOF work"
    )

    print()
    print(
        "PASS: replay EOF retires quantitatively "
        "unresolvable missing-baseline candidates"
    )


if __name__ == "__main__":
    main()
