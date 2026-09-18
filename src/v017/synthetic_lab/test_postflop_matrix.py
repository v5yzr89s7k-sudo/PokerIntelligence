import hashlib

from src.v017.synthetic_lab.factory_comparator import (
    compare_factory_run,
)
from src.v017.synthetic_lab.factory_runner import (
    run_factory_scenario,
)
from src.v017.synthetic_lab.scenarios import (
    POSTFLOP_SCENARIOS,
)


def digest(run):
    payload = "\n".join(
        (
            run.scenario,
            repr(run.final_actions),
            *(
                (
                    f"{row.frame}|"
                    f"{row.street}|"
                    f"{row.action_count}|"
                    f"{row.next_actor}|"
                    f"{row.text}"
                )
                for row in run.publications
            ),
        )
    )
    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def run_matrix_once(run_number):
    print()
    print(
        f"===== POSTFLOP MATRIX RUN "
        f"{run_number} ====="
    )

    results = []

    for scenario in POSTFLOP_SCENARIOS:
        run = run_factory_scenario(scenario)
        comparison = compare_factory_run(
            scenario,
            run,
        )
        run_digest = digest(run)

        print()
        print(f"SCENARIO: {scenario.name}")

        for publication in run.publications:
            print(
                f"  frame={publication.frame}",
                f"street={publication.street}",
                f"actions={publication.action_count}",
                f"next={publication.next_actor}",
            )

        print(
            "  final actions =",
            run.final_actions,
        )
        print(
            "  digest =",
            run_digest,
        )

        if not comparison.passed:
            for error in comparison.errors:
                print("  FAIL:", error)

        assert comparison.passed, (
            scenario.name,
            comparison.errors,
        )

        results.append(
            (
                scenario.name,
                run_digest,
                run.publications,
                run.final_actions,
            )
        )

    return tuple(results)


def main():
    runs = tuple(
        run_matrix_once(index)
        for index in range(1, 4)
    )

    assert runs[0] == runs[1] == runs[2], (
        "postflop matrix is nondeterministic"
    )

    print()
    print(
        "V0.17 SYNTHETIC LAB POSTFLOP "
        "MATRIX 3/3: PASS"
    )


if __name__ == "__main__":
    main()
