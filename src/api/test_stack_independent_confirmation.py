def confirm_candidate(
    *,
    ordinary_candidates,
    independent_value,
    independent_votes,
    independent_confidence,
):
    if (
        independent_value is None
        or independent_votes < 3
        or independent_confidence < 0.95
    ):
        return None

    independent_value = float(independent_value)

    matches = [
        float(value)
        for value in ordinary_candidates
        if abs(
            float(value) - independent_value
        ) <= 0.001
    ]

    if not matches:
        return None

    return independent_value


def test_8220_independent_confirmation():
    result = confirm_candidate(
        ordinary_candidates=[82.20],
        independent_value=82.20,
        independent_votes=5,
        independent_confidence=0.98,
    )

    assert result == 82.20

    print(
        "PASS 82.20: ordinary single candidate "
        "independently confirmed 5/5"
    )


def test_7970_independent_confirmation():
    result = confirm_candidate(
        ordinary_candidates=[79.70],
        independent_value=79.70,
        independent_votes=5,
        independent_confidence=0.98,
    )

    assert result == 79.70

    print(
        "PASS 79.70: ordinary single candidate "
        "independently confirmed 5/5"
    )


def test_catastrophic_independent_disagreement_not_confirmed():
    result = confirm_candidate(
        ordinary_candidates=[
            90.84,
            50.84,
        ],
        independent_value=0.84,
        independent_votes=3,
        independent_confidence=0.98,
    )

    assert result is None

    print(
        "PASS safety: independent 0.84 does not "
        "confirm disagreeing ordinary evidence"
    )


def test_weak_independent_consensus_not_confirmed():
    result = confirm_candidate(
        ordinary_candidates=[82.20],
        independent_value=82.20,
        independent_votes=2,
        independent_confidence=0.98,
    )

    assert result is None

    print(
        "PASS safety: fewer than three independent "
        "votes cannot verify candidate"
    )


def main():
    test_8220_independent_confirmation()
    test_7970_independent_confirmation()
    test_catastrophic_independent_disagreement_not_confirmed()
    test_weak_independent_consensus_not_confirmed()

    print()
    print(
        "PASS independent confirmation contract"
    )


if __name__ == "__main__":
    main()
