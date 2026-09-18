from dataclasses import dataclass
from typing import Tuple


EXPECTED_ACTIONS = (
    ("PREFLOP", "hero", "POST_SMALL_BLIND", 0.5, None),
    ("PREFLOP", "seat_lower_left", "POST_BIG_BLIND", 1.0, None),
    ("PREFLOP", "seat_upper_left", "FOLD", None, None),
    ("PREFLOP", "seat_upper_right", "FOLD", None, None),
    ("PREFLOP", "seat_mid_right", "FOLD", None, None),
    ("PREFLOP", "seat_lower_right", "RAISE", None, 2.0),
    ("PREFLOP", "hero", "CALL", 1.5, None),
    ("PREFLOP", "seat_lower_left", "CALL", 1.0, None),
    ("FLOP", "hero", "CHECK", None, None),
    ("FLOP", "seat_lower_left", "BET", 3.37, None),
    ("FLOP", "seat_lower_right", "FOLD", None, None),
    ("FLOP", "hero", "CALL", 3.37, None),
    ("TURN", "hero", "CHECK", None, None),
    ("TURN", "seat_lower_left", "CHECK", None, None),
    ("RIVER", "hero", "CHECK", None, None),
    ("RIVER", "seat_lower_left", "BET", 6.75, None),
    ("RIVER", "hero", "FOLD", None, None),
)

EXPECTED_PUBLICATION_FRAMES = (
    38,
    40,
    40,
    43,
    49,
    52,
    52,
    91,
    97,
    102,
    103,
    115,
    128,
    135,
)


@dataclass(frozen=True)
class Comparison:
    passed: bool
    errors: Tuple[str, ...]


def compare_july22(run):
    errors = []

    if run.frame_count != 135:
        errors.append(
            f"frame_count={run.frame_count}, "
            "expected=135"
        )

    if run.final_actions != EXPECTED_ACTIONS:
        errors.append(
            "final semantic action sequence mismatch"
        )

    frames = tuple(
        row.frame
        for row in run.publications
    )

    if frames != EXPECTED_PUBLICATION_FRAMES:
        errors.append(
            "publication frames mismatch: "
            f"{frames}"
        )

    counts = tuple(
        row.action_count
        for row in run.publications
    )

    if counts != tuple(sorted(counts)):
        errors.append(
            "publication action counts are "
            f"non-monotonic: {counts}"
        )

    if not counts or counts[-1] != 17:
        errors.append(
            "final publication action count "
            "is not 17"
        )

    required_text = (
        "FLOP: Jd 9s Tc",
        "TURN: 9h",
        "RIVER: 7h",
        "BB (Birkam) bets 6.75 BB",
        "SB (poker5068) folds",
    )

    for token in required_text:
        if token not in run.final_text:
            errors.append(
                f"final product missing: {token}"
            )

    # Street-boundary product must exist before any later
    # action on that street can contaminate the publication.
    required_boundaries = {
        (52, "FLOP"): 8,
        (103, "TURN"): 12,
        (115, "RIVER"): 14,
    }

    for key, expected_count in (
        required_boundaries.items()
    ):
        frame, street = key

        matches = [
            row
            for row in run.publications
            if (
                row.frame == frame
                and row.street == street
            )
        ]

        if len(matches) != 1:
            errors.append(
                "missing/duplicate boundary "
                f"publication: {key}"
            )
            continue

        if (
            matches[0].action_count
            != expected_count
        ):
            errors.append(
                f"{street} boundary action_count="
                f"{matches[0].action_count}, "
                f"expected={expected_count}"
            )

    return Comparison(
        passed=not errors,
        errors=tuple(errors),
    )
