from dataclasses import replace

from src.v017.synthetic_lab.scenario_factory import (
    validate_scenario,
)
from src.v017.synthetic_lab.scenarios import (
    PREFLOP_OPEN_FOLDS,
    PREFLOP_SCENARIOS,
    POSTFLOP_SCENARIOS,
    SCENARIOS,
)


def expect_invalid(scenario, label):
    try:
        validate_scenario(scenario)
    except AssertionError:
        print(label, "REJECTED")
        return

    raise AssertionError(
        f"invalid scenario accepted: {label}"
    )


def main():
    scenario = PREFLOP_OPEN_FOLDS

    assert scenario.name == "preflop_open_folds"
    assert len(scenario.players) == 4
    assert len(scenario.evidence) == 5
    assert len(scenario.expected_actions) == 6
    assert len(
        scenario.expected_publications
    ) == 4

    expected_registry = (
        "preflop_open_folds",
        "preflop_open_call",
        "preflop_three_bet_call",
        "preflop_sb_complete",
        "preflop_short_allin",
        "flop_check_check",
        "flop_bet_fold",
        "flop_bet_call",
        "flop_raise_call",
    )

    expected_preflop = expected_registry[:5]
    expected_postflop = expected_registry[5:]

    assert tuple(
        item.name
        for item in PREFLOP_SCENARIOS
    ) == expected_preflop

    assert tuple(
        item.name
        for item in POSTFLOP_SCENARIOS
    ) == expected_postflop

    assert (
        SCENARIOS
        == PREFLOP_SCENARIOS
        + POSTFLOP_SCENARIOS
    )

    assert tuple(
        item.name
        for item in SCENARIOS
    ) == expected_registry

    for registered in SCENARIOS:
        assert (
            validate_scenario(registered)
            is registered
        )

    # Model must reject chronology regressions.
    expect_invalid(
        replace(
            scenario,
            evidence=tuple(
                reversed(
                    scenario.evidence
                )
            ),
        ),
        "reverse evidence chronology",
    )

    # Model must reject publication regression.
    publications = list(
        scenario.expected_publications
    )

    publications[2] = replace(
        publications[2],
        action_count=2,
    )

    expect_invalid(
        replace(
            scenario,
            expected_publications=tuple(
                publications
            ),
        ),
        "publication action regression",
    )

    # Model must reject Hero ownership ambiguity.
    players = list(scenario.players)

    players[0] = replace(
        players[0],
        is_hero=True,
    )

    expect_invalid(
        replace(
            scenario,
            players=tuple(players),
        ),
        "multiple heroes",
    )

    print()
    print(
        "V0.17 SYNTHETIC LAB GENERIC "
        "SCENARIO MODEL: PASS"
    )


if __name__ == "__main__":
    main()
