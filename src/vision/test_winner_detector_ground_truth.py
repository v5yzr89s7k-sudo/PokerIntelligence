from pathlib import Path

from src.vision.winner_normalized_probe import (
    STACK_REGIONS,
    canonical_image,
    winner_roi_for_seat,
    crop,
    extract_bright_word,
    similarity,
    template,
)


ROOT = Path(__file__).resolve().parents[2]

SESSIONS = (
    ROOT
    / "runtime/debug/action_sequence"
)

# Human-verified from the recorded screenshots.
#
# These are deliberately NOT inferred from board-clear timing.
# Each positive frame visibly contains the ACR WINNER treatment.
# Each negative frame visibly precedes WINNER in the same hand.
CASES = [
    # Replay 0003 — Hero winner.
    ("20260809_124419", 105, "hero", True),
    ("20260809_124419", 106, "hero", True),

    # Independent July hand — lower-right winner.
    ("20260718_172832", 133, "seat_lower_right", True),
    ("20260718_172832", 134, "seat_lower_right", True),
    ("20260718_172832", 135, "seat_lower_right", True),

    # Independent July hand — upper-left winner.
    ("20260721_152123", 118, None, False),
    ("20260721_152123", 119, None, False),
    ("20260721_152123", 120, None, False),
    ("20260721_152123", 121, "seat_upper_left", True),
    ("20260721_152123", 122, "seat_upper_left", True),
    ("20260721_152123", 123, "seat_upper_left", True),
    ("20260721_152123", 124, "seat_upper_left", True),

    # Independent July hand — Hero winner.
    ("20260722_104530", 210, None, False),
    ("20260722_104530", 211, None, False),
    ("20260722_104530", 213, "hero", True),
    ("20260722_104530", 214, "hero", True),
    ("20260722_104530", 215, "hero", True),
]


def score_frame(session_name, frame, tmpl):
    path = (
        SESSIONS
        / session_name
        / f"{frame:04d}_full.png"
    )

    image = canonical_image(path)

    results = []

    for seat in STACK_REGIONS:
        word, _ = extract_bright_word(
            crop(
                image,
                winner_roi_for_seat(seat),
            )
        )

        score = similarity(
            tmpl,
            word,
        )

        if score is None:
            score = -1.0

        results.append(
            (
                float(score),
                seat,
            )
        )

    results.sort(reverse=True)

    return {
        "score": results[0][0],
        "seat": results[0][1],
        "second": results[1][0],
        "margin": (
            results[0][0]
            - results[1][0]
        ),
    }


def main():
    tmpl = template()

    failures = []

    print(
        "session frame expected "
        "best score margin"
    )

    for (
        session,
        frame,
        expected_seat,
        positive,
    ) in CASES:
        result = score_frame(
            session,
            frame,
            tmpl,
        )

        print(
            session,
            f"{frame:04d}",
            expected_seat or "NEGATIVE",
            result["seat"],
            f"{result['score']:.4f}",
            f"{result['margin']:.4f}",
        )

        if positive:
            if result["seat"] != expected_seat:
                failures.append(
                    (
                        session,
                        frame,
                        "wrong_seat",
                        result,
                    )
                )

    if failures:
        raise AssertionError(
            failures
        )

    print()
    print(
        "PASS winner ground truth: "
        "human-verified WINNER frames localize "
        "to the correct canonical seat"
    )


if __name__ == "__main__":
    main()
