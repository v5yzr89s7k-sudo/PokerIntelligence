from pathlib import Path

from src.vision.winner_normalized_probe import (
    canonical_image,
)

from src.vision.winner_detector import (
    detect_winner,
    WINNER_SCORE_THRESHOLD,
)


ROOT = Path(__file__).resolve().parents[2]

SESSIONS = (
    ROOT
    / "runtime/debug/action_sequence"
)


# Human-verified clean positives.
POSITIVES = [
    ("20260809_124419", 105, "hero"),

    ("20260718_172832", 133, "seat_lower_right"),
    ("20260718_172832", 134, "seat_lower_right"),
    ("20260718_172832", 135, "seat_lower_right"),

    ("20260721_152123", 121, "seat_upper_left"),
    ("20260721_152123", 122, "seat_upper_left"),
    ("20260721_152123", 123, "seat_upper_left"),
    ("20260721_152123", 124, "seat_upper_left"),

    ("20260722_104530", 213, "hero"),
    ("20260722_104530", 214, "hero"),
    ("20260722_104530", 215, "hero"),
]


# Human-verified ordinary river frames immediately before WINNER.
NEGATIVES = [
    ("20260721_152123", 118),
    ("20260721_152123", 119),
    ("20260721_152123", 120),

    ("20260722_104530", 210),
    ("20260722_104530", 211),
]


def image(session, frame):
    return canonical_image(
        SESSIONS
        / session
        / f"{frame:04d}_full.png"
    )


def test_verified_positives():
    for session, frame, expected_seat in POSITIVES:
        result = detect_winner(
            image(session, frame)
        )

        assert result["visible"], (
            session,
            frame,
            result,
        )

        assert result["seat"] == expected_seat, (
            session,
            frame,
            expected_seat,
            result,
        )

        print(
            "PASS POSITIVE",
            session,
            f"{frame:04d}",
            expected_seat,
            f"score={result['score']:.4f}",
        )


def test_verified_negatives():
    for session, frame in NEGATIVES:
        result = detect_winner(
            image(session, frame)
        )

        assert not result["visible"], (
            session,
            frame,
            result,
        )

        print(
            "PASS NEGATIVE",
            session,
            f"{frame:04d}",
            f"score={result['score']:.4f}",
        )


def main():
    print(
        "winner threshold:",
        WINNER_SCORE_THRESHOLD,
    )

    test_verified_positives()
    test_verified_negatives()

    print()
    print(
        "PASS winner detector: human-verified "
        "WINNER frames localize to the correct canonical "
        "seat while verified ordinary river frames remain negative"
    )


if __name__ == "__main__":
    main()
