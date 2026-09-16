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
]


def main():
    with tempfile.TemporaryDirectory() as td:
        result = replay(
            progression_dir=td
        )

        hand = result["hand"]
        events = result["events"]

        # The shared replay now continues through the complete
        # hand. This test owns PREFLOP + FLOP only.
        observed = [
            (
                row["action"],
                row["seat"],
                row["amount_bb"],
                row["raise_to_bb"],
            )
            for row
            in hand.semantic_actions()
            if row["street"] in (
                "PREFLOP",
                "FLOP",
            )
        ]

        print(
            "===== FRAME-DERIVED EVENTS ====="
        )

        for event in events:
            print(event)

        print()
        print(
            "===== ACTIONS THROUGH FLOP ====="
        )

        for row in (
            hand.semantic_actions()
        ):
            print(row)

        assert observed == EXPECTED, (
            observed
        )

        # The shared replay now advances beyond FLOP.
        # FLOP lifecycle is proven by the TURN boundary event,
        # not by the replay's eventual final street.

        turn_boundary = [
            event
            for event in events
            if event.get("type")
            == "TURN_BOUNDARY"
        ]

        assert len(turn_boundary) == 1
        assert turn_boundary[0]["frame"] == 103
        assert (
            turn_boundary[0][
                "next_actor_before"
            ]
            is None
        )

        # Critical chronology proof:
        # Hero CHECK must have been emitted when later BB physical
        # commitment established that Hero had already completed.
        hero_check = [
            event
            for event in events
            if (
                event.get("type")
                == "CHRONOLOGY_COMPLETION"
                and event.get("seat")
                == "hero"
                and event.get("frame")
                == 90
                and event.get(
                    "semantic_action"
                )
                == "CHECK"
            )
        ]

        assert len(hero_check) == 1
        assert (
            hero_check[0]["frame"]
            == 90
        )
        assert (
            hero_check[0]["proved_by"]
            == "seat_lower_left"
        )

        # False wakes may exist but cannot publish semantics.
        for frame in (
            57,
            73,
            96,
        ):
            rows = [
                event
                for event in events
                if (
                    event.get("frame")
                    == frame
                    and event.get("type")
                    == "STACK_MOTION_WAKE"
                )
            ]

            for row in rows:
                assert (
                    "semantic_action"
                    not in row
                ), row

        # Physical Hero 3.38 must normalize to authoritative 3.37.
        hero_call = [
            event
            for event in events
            if (
                event.get("frame")
                == 101
                and event.get("seat")
                == "hero"
                and event.get(
                    "semantic_action"
                )
                == "CALL"
            )
        ]

        assert len(hero_call) == 1
        assert (
            hero_call[0][
                "physical_delta_bb"
            ]
            == 3.38
        )
        assert (
            hero_call[0][
                "normalized_delta_bb"
            ]
            == 3.37
        )
        assert (
            hero_call[0][
                "snapped_to_call_price"
            ]
            is True
        )

        print()
        print(
            "V0.17 JULY22 FRAME FLOP REPLAY: PASS"
        )


if __name__ == "__main__":
    main()
