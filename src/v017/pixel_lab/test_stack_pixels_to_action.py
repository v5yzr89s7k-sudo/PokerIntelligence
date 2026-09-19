"""
V0.17 Pixel Lab: stack pixels -> semantic action.

The deterministic truth exists only in the generator/comparator side.

FrameHandObserver receives image pixels, bootstrap state, and production
geometry. It receives no expected action or generated stack truth.
"""

from pathlib import Path
import json
import shutil

import cv2

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)
from src.vision.stack_reader import (
    read_stack_native_fast,
)

ROOT = Path(__file__).resolve().parents[3]

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)

SOURCE = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_8p.png"
)

WORK = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "stack_pixels_to_action"
)

OBSERVER_INPUT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "stack_pixels_to_action"
)

TARGET_SEAT = "seat_mid_right"

# Authentic substrate stack for this seat.
PRIOR_STACK = 82.14

# Private generator truth.
TARGET_STACK = 79.14


def crop(frame, rect):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])
    return frame[y:y+h, x:x+w]


def extract_digit_atlas(source):
    from src.v017.pixel_lab.test_novel_stack_pixels import (
        build_atlas,
    )

    image = cv2.imread(str(source))
    assert image is not None, source

    return build_atlas(image)

def main():
    assert SOURCE.exists(), SOURCE

    # First run the permanent proven generator calibration.
    # This test consumes only its private generator artifacts.
    atlas = extract_digit_atlas(SOURCE)

    shutil.rmtree(
        WORK,
        ignore_errors=True,
    )
    shutil.rmtree(
        OBSERVER_INPUT,
        ignore_errors=True,
    )

    WORK.mkdir(
        parents=True,
        exist_ok=True,
    )
    OBSERVER_INPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    base = cv2.imread(str(SOURCE))
    assert base is not None

    # --------------------------------------------------------
    # Generator side.
    #
    # We deliberately use the existing novel-stack renderer rather
    # than teach the observer anything about TARGET_STACK.
    # --------------------------------------------------------

    from src.v017.pixel_lab.test_novel_stack_pixels import (
        render_stack_value,
    )

    changed = base.copy()

    render_stack_value(
        changed,
        geometry=GEOMETRY,
        seat=TARGET_SEAT,
        value=TARGET_STACK,
        atlas=atlas,
    )

    generator_frames = [
        ("frame_0001.png", base),
        ("frame_0002.png", changed),
        ("frame_0003.png", changed.copy()),
        ("frame_0004.png", changed.copy()),
    ]

    for filename, image in generator_frames:
        private_path = WORK / filename
        public_path = OBSERVER_INPUT / filename

        assert cv2.imwrite(
            str(private_path),
            image,
        )

        # Only PNG bytes cross the isolation wall.
        shutil.copy2(
            private_path,
            public_path,
        )

    print("===== GENERATOR =====")
    print("private truth =", TARGET_STACK)
    print(
        "frames =",
        tuple(
            name
            for name, _ in generator_frames
        ),
    )

    # --------------------------------------------------------
    # Isolation wall.
    # --------------------------------------------------------

    files = tuple(
        sorted(
            path.name
            for path in OBSERVER_INPUT.iterdir()
        )
    )

    assert files == (
        "frame_0001.png",
        "frame_0002.png",
        "frame_0003.png",
        "frame_0004.png",
    )

    assert all(
        path.suffix == ".png"
        for path in OBSERVER_INPUT.iterdir()
    )

    print()
    print("===== ISOLATION WALL =====")
    print("observer input =", files)
    print("ONLY PIXELS CROSSED WALL: PASS")

    # --------------------------------------------------------
    # Observer side.
    #
    # Deliberately minimal heads-up semantic state so target seat is
    # immediately authoritative. No expected action is supplied.
    # --------------------------------------------------------

    players = [
        {
            "seat": TARGET_SEAT,
            "position": "SB",
            "name": "Opponent",
            "stack_bb": PRIOR_STACK,
            "dealt_in": True,
        },
        {
            "seat": "hero",
            "position": "BB",
            "name": "Hero",
            "stack_bb": 80.43,
            "dealt_in": True,
            "is_hero": True,
        },
    ]

    observer = FrameHandObserver(
        players=players,
        action_order=[
            TARGET_SEAT,
            "hero",
        ],
        small_blind_seat=TARGET_SEAT,
        big_blind_seat="hero",
        geometry=GEOMETRY,
        trusted_stacks={
            TARGET_SEAT: PRIOR_STACK,
        },
        opponent_seats=[],
        quantitative_seats=[
            TARGET_SEAT,
        ],
        hero_seat="hero",
        hand_id="pixel-stack-action",
        stack_reader=read_stack_native_fast,
    )

    gate = StackSettlementGate()

    physical = []
    settled_rows = []
    admitted_rows = []

    print()
    print("===== OBSERVER =====")

    for frame_id, path in enumerate(
        sorted(OBSERVER_INPUT.glob("*.png")),
        start=1,
    ):
        image = cv2.imread(str(path))
        assert image is not None

        result = observer.process_frame(
            image,
            frame_id=frame_id,
        )

        for event in result.events:
            if (
                event.get("type")
                != "STACK_QUANTITATIVE_OBSERVATION"
            ):
                continue

            physical.append(dict(event))

            print(
                "physical",
                frame_id,
                event,
            )

            settled = gate.observe(
                event,
                phase=observer.hand.street,
                has_commitment_evidence=False,
                all_in_confirmed=False,
            )

            if settled is None:
                continue

            settled_rows.append(settled)

            admitted = (
                observer.admit_quantitative_observation(
                    event
                )
            )

            if admitted:
                admitted_rows.extend(admitted)
                observer.clear_quantitative_ownership(
                    settled.seat
                )
                gate.clear_seat(
                    settled.seat
                )

    print()
    print("===== OBSERVED RESULT =====")
    print("physical count =", len(physical))
    print("settlements =", settled_rows)
    print("admitted =", admitted_rows)
    print(
        "actions =",
        tuple(
            (
                action.street,
                action.seat,
                action.action,
                action.amount_bb,
                action.raise_to_bb,
            )
            for action in observer.hand.actions
        ),
    )
    print(
        "trusted stack =",
        observer.trusted_stacks.get(
            TARGET_SEAT
        ),
    )

    # --------------------------------------------------------
    # Offline comparator.
    # Truth re-enters only here.
    # --------------------------------------------------------

    print()
    print("===== OFFLINE COMPARATOR =====")

    assert len(physical) >= 2, (
        "production observer did not produce two independent "
        "quantitative observations"
    )

    values = [
        event.get("resolved_value")
        for event in physical
        if event.get("resolved_value") is not None
    ]

    assert values
    assert any(
        abs(float(value) - TARGET_STACK) < 0.011
        for value in values
    ), values

    assert settled_rows, (
        "production settlement gate never established "
        "temporal authority"
    )

    assert abs(
        observer.trusted_stacks[TARGET_SEAT]
        - TARGET_STACK
    ) < 0.011

    semantic = [
        action
        for action in observer.hand.actions
        if action.seat == TARGET_SEAT
        and action.action
        not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    assert len(semantic) == 1, semantic

    action = semantic[0]

    print(
        "offline truth stack =",
        TARGET_STACK,
    )
    print(
        "observer semantic action =",
        action,
    )

    print()
    print(
        "V0.17 PIXEL LAB STACK PIXELS "
        "TO ACTION: PASS"
    )


if __name__ == "__main__":
    main()
