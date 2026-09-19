"""
First real-ACR PNG-only FrameHandObserver crossing.

Generator truth is used only before the isolation wall to produce the
private PNG progression. Only selected PNG bytes are copied into the
observer input directory.

observer_runner itself contains no ACR parser/truth/renderer imports.
"""

from pathlib import Path
import shutil

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)
from src.v017.pixel_lab.acr_truth_timeline import (
    compile_truth_timeline,
)
from src.v017.pixel_lab.acr_pixel_renderer import (
    render_hand_progression,
)


ROOT = Path(__file__).resolve().parents[3]

CORPUS = (
    ROOT
    / "runtime/pixel_lab/acr_hand_histories"
)

GENERATOR = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "observer_crossing_2826874674"
)

OBSERVER_INPUT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "real_acr_hand_2826874674"
)

HAND_ID = "2826874674"


def generator_phase():
    shutil.rmtree(
        GENERATOR,
        ignore_errors=True,
    )
    shutil.rmtree(
        OBSERVER_INPUT,
        ignore_errors=True,
    )

    GENERATOR.mkdir(
        parents=True,
        exist_ok=True,
    )
    OBSERVER_INPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    hand = next(
        hand
        for _, hand in parse_corpus(CORPUS)
        if hand.hand_id == HAND_ID
    )

    truth = compile_truth_timeline(
        hand
    )

    rendered = render_hand_progression(
        hand=hand,
        truth_frames=truth,
        output_dir=GENERATOR,
    )

    assert len(rendered["frames"]) == 20

    # Acquisition occurs at physical frame 9 after forced
    # contributions have settled and immediately before UTG acts.
    selected = rendered["frames"][8:]

    assert len(selected) == 12

    for source in selected:
        destination = (
            OBSERVER_INPUT
            / source.name
        )

        # Bytes only cross the wall.
        shutil.copyfile(
            source,
            destination,
        )

    print(
        "generator frames =",
        len(rendered["frames"]),
    )
    print(
        "observer frames =",
        tuple(
            path.name
            for path in sorted(
                OBSERVER_INPUT.glob(
                    "frame_*.png"
                )
            )
        ),
    )


def assert_wall():
    files = tuple(
        sorted(
            OBSERVER_INPUT.iterdir()
        )
    )

    assert files

    assert all(
        path.suffix.lower() == ".png"
        for path in files
    )

    assert all(
        path.name.startswith(
            "frame_"
        )
        for path in files
    )

    print(
        "ONLY PNG PIXELS CROSSED WALL: PASS"
    )


def observer_phase():
    # Import only after the wall is established.
    from src.v017.pixel_lab.observer_runner import (
        run,
    )

    return run()


def main():
    print(
        "===== PRIVATE GENERATOR ====="
    )
    generator_phase()

    print()
    print(
        "===== ISOLATION WALL ====="
    )
    assert_wall()

    print()
    print(
        "===== OBSERVER ====="
    )
    result = observer_phase()

    # First crossing acceptance is intentionally structural.
    #
    # We do not supply expected ACR actions to observer_runner.
    # We require that production perception sees the known physical
    # fold and board signals and that HandEngine makes progress.
    physical_types = tuple(
        event.get("type")
        for event in result[
            "physical_events"
        ]
    )

    assert (
        "OPPONENT_CARDS_DISAPPEARED"
        in physical_types
    ), physical_types

    assert (
        "FLOP_BOUNDARY_PHYSICAL"
        in physical_types
    ), physical_types

    observer = result["observer"]

    actions = tuple(
        observer.hand.semantic_actions()
    )

    assert actions, (
        "production HandEngine "
        "made no semantic progress"
    )

    print()
    print(
        "PNG -> FRAMEHANDOBSERVER: PASS"
    )
    print(
        "PHYSICAL FOLD SIGNALS: PASS"
    )
    print(
        "PHYSICAL FLOP BOUNDARY: PASS"
    )
    print(
        "HANDENGINE SEMANTIC PROGRESS: PASS"
    )
    print()
    print(
        "V0.17 REAL ACR OBSERVER CROSSING: PASS"
    )


if __name__ == "__main__":
    main()
