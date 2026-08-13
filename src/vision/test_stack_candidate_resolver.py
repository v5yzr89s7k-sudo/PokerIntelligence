from src.vision.stack_candidate_resolver import (
    resolve_stack_candidates,
)


def test_replay_0002_initial_disagreement_is_not_guessed():
    result = resolve_stack_candidates(
        [99.41, 99.41, 55.41],
        previous_stack_bb=None,
    )

    assert result.resolved is False
    assert result.value is None
    assert (
        result.reason
        == "candidate_disagreement_without_baseline"
    )


def test_replay_0002_transition_uses_continuity():
    result = resolve_stack_candidates(
        [3.41, 93.41, 93.41, 53.41],
        previous_stack_bb=55.41,
        maximum_drop_bb=12.0,
    )

    assert result.resolved is True
    assert result.value == 53.41
    assert round(result.distance, 2) == 2.0


def test_replay_0001_bb_uses_continuity():
    result = resolve_stack_candidates(
        [96.6, 96.6, 56.6],
        previous_stack_bb=65.6,
        maximum_drop_bb=12.0,
    )

    assert result.resolved is True
    assert result.value == 56.6
    assert round(result.distance, 2) == 9.0


def test_replay_0001_hero_does_not_choose_catastrophic_psm13():
    result = resolve_stack_candidates(
        [90.84, 90.84, 50.84, 0.84, 80.84],
        previous_stack_bb=50.84,
        maximum_drop_bb=12.0,
    )

    assert result.resolved is True
    assert result.value == 50.84
    assert result.distance == 0.0


def test_stack_increase_is_not_selected():
    result = resolve_stack_candidates(
        [93.41, 99.41],
        previous_stack_bb=55.41,
        maximum_drop_bb=12.0,
    )

    assert result.resolved is False
    assert result.value is None
    assert result.reason == "all_candidates_increase_stack"


def test_clean_single_candidate_remains_valid():
    result = resolve_stack_candidates(
        [65.6, 65.6, 65.6],
        previous_stack_bb=None,
    )

    assert result.resolved is True
    assert result.value == 65.6


def main():
    tests = [
        test_replay_0002_initial_disagreement_is_not_guessed,
        test_replay_0002_transition_uses_continuity,
        test_replay_0001_bb_uses_continuity,
        test_replay_0001_hero_does_not_choose_catastrophic_psm13,
        test_stack_increase_is_not_selected,
        test_clean_single_candidate_remains_valid,
    ]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print()
    print(
        "PASS stack candidate resolver: "
        "OCR-family agreement does not override canonical continuity; "
        "disagreement without a baseline remains unresolved"
    )


if __name__ == "__main__":
    main()
