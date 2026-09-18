from src.v017.synthetic_lab.runner import (
    run_july22,
)
from src.v017.synthetic_lab.comparator import (
    compare_july22,
)
from src.v017.synthetic_lab.run_suite import (
    digest_run,
)


def main():
    first = run_july22()
    second = run_july22()
    third = run_july22()

    for run in (first, second, third):
        result = compare_july22(run)
        assert result.passed, result.errors

    digests = (
        digest_run(first),
        digest_run(second),
        digest_run(third),
    )

    print("digests =", digests)

    assert len(set(digests)) == 1

    assert (
        first.final_actions
        == second.final_actions
        == third.final_actions
    )

    assert (
        first.publications
        == second.publications
        == third.publications
    )

    print()
    print(
        "SYNTHETIC LAB NARRATOR "
        "DETERMINISM 3/3: PASS"
    )


if __name__ == "__main__":
    main()
