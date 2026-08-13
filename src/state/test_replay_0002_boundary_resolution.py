import cv2
import json

from pathlib import Path

from src.vision.stack_reader import (
    read_stack,
    read_stack_independent_consensus,
)
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

    crop = image[y:y+h, x:x+w]

    independent = (
        read_stack_independent_consensus(crop)
        or {}
    )

    if (
        independent.get("stack_bb") is not None
        and float(
            independent.get("confidence") or 0.0
        ) >= 0.95
        and int(
            independent.get("votes") or 0
        ) >= 3
    ):
        result = independent
    else:
        result = read_stack(crop)

    return path, result


def main():
    # ------------------------------------------------------------
    # UTG+1
    #
    # Real Replay 0002 chronology:
    #
    #   UTG+1 raises to 2 BB
    #   LJ raises to 7 BB
    #   Hero calls 7 BB
    #
    # UTG+1 therefore owes a response to the final 7 BB price.
    # Its already-accounted live commitment is 2 BB.
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

    assert result["stack_bb"] == 53.41, result
    assert float(result["confidence"]) >= 0.90, result
    assert int(result["votes"]) >= 2, result

    observation = BoundaryStackObservation(
        street="PREFLOP",
        seat=seat,

        # Last authoritative stack after UTG+1's own 2 BB raise.
        previous_stack_bb=53.41,

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

        # UTG+1 already has 2 BB live in the pot.
        prior_live_commitment_bb=2.0,
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
        prior_live_commitment_bb=2.0,
    )

    assert negative.resolved is False
    assert negative.action is None

    print()
    print("===== NEGATIVE CONTROL =====")
    print(negative.to_dict())

    # ------------------------------------------------------------
    # Remaining unresolved responders.
    #
    # Use the same real flop-boundary frame. Every seat below still
    # owes a response to the final 7 BB preflop price.
    #
    # Strong unchanged reads may resolve FOLD.
    # Weak/ambiguous reads must remain unresolved.
    # ------------------------------------------------------------

    cases = [
        {
            "position": "CO",
            "seat": "seat_lower_left",
            "previous": 64.13,
            "prior_live": 0.0,
            "expected": "FOLD",
        },
        {
            "position": "BTN",
            "seat": "seat_mid_left",
            "previous": 19.82,
            "prior_live": 0.0,
            "expected": "FOLD",
        },
        {
            "position": "SB",
            "seat": "seat_upper_left",
            "previous": 37.94,
            "prior_live": 0.5,
            "expected": "FOLD",
        },
        {
            "position": "BB",
            "seat": "seat_top",
            "previous": 28.36,
            "prior_live": 1.0,
            # The exact boundary frame now independently resolves
            # the displayed 28.36 BB with strong consensus.
            "frame": 79,
            "expected": "FOLD",
        },
    ]

    print()
    print("===== REMAINING REAL BOUNDARY RESPONDERS =====")

    actual = []

    for case in cases:
        case_frame = case.get(
            "frame",
            79,
        )

        case_path, case_read = read_real_stack(
            case["seat"],
            case_frame,
        )

        case_observation = BoundaryStackObservation(
            street="PREFLOP",
            seat=case["seat"],
            previous_stack_bb=case["previous"],
            observed_stack_bb=case_read.get("stack_bb"),
            confidence=float(
                case_read.get("confidence") or 0.0
            ),
            votes=int(
                case_read.get("votes") or 0
            ),
            mode=str(
                case_read.get("mode") or ""
            ),
            frame_path=str(case_path),
            ts=None,
        )

        case_resolution = resolve_boundary_action(
            case_observation,
            owes_action=True,
            betting_open=True,
            current_price_bb=7.0,
            prior_live_commitment_bb=case["prior_live"],
        )

        print()
        print(
            case["position"],
            case["seat"],
        )
        print("read      =", case_read)
        print(
            "observation=",
            case_observation.to_dict(),
        )
        print(
            "resolution =",
            case_resolution.to_dict(),
        )

        if case["expected"] is None:
            assert case_resolution.resolved is False, (
                case_resolution
            )
            assert case_resolution.action is None, (
                case_resolution
            )
        else:
            assert case_resolution.resolved is True, (
                case_resolution
            )
            assert (
                case_resolution.action
                == case["expected"]
            ), case_resolution

        actual.append(
            (
                case["position"],
                case_resolution.action,
                case_resolution.resolved,
                case_observation.confidence,
                case_observation.votes,
            )
        )

    print()
    print("===== REAL BOUNDARY SUMMARY =====")

    for item in actual:
        print(item)

    assert actual[0][0:3] == (
        "CO",
        "FOLD",
        True,
    )

    assert actual[1][0:3] == (
        "BTN",
        "FOLD",
        True,
    )

    assert actual[2][0:3] == (
        "SB",
        "FOLD",
        True,
    )

    assert actual[3][0:3] == (
        "BB",
        "FOLD",
        True,
    )

    print()
    print(
        "PASS Replay 0002 boundary resolution: "
        "real trusted terminal stack evidence independently resolves "
        "UTG+1/CO/BTN/SB/BB folds without lowering confidence thresholds"
    )


if __name__ == "__main__":
    main()
