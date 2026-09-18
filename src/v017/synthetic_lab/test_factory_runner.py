import hashlib

from src.v017.synthetic_lab.factory_comparator import (
    compare_factory_run,
)
from src.v017.synthetic_lab.factory_runner import (
    run_factory_scenario,
)
from src.v017.synthetic_lab.scenarios import (
    PREFLOP_OPEN_FOLDS,
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


def main():
    scenario = PREFLOP_OPEN_FOLDS

    runs = tuple(
        run_factory_scenario(scenario)
        for _ in range(3)
    )

    for index, run in enumerate(
        runs,
        1,
    ):
        result = compare_factory_run(
            scenario,
            run,
        )

        print()
        print(
            f"===== FACTORY RUN {index} ====="
        )

        for publication in run.publications:
            print(
                f"frame={publication.frame}",
                f"street={publication.street}",
                f"actions={publication.action_count}",
                f"next={publication.next_actor}",
            )

        print(
            "final actions =",
            run.final_actions,
        )

        print(
            "digest =",
            digest(run),
        )

        if not result.passed:
            for error in result.errors:
                print("FAIL:", error)

        assert result.passed, result.errors

    digests = tuple(
        digest(run)
        for run in runs
    )

    assert len(set(digests)) == 1
    assert (
        runs[0].publications
        == runs[1].publications
        == runs[2].publications
    )
    assert (
        runs[0].final_actions
        == runs[1].final_actions
        == runs[2].final_actions
    )

    print()
    print(
        "V0.17 SYNTHETIC LAB GENERIC "
        "FACTORY RUNNER 3/3: PASS"
    )


if __name__ == "__main__":
    main()
