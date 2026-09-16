from pathlib import Path
import tempfile

from src.v017.july22_frame_preflop_replay import (
    replay,
)


# Expected output is intentionally defined only in the TEST.
# The production replay module cannot import this.
EXPECTED = [
    ("POST_SMALL_BLIND", "hero", 0.5, None),
    ("POST_BIG_BLIND", "seat_lower_left", 1.0, None),
    ("FOLD", "seat_upper_left", None, None),
    ("FOLD", "seat_upper_right", None, None),
    ("FOLD", "seat_mid_right", None, None),
    ("RAISE", "seat_lower_right", None, 2.0),
    ("CALL", "hero", 1.5, None),
    ("CALL", "seat_lower_left", 1.0, None),
]


def main():
    with tempfile.TemporaryDirectory() as td:
        result = replay(
            progression_dir=td
        )

        hand = result["hand"]
        events = result["events"]
        publications = (
            result["publications"]
        )

        # The shared replay now continues through the complete
        # hand. This test owns only the PREFLOP semantic slice.
        observed = [
            (
                action["action"],
                action["seat"],
                action["amount_bb"],
                action["raise_to_bb"],
            )
            for action
            in hand.semantic_actions()
            if action["street"] == "PREFLOP"
        ]

        print(
            "===== FRAME-DERIVED EVENTS ====="
        )

        for event in events:
            print(event)

        print()
        print(
            "===== PRODUCT PUBLICATIONS ====="
        )

        for publication in publications:
            print(
                "frame=",
                publication["frame"],
                "actions=",
                publication[
                    "action_count"
                ],
                "next=",
                publication[
                    "next_actor"
                ],
                "processing_ms=",
                publication[
                    "processing_ms"
                ],
            )

        print()
        print(
            "===== FINAL PREFLOP ====="
        )

        for action in (
            hand.semantic_actions()
        ):
            print(action)

        assert observed == EXPECTED, (
            observed
        )

        # Do not assert the shared replay's final actor here.
        # Later street lifecycle is outside this slice.

        # The physical FLOP boundary must occur only after
        # preflop chronology has closed.
        boundaries = [
            event
            for event in events
            if event["type"]
            == "FLOP_BOUNDARY"
        ]

        assert boundaries

        assert (
            boundaries[0][
                "next_actor_before"
            ]
            is None
        )

        # No transient semantic publication may contain more
        # actions than the final authoritative sequence.
        for publication in publications:
            if publication["frame"] <= 52:
                assert (
                    publication[
                        "action_count"
                    ]
                    <= len(EXPECTED)
                )

        # Publication action counts may only move forward.
        counts = [
            publication[
                "action_count"
            ]
            for publication
            in publications
        ]

        assert counts == sorted(
            counts
        )

        print()
        print(
            "V0.17 JULY22 FRAME PREFLOP REPLAY: PASS"
        )


if __name__ == "__main__":
    main()
