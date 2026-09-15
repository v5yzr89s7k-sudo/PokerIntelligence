from pathlib import Path

import cv2

from src.events.local_event_detector import LocalEventDetector


ROOT = Path(__file__).resolve().parents[2]

SEP8 = (
    ROOT
    / "runtime/debug/action_sequence/20260908_123720"
)

REAL_FLOP = (
    ROOT
    / "runtime/debug/action_sequence/20260812_104222"
)


def load(session, index):
    path = session / f"{index:04d}_full.png"

    assert path.exists(), (
        f"required recorded frame missing: {path}"
    )

    image = cv2.imread(str(path))

    assert image is not None, (
        f"could not decode recorded frame: {path}"
    )

    if image.shape[:2] != (696, 934):
        image = cv2.resize(
            image,
            (934, 696),
        )

    return path, image


def main():
    print(
        "===== SEPTEMBER 8 RABBIT-HUNT BOARD CONTRACT ====="
    )
    print()

    # --------------------------------------------------------
    # Real September 8 sequence.
    #
    # 0933: normal PREFLOP table, no board.
    # 0934: Rabbit Hunt appears as three black-backed cards
    #       carrying the white rabbit artwork.
    #
    # There was no FLOP in this hand.
    # --------------------------------------------------------

    pre_path, pre = load(SEP8, 933)
    rabbit_path, rabbit = load(SEP8, 934)

    detector = LocalEventDetector()

    before = detector.detect(pre)
    rabbit_changes = detector.detect(rabbit)

    print("preflop_frame:", pre_path.name)
    print("preflop_board_count:", before.board_count)
    print()
    print("rabbit_frame:", rabbit_path.name)
    print("rabbit_board_count:", rabbit_changes.board_count)
    print("rabbit_board_changed:", rabbit_changes.board_changed)

    assert before.board_count == 0, (
        "HARNESS INVALID: frame 0933 is not recognized "
        "as board-free PREFLOP"
    )

    # This is the new contract.
    #
    # Rabbit Hunt card backs are UI/result-state graphics,
    # not community cards and therefore cannot establish
    # a physical FLOP boundary.
    assert rabbit_changes.board_count == 0, (
        "RED: September 8 Rabbit Hunt card backs were "
        f"classified as a real board: "
        f"board_count={rabbit_changes.board_count}"
    )

    # --------------------------------------------------------
    # Positive control:
    # preserve detection of a real three-card FLOP.
    #
    # This recorded Aug 12 fixture is already used elsewhere
    # as a genuine physical-flop frame.
    # --------------------------------------------------------

    baseline_path, baseline = load(REAL_FLOP, 54)
    control_path, control = load(REAL_FLOP, 58)

    control_detector = LocalEventDetector()

    baseline_changes = control_detector.detect(
        baseline
    )

    control_changes = control_detector.detect(
        control
    )

    print()
    print(
        "real_flop_baseline:",
        baseline_path.name,
    )
    print(
        "real_flop_baseline_count:",
        baseline_changes.board_count,
    )

    print()
    print("real_flop_frame:", control_path.name)
    print(
        "real_flop_board_count:",
        control_changes.board_count,
    )

    assert control_changes.board_count == 3, (
        "CONTROL FAILURE: genuine recorded FLOP no longer "
        f"detects three cards: "
        f"board_count={control_changes.board_count}"
    )

    print()
    print(
        "PASS: Rabbit Hunt does not create a board while "
        "a genuine recorded FLOP remains detectable"
    )


if __name__ == "__main__":
    main()
