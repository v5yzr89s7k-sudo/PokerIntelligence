import hashlib

from src.v017.synthetic_lab.runner import (
    run_july22,
)
from src.v017.synthetic_lab.comparator import (
    compare_july22,
)


def digest_run(run):
    payload = "\n".join(
        [
            str(run.frame_count),
            repr(run.final_actions),
            *[
                (
                    f"{row.frame}|"
                    f"{row.street}|"
                    f"{row.action_count}|"
                    f"{row.next_actor}|"
                    f"{row.text}"
                )
                for row in run.publications
            ],
        ]
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def main():
    print(
        "============================================================"
    )
    print(
        "V0.17 SYNTHETIC ACR LAB"
    )
    print(
        "CONTROLLED NARRATOR — JULY22 BASELINE"
    )
    print(
        "============================================================"
    )

    run = run_july22()
    comparison = compare_july22(run)

    print()
    print("===== OBSERVER NARRATION =====")

    previous_count = 0

    for index, snapshot in enumerate(
        run.publications,
        1,
    ):
        print(
            f"{index:02d}",
            f"frame={snapshot.frame:03d}",
            f"street={snapshot.street}",
            f"actions={snapshot.action_count}",
            f"new_actions="
            f"{snapshot.action_count - previous_count}",
            f"next={snapshot.next_actor}",
        )

        previous_count = snapshot.action_count

    print()
    print("===== FINAL SEMANTIC ACTIONS =====")

    for index, action in enumerate(
        run.final_actions,
        1,
    ):
        print(index, *action)

    print()
    print("===== FINAL CURRENT_HAND =====")
    print(run.final_text)

    print("===== COMPARISON =====")

    if comparison.passed:
        print("GROUND TRUTH vs OBSERVER: PASS")
    else:
        print("GROUND TRUTH vs OBSERVER: FAIL")

        for error in comparison.errors:
            print("FAIL:", error)

    print()
    print("frames =", run.frame_count)
    print(
        "publications =",
        len(run.publications),
    )
    print(
        "final actions =",
        len(run.final_actions),
    )
    print(
        "digest =",
        digest_run(run),
    )

    if not comparison.passed:
        raise SystemExit(1)

    print()
    print(
        "SYNTHETIC LAB JULY22 BASELINE: PASS"
    )


if __name__ == "__main__":
    main()
