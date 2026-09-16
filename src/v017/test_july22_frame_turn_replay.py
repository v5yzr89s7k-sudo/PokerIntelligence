import tempfile

from src.v017.july22_frame_preflop_replay import (
    replay,
)


EXPECTED = [
    ("POST_SMALL_BLIND", "hero", 0.5, None),
    ("POST_BIG_BLIND", "seat_lower_left", 1.0, None),
    ("FOLD", "seat_upper_left", None, None),
    ("FOLD", "seat_upper_right", None, None),
    ("FOLD", "seat_mid_right", None, None),
    ("RAISE", "seat_lower_right", None, 2.0),
    ("CALL", "hero", 1.5, None),
    ("CALL", "seat_lower_left", 1.0, None),
    ("CHECK", "hero", None, None),
    ("BET", "seat_lower_left", 3.37, None),
    ("FOLD", "seat_lower_right", None, None),
    ("CALL", "hero", 3.37, None),
    ("CHECK", "hero", None, None),
    ("CHECK", "seat_lower_left", None, None),
]


def main():
    with tempfile.TemporaryDirectory() as td:
        result = replay(
            progression_dir=td
        )

        hand = result["hand"]
        events = result["events"]

        # The shared replay now continues through RIVER.
        # This test owns PREFLOP + FLOP + TURN only.
        observed = [
            (
                row["action"],
                row["seat"],
                row["amount_bb"],
                row["raise_to_bb"],
            )
            for row in hand.semantic_actions()
            if row["street"] != "RIVER"
        ]

        print("===== TURN / RIVER BOUNDARY EVENTS =====")

        for row in events:
            if (
                row.get("frame", 0) >= 103
                or row.get("type")
                == "STREET_BOUNDARY_COMPLETION"
            ):
                print(row)

        print()
        print("===== ACTIONS THROUGH TURN =====")

        for row in hand.semantic_actions():
            print(row)

        assert observed == EXPECTED, observed

        # The shared replay now advances through RIVER.
        # TURN completion is owned by the objective RIVER
        # boundary assertions below, not final replay state.

        turn_start = [
            row
            for row in events
            if (
                row.get("type")
                == "STREET_STARTED"
                and row.get("street")
                == "TURN"
            )
        ]

        assert len(turn_start) == 1
        assert turn_start[0]["frame"] == 103
        assert turn_start[0]["next_actor"] == "hero"

        boundary = [
            row
            for row in events
            if row.get("type")
            == "RIVER_BOUNDARY"
        ]

        assert len(boundary) == 1
        assert boundary[0]["frame"] == 115

        assert boundary[0]["pending_before"] == [
            "hero",
            "seat_lower_left",
        ]

        completions = [
            (
                row["frame"],
                row["seat"],
                row["semantic_action"],
            )
            for row in events
            if row.get("type")
            == "STREET_BOUNDARY_COMPLETION"
        ]

        assert completions == [
            (
                115,
                "hero",
                "CHECK",
            ),
            (
                115,
                "seat_lower_left",
                "CHECK",
            ),
        ], completions

        river_board = [
            row
            for row in events
            if (
                row.get("type")
                == "BOARD_IDENTITY_OBSERVED"
                and row.get("street")
                == "RIVER"
            )
        ]

        assert len(river_board) == 1

        assert river_board[0]["frame"] == 115

        assert river_board[0]["board"] == [
            "Jd",
            "9s",
            "Tc",
            "9h",
            "7h",
        ]

        # These physical wakes were independently verified to
        # contain zero positive stack commitment.
        for frame in (
            108,
            111,
            113,
        ):
            wakes = [
                row
                for row in events
                if (
                    row.get("frame")
                    == frame
                    and row.get("type")
                    == "STACK_MOTION_WAKE"
                )
            ]

            for row in wakes:
                assert (
                    row.get(
                        "physical_delta_bb"
                    )
                    in (
                        None,
                        0.0,
                    )
                ), row

                assert (
                    "semantic_action"
                    not in row
                ), row

        print()
        print(
            "V0.17 JULY22 FRAME TURN REPLAY: PASS"
        )


if __name__ == "__main__":
    main()
