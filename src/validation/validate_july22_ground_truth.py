from pathlib import Path
import json
import re
import sys


ROOT = Path(__file__).resolve().parents[2]

GROUND_TRUTH = (
    ROOT
    / "runtime/debug/action_sequence/20260722_152155/ground_truth.json"
)

CURRENT_HAND = (
    ROOT
    / "runtime/live/current_hand.txt"
)


def normalize(line):
    line = line.strip()

    line = re.sub(
        r"\([^)]*\)",
        "",
        line,
    )

    line = re.sub(
        r"\s+",
        " ",
        line,
    )

    return line.strip().upper()


def expected_text(action):
    position = action["position"]
    kind = action["action"]

    if kind == "FOLD":
        return f"{position} FOLDS"

    if kind == "CHECK":
        return f"{position} CHECKS"

    if kind == "BET":
        return (
            f"{position} BETS "
            f"{action['amount_bb']:g} BB"
        )

    if kind == "CALL":
        return (
            f"{position} CALLS "
            f"{action['amount_bb']:g} BB"
        )

    if kind == "RAISE":
        return (
            f"{position} "
            f"RAISES TO "
            f"{action['raise_to_bb']:g} BB"
        )

    raise ValueError(kind)


def match_action(line, expected):
    line = normalize(line)
    expected = normalize(expected)

    # Open/raise wording is semantically equivalent for the
    # first voluntary preflop raise.
    if "RAISES TO 2 BB" in expected:
        return (
            line == expected
            or line == expected.replace(
                "RAISES TO",
                "OPENS TO",
            )
        )

    return line == expected


def main():
    truth = json.loads(
        GROUND_TRUTH.read_text()
    )

    if not CURRENT_HAND.exists():
        raise SystemExit(
            "NO runtime/live/current_hand.txt"
        )

    raw_lines = [
        line.strip()
        for line in CURRENT_HAND.read_text().splitlines()
        if line.strip()
    ]

    cursor = 0
    passed = []
    failures = []

    for action in truth["actions"]:
        expected = expected_text(action)

        found = None

        for i in range(
            cursor,
            len(raw_lines),
        ):
            if match_action(
                raw_lines[i],
                expected,
            ):
                found = i
                break

        if found is None:
            failures.append({
                "index": action["index"],
                "street": action["street"],
                "expected": expected,
                "visual_frames": (
                    action["visual_frames"]
                ),
            })
            continue

        passed.append({
            "index": action["index"],
            "street": action["street"],
            "expected": expected,
            "line": raw_lines[found],
        })

        cursor = found + 1

    print("=" * 72)
    print("JULY 22 VISUAL GROUND-TRUTH VALIDATION")
    print("=" * 72)

    print()
    print(
        f"Matched: {len(passed)}/{len(truth['actions'])}"
    )

    for item in passed:
        print(
            f"PASS {item['index']:02d} "
            f"{item['street']:8s} "
            f"{item['expected']}"
        )

    if failures:
        print()
        print("===== FAILURES =====")

        for item in failures:
            frames = item["visual_frames"]

            print(
                f"FAIL {item['index']:02d} "
                f"{item['street']:8s} "
                f"{item['expected']}"
            )

            print(
                f"     visually established "
                f"frames {frames[0]}-{frames[-1]}"
            )

        print()
        print(
            f"FAILED: {len(failures)} "
            "ground-truth actions missing or out of order"
        )

        sys.exit(1)

    print()
    print(
        "PASS: all visually established actions "
        "appear in chronological order"
    )


if __name__ == "__main__":
    main()
