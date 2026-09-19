"""
Pixel Lab hard isolation contract.

This test exists before the renderer or simulator.

The simulator is allowed to know deterministic ground truth.

The production observer is allowed to know only what the normal
production path can derive from rendered pixels.

Ground truth may be used only AFTER observation, by the comparator.
"""

from pathlib import Path
import inspect

from src.v017.frame_hand_observer import FrameHandObserver


ROOT = Path(__file__).resolve().parents[3]
PIXEL_LAB = ROOT / "src/v017/pixel_lab"


FORBIDDEN_OBSERVER_ARGUMENTS = {
    "truth",
    "ground_truth",
    "expected_actions",
    "expected_cards",
    "expected_board",
    "expected_stacks",
    "scenario",
    "scripted_actions",
    "simulator_state",
}


FORBIDDEN_RUNNER_IMPORTS = (
    "hand_generator",
    "truth_model",
    "ground_truth",
    "scenario_truth",
)


def assert_observer_interface_clean():
    signature = inspect.signature(
        FrameHandObserver.__init__
    )

    names = set(signature.parameters)

    leaked = sorted(
        names & FORBIDDEN_OBSERVER_ARGUMENTS
    )

    assert not leaked, (
        "FrameHandObserver exposes simulator truth: "
        f"{leaked}"
    )

    print(
        "FrameHandObserver truth arguments: NONE"
    )


def assert_pixel_lab_structure():
    """
    Once Pixel Lab components exist, enforce one-way ownership.

    Generator/renderer may know truth.

    observer_runner must not import truth-producing modules.

    comparator may read both sides because comparison occurs only
    after the observer has produced its output.
    """

    runner = PIXEL_LAB / "observer_runner.py"

    if not runner.exists():
        print(
            "observer_runner.py: not created yet "
            "(contract armed)"
        )
        return

    source = runner.read_text()

    violations = [
        token
        for token in FORBIDDEN_RUNNER_IMPORTS
        if token in source
    ]

    assert not violations, (
        "observer runner crossed truth isolation wall: "
        f"{violations}"
    )

    print(
        "observer_runner truth imports: NONE"
    )


def assert_no_environment_truth_channel():
    """
    Reserve environment-variable namespace against accidental
    simulator-to-observer truth injection.
    """

    runner = PIXEL_LAB / "observer_runner.py"

    if not runner.exists():
        print(
            "observer environment truth channel: "
            "not created yet (contract armed)"
        )
        return

    source = runner.read_text().upper()

    forbidden = (
        "PIXEL_LAB_TRUTH",
        "SIMULATOR_TRUTH",
        "GROUND_TRUTH",
        "EXPECTED_ACTIONS",
        "EXPECTED_CARDS",
        "EXPECTED_STACKS",
    )

    leaked = [
        token
        for token in forbidden
        if token in source
    ]

    assert not leaked, (
        "observer runner exposes truth through environment: "
        f"{leaked}"
    )

    print(
        "observer environment truth channel: NONE"
    )


def main():
    print(
        "===== V0.17 PIXEL LAB ISOLATION CONTRACT ====="
    )

    assert_observer_interface_clean()
    assert_pixel_lab_structure()
    assert_no_environment_truth_channel()

    print()
    print(
        "TRUTH -> RENDERER: ALLOWED"
    )
    print(
        "RENDERED PIXELS -> OBSERVER: ALLOWED"
    )
    print(
        "TRUTH -> OBSERVER: FORBIDDEN"
    )
    print(
        "OBSERVER OUTPUT + TRUTH -> COMPARATOR: ALLOWED"
    )

    print()
    print(
        "V0.17 PIXEL LAB ISOLATION CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
