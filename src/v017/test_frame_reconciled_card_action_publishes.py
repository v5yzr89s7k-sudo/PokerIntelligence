"""
Regression:

A card disappearance admitted by frame reconciliation changes authoritative
HandEngine state. The same physical transaction must therefore create a
publication even when no quantitative action happens to publish alongside it.

This specifically protects the frame-15/frame-16 controlled-hand defect where
semantic folds existed in HandEngine but current_hand.txt remained stale.
"""

from pathlib import Path

import cv2

from src.v017.pixel_lab.observer_runner import (
    run,
)


ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "controlled_hand_2826921615"
)


def main():
    assert INPUT.exists(), INPUT

    result = run(
        observer_input=INPUT,
        publish_live_product=False,
    )

    observer = result["observer"]

    actions = observer.hand.semantic_actions()

    expected_prefix = (
        ("seat_mid_left", "POST_SMALL_BLIND"),
        ("seat_upper_left", "POST_BIG_BLIND"),
        ("seat_top", "RAISE"),
        ("seat_upper_right", "FOLD"),
        ("seat_mid_right", "FOLD"),
        ("seat_lower_right", "FOLD"),
    )

    observed_prefix = tuple(
        (
            row["seat"],
            row["action"],
        )
        for row in actions[:6]
    )

    print(
        "observed_prefix =",
        observed_prefix,
    )

    assert observed_prefix == expected_prefix, (
        observed_prefix,
        expected_prefix,
    )

    by_frame = {}

    for publication in observer.publications:
        raw_frame = publication.get(
            "frame"
        )

        try:
            frame = int(
                raw_frame
            )
        except (TypeError, ValueError):
            # Bootstrap and other lifecycle publications are valid,
            # but they are outside this physical-frame regression.
            continue

        by_frame.setdefault(
            frame,
            [],
        ).append(
            publication
        )

    for frame, minimum_actions in (
        (14, 4),
        (15, 5),
        (16, 6),
    ):
        rows = by_frame.get(
            frame,
            [],
        )

        print()
        print(
            "frame =",
            frame,
        )
        print(
            "publications =",
            [
                row["action_count"]
                for row in rows
            ],
        )

        assert rows, (
            "missing publication",
            frame,
        )

        latest = rows[-1]

        assert int(
            latest["action_count"]
        ) >= minimum_actions, (
            frame,
            latest["action_count"],
            minimum_actions,
        )

    frame15 = by_frame[15][-1]["text"]
    frame16 = by_frame[16][-1]["text"]

    assert (
        "LJ (Meatbag) folds"
        in frame15
    )

    assert (
        "HJ (Baron_Team) folds"
        in frame16
    )

    print()
    print(
        "FRAME-RECONCILED CARD PUBLICATION: PASS"
    )


if __name__ == "__main__":
    main()
