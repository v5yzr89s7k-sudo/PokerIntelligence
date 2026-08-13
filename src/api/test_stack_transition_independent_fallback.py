from src.vision.stack_candidate_resolver import (
    resolve_stack_candidates,
)


def test_stable_independent_candidate_can_recover_transition():
    previous = 83.20

    ordinary_candidates = [
        93.20,
        3.20,
    ]

    independent_candidate = 82.20

    result = resolve_stack_candidates(
        candidates=(
            ordinary_candidates
            + [independent_candidate]
        ),
        previous_stack_bb=previous,
    )

    assert result.resolved is True, result
    assert result.value == 82.20, result

    print(
        "PASS transition fallback: "
        "canonical continuity selects stable "
        "82.20 independent candidate from noisy OCR"
    )


def test_catastrophic_independent_candidate_is_not_forced():
    previous = 50.84

    ordinary_candidates = [
        90.84,
        50.84,
    ]

    independent_candidate = 0.84

    result = resolve_stack_candidates(
        candidates=(
            ordinary_candidates
            + [independent_candidate]
        ),
        previous_stack_bb=previous,
    )

    assert result.resolved is True, result
    assert result.value == 50.84, result

    print(
        "PASS safety: catastrophic independent "
        "0.84 candidate does not override continuity"
    )


def main():
    test_stable_independent_candidate_can_recover_transition()
    test_catastrophic_independent_candidate_is_not_forced()


if __name__ == "__main__":
    main()
