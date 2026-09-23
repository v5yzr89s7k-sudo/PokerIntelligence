from pathlib import Path

import cv2

from src.v017.pixel_lab.observer_runner import (
    _recover_preacquisition_stacks,
)
from src.v017.run_live_observer import (
    build_observer_from_frame,
)


def main():
    root = Path(
        "runtime/pixel_lab/observer_input/"
        "controlled_hand_2826921615"
    )

    paths = tuple(
        sorted(
            root.glob("frame_*.png")
        )
    )

    acquisition_index = next(
        i
        for i, path in enumerate(paths)
        if path.name == "frame_0012.png"
    )

    acquisition_path = paths[
        acquisition_index
    ]

    image = cv2.imread(
        str(acquisition_path)
    )

    assert image is not None

    observer = build_observer_from_frame(
        image,
        acquisition_path,
        hand_id="preacquisition-recovery-test",
    )

    assert observer is not None

    print(
        "before_trusted =",
        observer.trusted_stacks,
    )

    assert (
        "seat_top"
        not in observer.trusted_stacks
    )

    recovered = (
        _recover_preacquisition_stacks(
            observer,
            paths,
            acquisition_index,
        )
    )

    print(
        "recovered =",
        recovered,
    )

    print(
        "after_trusted =",
        observer.trusted_stacks,
    )

    assert "seat_top" in recovered

    assert (
        recovered["seat_top"]["frame"]
        == "frame_0001.png"
    )

    assert abs(
        observer.trusted_stacks[
            "seat_top"
        ]
        - 44.83
    ) < 0.001

    assert (
        "seat_top"
        in observer.quantitative_seats
    )

    player = observer.hand.players[
        "seat_top"
    ]

    assert abs(
        player.starting_stack_bb
        - 44.83
    ) < 0.001

    print()
    print(
        "PRE-ACQUISITION STACK RECOVERY: PASS"
    )


if __name__ == "__main__":
    main()
