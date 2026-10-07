"""
Regression for the 2026-10-07 live certification crash.

A single physical frame may arrive after the table has already
run from zero board cards to five. The production transaction layer
must expand that observation into strict FLOP/TURN/RIVER physical
boundaries instead of passing board_count=5 into a FLOP boundary.
"""

from src.v017.run_live_observer import (
    expand_physical_board_boundaries,
)


def main():
    events = expand_physical_board_boundaries(
        previous_board_count=0,
        current_board_count=5,
        frame_id=248,
    )

    observed = [
        (
            event["type"],
            event["board_count"],
            event["frame"],
        )
        for event in events
    ]

    expected = [
        (
            "FLOP_BOUNDARY_PHYSICAL",
            3,
            248,
        ),
        (
            "TURN_BOUNDARY_PHYSICAL",
            4,
            248,
        ),
        (
            "RIVER_BOUNDARY_PHYSICAL",
            5,
            248,
        ),
    ]

    print("observed =", observed)
    print("expected =", expected)

    assert observed == expected, (
        "physical 0 -> 5 board jump was not expanded "
        "into strict chronological street boundaries"
    )

    # Normal one-street progression must remain unchanged.
    assert [
        (
            event["type"],
            event["board_count"],
        )
        for event in expand_physical_board_boundaries(
            previous_board_count=0,
            current_board_count=3,
            frame_id=10,
        )
    ] == [
        ("FLOP_BOUNDARY_PHYSICAL", 3)
    ]

    assert [
        (
            event["type"],
            event["board_count"],
        )
        for event in expand_physical_board_boundaries(
            previous_board_count=3,
            current_board_count=4,
            frame_id=20,
        )
    ] == [
        ("TURN_BOUNDARY_PHYSICAL", 4)
    ]

    assert [
        (
            event["type"],
            event["board_count"],
        )
        for event in expand_physical_board_boundaries(
            previous_board_count=4,
            current_board_count=5,
            frame_id=30,
        )
    ] == [
        ("RIVER_BOUNDARY_PHYSICAL", 5)
    ]

    print(
        "V0.17 LIVE PHYSICAL BOARD JUMP EXPANSION: PASS"
    )


if __name__ == "__main__":
    main()
