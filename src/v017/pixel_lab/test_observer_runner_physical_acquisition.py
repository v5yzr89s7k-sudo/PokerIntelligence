from pathlib import Path
from unittest.mock import patch

from src.v017.pixel_lab import observer_runner


def main():
    root = Path(
        "runtime/pixel_lab/observer_input/"
        "controlled_hand_2826921615"
    )

    calls = []

    real_build = (
        observer_runner
        .build_observer_from_frame
    )

    def capture_build(
        image,
        frame_path,
        hand_id,
    ):
        calls.append(
            Path(frame_path).name
        )

        return real_build(
            image,
            frame_path,
            hand_id,
        )

    with patch.object(
        observer_runner,
        "build_observer_from_frame",
        side_effect=capture_build,
    ):
        result = observer_runner.run(
            observer_input=root,
            publish_live_product=False,
        )

    print(
        "bootstrap_calls =",
        calls,
    )

    assert calls, calls

    assert calls[0] == (
        "frame_0012.png"
    ), calls

    observer = result["observer"]

    print(
        "hero_cards =",
        observer.hand.hero_cards,
    )

    assert tuple(
        observer.hand.hero_cards
    ) == (
        "Kd",
        "2d",
    )

    print()
    print(
        "PIXEL RUNNER PHYSICAL ACQUISITION: PASS"
    )


if __name__ == "__main__":
    main()
