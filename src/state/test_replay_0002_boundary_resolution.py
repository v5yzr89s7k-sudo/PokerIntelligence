import cv2
import json

from pathlib import Path

from src.vision.stack_reader import read_stack
from src.state.boundary_stack_observation import (
    BoundaryStackObservation,
)
from src.state.boundary_action_resolver import (
    resolve_boundary_action,
)


SESSION = Path(
    "runtime/debug/action_sequence/20260808_114630"
)

GEOMETRY = json.loads(
    Path("config/geometry.json").read_text()
)


def read_real_stack(seat, frame_index):
    path = SESSION / f"{frame_index:04d}_full.png"

    if not path.exists():
        raise AssertionError(
            f"Replay 0002 frame missing: {path}"
        )

    image = cv2.imread(str(path))

    if image is None:
        raise AssertionError(
            f"Could not read Replay 0002 frame: {path}"
        )

    image = cv2.resize(
        image,
        (934, 696),
    )

    r = GEOMETRY["stack_regions"][seat]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    result = read_stack(
        image[y:y+h, x:x+w]
    )

    return path, result


def main():
    # ------------------------------------------------------------
    # UTG+1
    #
    # Real Replay 0002 chronology:
    #
    #   UTG+1 raises to 6 BB
    #   LJ raises to 7 BB
    #   Hero calls 7 BB
    #
    # UTG+1 therefore owes a response to the final 7 BB price.
    # Its already-accounted live commitment is 6 BB.
    #
    # Frame 79 is the first locally observed flop frame, so its
    # stack is terminal evidence for the preflop betting round.
    # ------------------------------------------------------------

    seat = "seat_mid_right"

    frame_path, result = read_real_stack(
        seat,
        79,
    )

    print("===== REAL REPLAY 0002 UTG+1 BOUNDARY READ =====")
    print(result)

    assert result["stack_bb"] == 93.41, result
    assert float(result["confidence"]) >= 0.90, result
    assert int(result["votes"]) >= 2, result

    observation = BoundaryStackObservation(
        street="PREFLOP",
        seat=seat,

        # Last authoritative stack after UTG+1's own 6 BB raise.
        previous_stack_bb=93.41,

        observed_stack_bb=float(
            result["stack_bb"]
        ),

        confidence=float(
            result["confidence"]
        ),
        votes=int(
            result["votes"]
        ),
        mode=str(
            result.get("mode") or ""
        ),

        frame_path=str(frame_path),
        ts=None,
    )

    resolution = resolve_boundary_action(
        observation,

        # Preserved PREFLOP response state says UTG+1 owes
        # a response to LJ's 7 BB raise.
        owes_action=True,
        betting_open=True,
        current_price_bb=7.0,

        # UTG+1 already has 6 BB live in the pot.
        prior_live_commitment_bb=6.0,
    )

    print()
    print("===== UTG+1 BOUNDARY OBSERVATION =====")
    print(observation.to_dict())

    print()
    print("===== UTG+1 RESOLUTION =====")
    print(resolution.to_dict())

    assert resolution.resolved is True
    assert resolution.action == "FOLD"
    assert resolution.amount_bb is None

    # ------------------------------------------------------------
    # Negative control:
    #
    # The same unchanged stack must NOT become a fold merely
    # because we have a boundary observation. If the preserved
    # betting state says the player does not owe action, the
    # resolver must refuse to assign semantics.
    # ------------------------------------------------------------

    negative = resolve_boundary_action(
        observation,
        owes_action=False,
        betting_open=True,
        current_price_bb=7.0,
        prior_live_commitment_bb=6.0,
    )

    assert negative.resolved is False
    assert negative.action is None

    print()
    print("===== NEGATIVE CONTROL =====")
    print(negative.to_dict())

    print()
    print(
        "PASS Replay 0002 boundary resolution: "
        "real unchanged UTG+1 stack at flop boundary + "
        "preserved 6-of-7 BB response obligation -> FOLD; "
        "same pixels without an action obligation remain unresolved"
    )


if __name__ == "__main__":
    main()
