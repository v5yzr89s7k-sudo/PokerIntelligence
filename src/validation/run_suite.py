from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.validation.compare_output import compare_output
from src.validation.golden_hand import discover_golden_hands
from src.validation.event_replay import (
    EventReplayError,
    replay,
)


def main():

    hands = discover_golden_hands()

    if not hands:
        print("No golden hands found.")
        print()
        print(
            "Expected:")
        print(
            "    runtime/golden_hands/hand_xxxx/"
        )
        return 0

    print("=" * 60)
    print("Poker Intelligence Validation Suite")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for hand in hands:

        print(f"{hand.name} ... ", end="", flush=True)

        try:
            generated = replay(
                hand.events_path
            )

            comparison = compare_output(
                hand.expected_current_hand(),
                generated,
            )

        except EventReplayError as exc:
            print("ERROR")
            print(exc)
            print()
            failed += 1
            continue

        except Exception as exc:
            print("ERROR")
            print(exc)
            print()
            failed += 1
            continue

        if comparison.passed:
            print("PASS")
            passed += 1
        else:
            print("FAIL")
            print()
            print(comparison.format())
            print()
            failed += 1

    print("-" * 60)
    print(
        f"Passed: {passed}"
    )
    print(
        f"Failed: {failed}"
    )
    print(
        f"Total : {passed + failed}"
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
