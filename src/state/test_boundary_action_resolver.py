from src.state.boundary_stack_observation import (
    BoundaryStackObservation,
)
from src.state.boundary_action_resolver import (
    resolve_boundary_action,
)


def obs(
    *,
    street="PREFLOP",
    previous=100.0,
    observed=100.0,
    confidence=0.98,
    votes=2,
):
    return BoundaryStackObservation(
        street=street,
        seat="seat_x",
        previous_stack_bb=previous,
        observed_stack_bb=observed,
        confidence=confidence,
        votes=votes,
        mode="agreement_verified",
    )


def test_unchanged_stack_facing_bet_resolves_fold():
    result = resolve_boundary_action(
        obs(),
        owes_action=True,
        betting_open=True,
        current_price_bb=7.0,
        prior_live_commitment_bb=0.0,
    )

    assert result.resolved is True
    assert result.action == "FOLD"
    assert result.amount_bb is None


def test_exact_terminal_commitment_resolves_call():
    result = resolve_boundary_action(
        obs(
            previous=93.0,
            observed=87.0,
        ),
        owes_action=True,
        betting_open=True,
        current_price_bb=7.0,
        prior_live_commitment_bb=1.0,
    )

    assert result.resolved is True
    assert result.action == "CALL"
    assert result.amount_bb == 6.0


def test_prior_commitment_plus_delta_is_used():
    result = resolve_boundary_action(
        obs(
            previous=50.0,
            observed=49.0,
        ),
        owes_action=True,
        betting_open=True,
        current_price_bb=7.0,
        prior_live_commitment_bb=6.0,
    )

    assert result.resolved is True
    assert result.action == "CALL"
    assert result.amount_bb == 1.0


def test_exceeding_price_does_not_guess_raise():
    result = resolve_boundary_action(
        obs(
            previous=100.0,
            observed=90.0,
        ),
        owes_action=True,
        betting_open=True,
        current_price_bb=7.0,
        prior_live_commitment_bb=0.0,
    )

    assert result.resolved is False
    assert result.action is None
    assert "additional evidence" in result.reason


def test_short_commitment_does_not_guess_all_in_call():
    result = resolve_boundary_action(
        obs(
            previous=4.0,
            observed=0.0,
        ),
        owes_action=True,
        betting_open=True,
        current_price_bb=7.0,
        prior_live_commitment_bb=0.0,
    )

    assert result.resolved is False
    assert result.action is None


def test_postflop_unchanged_without_open_bet_resolves_check():
    result = resolve_boundary_action(
        obs(
            street="FLOP",
            previous=50.0,
            observed=50.0,
        ),
        owes_action=True,
        betting_open=False,
        current_price_bb=0.0,
        prior_live_commitment_bb=0.0,
    )

    assert result.resolved is True
    assert result.action == "CHECK"


def test_preflop_unopened_does_not_guess_check():
    result = resolve_boundary_action(
        obs(
            street="PREFLOP",
            previous=50.0,
            observed=50.0,
        ),
        owes_action=True,
        betting_open=False,
        current_price_bb=1.0,
        prior_live_commitment_bb=0.0,
    )

    assert result.resolved is False
    assert result.action is None


def test_untrusted_read_never_resolves():
    result = resolve_boundary_action(
        obs(
            confidence=0.50,
            votes=1,
        ),
        owes_action=True,
        betting_open=True,
        current_price_bb=7.0,
        prior_live_commitment_bb=0.0,
    )

    assert result.resolved is False
    assert result.action is None


def test_player_not_owing_action_never_resolves():
    result = resolve_boundary_action(
        obs(),
        owes_action=False,
        betting_open=True,
        current_price_bb=7.0,
        prior_live_commitment_bb=0.0,
    )

    assert result.resolved is False
    assert result.action is None


if __name__ == "__main__":
    tests = [
        test_unchanged_stack_facing_bet_resolves_fold,
        test_exact_terminal_commitment_resolves_call,
        test_prior_commitment_plus_delta_is_used,
        test_exceeding_price_does_not_guess_raise,
        test_short_commitment_does_not_guess_all_in_call,
        test_postflop_unchanged_without_open_bet_resolves_check,
        test_preflop_unopened_does_not_guess_check,
        test_untrusted_read_never_resolves,
        test_player_not_owing_action_never_resolves,
    ]

    for test in tests:
        test()

    print(
        "PASS boundary action resolver: "
        "trusted terminal stack evidence resolves only unique "
        "FOLD/CALL/CHECK cases; ambiguous raise/all-in cases remain unresolved"
    )
