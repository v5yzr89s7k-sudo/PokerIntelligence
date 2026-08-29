"""
Regression:

At a confirmed next-street boundary, an explicit retrospective stack
observation that cannot itself classify an action must not permanently
veto a uniquely implied passive CHECK when:

- the old street is postflop and unopened;
- the seat still owes action;
- there is no unresolved quantitative stack candidate;
- there is no preserved qualified commitment action.

This is the July 22 TURN Hero case.
"""

import src.api.api_event_state_machine as sm


def main():

    print(
        "===== CONTRACT ====="
    )

    # The existing passive resolver already has a controlled mechanism
    # for reconsidering an observed seat after quantitative ambiguity
    # has disappeared.
    #
    # The missing semantic distinction is whether an unresolved
    # boundary observation still owns any quantitative blocker.

    observed_seats = {
        "hero",
    }

    unresolved_candidates = set()

    preserved_actions = {}

    betting_open = False

    street = "TURN"

    hero_has_quantitative_blocker = (
        "hero" in unresolved_candidates
        or "hero" in preserved_actions
    )

    print(
        "street:",
        street,
    )

    print(
        "observed:",
        sorted(observed_seats),
    )

    print(
        "quantitative blocker:",
        hero_has_quantitative_blocker,
    )

    print(
        "betting open:",
        betting_open,
    )

    assert hero_has_quantitative_blocker is False

    assert betting_open is False

    helper = getattr(
        sm,
        "boundary_observation_must_block_passive_resolution",
        None,
    )

    assert helper is not None, (
        "RED: unresolved explicit boundary observations are "
        "treated as unconditional passive-action vetoes; "
        "there is no arbitration against surviving quantitative "
        "commitment ownership"
    )

    blocked = helper(
        seat="hero",
        observed_seats=observed_seats,
        unresolved_candidates=unresolved_candidates,
        preserved_actions=preserved_actions,
        reconsider_observed_after_candidate_release=False,
    )

    print(
        "blocked:",
        blocked,
    )

    assert blocked is False, (
        "RED: unclassifiable Hero boundary observation still "
        "vetoes uniquely implied TURN CHECK despite no surviving "
        "quantitative commitment evidence"
    )

    # Genuine unresolved quantitative ownership must still block.
    blocked = helper(
        seat="hero",
        observed_seats=observed_seats,
        unresolved_candidates={"hero"},
        preserved_actions=preserved_actions,
        reconsider_observed_after_candidate_release=False,
    )

    print(
        "blocked with unresolved candidate:",
        blocked,
    )

    assert blocked is True, (
        "REGRESSION: unresolved quantitative stack ownership "
        "no longer protects boundary action classification"
    )

    # A preserved qualified action must also remain authoritative.
    blocked = helper(
        seat="hero",
        observed_seats=observed_seats,
        unresolved_candidates=set(),
        preserved_actions={"hero": object()},
        reconsider_observed_after_candidate_release=False,
    )

    print(
        "blocked with preserved action:",
        blocked,
    )

    assert blocked is True, (
        "REGRESSION: preserved qualified action no longer "
        "protects boundary reconciliation"
    )

    print(
        "PASS boundary observation arbitration contract"
    )


if __name__ == "__main__":
    main()
