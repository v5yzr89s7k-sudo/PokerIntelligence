from src.state.boundary_action_resolver import (
    resolve_boundary_action,
)
from src.state.boundary_stack_observation import (
    BoundaryStackObservation,
)


def make_observation(delta):
    return BoundaryStackObservation(
        seat="hero",
        street="FLOP",
        previous_stack_bb=11.78,
        observed_stack_bb=round(11.78 - delta, 2),
        confidence=0.99,
        votes=3,
    )


def main():
    # July 22 case:
    # raw stack evidence says 3.38 BB,
    # established betting price says 3.37 BB.
    observation = make_observation(3.38)

    result = resolve_boundary_action(
        observation,
        owes_action=True,
        betting_open=True,
        current_price_bb=3.37,
        prior_live_commitment_bb=0.0,
    )

    print("===== JULY 22 CALL NORMALIZATION =====")
    print("raw delta:", observation.delta_bb)
    print("canonical action:", result.action)
    print("canonical amount:", result.amount_bb)

    assert result.resolved
    assert result.action == "CALL"
    assert abs(observation.delta_bb - 3.38) < 0.001
    assert abs(result.amount_bb - 3.37) < 0.001

    # Existing partial-commitment semantics must remain correct:
    # player already has 0.5 BB live and calls a 2.5 BB price.
    partial = make_observation(2.01)

    partial_result = resolve_boundary_action(
        partial,
        owes_action=True,
        betting_open=True,
        current_price_bb=2.5,
        prior_live_commitment_bb=0.5,
    )

    print()
    print("===== PARTIAL COMMITMENT NORMALIZATION =====")
    print("raw delta:", partial.delta_bb)
    print("prior live:", 0.5)
    print("price:", 2.5)
    print("canonical amount:", partial_result.amount_bb)

    assert partial_result.resolved
    assert partial_result.action == "CALL"
    assert abs(partial_result.amount_bb - 2.0) < 0.001

    # Outside tolerance must NOT be silently converted into a CALL.
    outside = make_observation(3.50)

    outside_result = resolve_boundary_action(
        outside,
        owes_action=True,
        betting_open=True,
        current_price_bb=3.37,
        prior_live_commitment_bb=0.0,
    )

    print()
    print("===== OUTSIDE TOLERANCE =====")
    print("raw delta:", outside.delta_bb)
    print("resolved:", outside_result.resolved)
    print("action:", outside_result.action)

    assert not outside_result.resolved
    assert outside_result.action is None

    print()
    print(
        "PASS: exact-price CALL uses established betting price; "
        "raw stack measurement remains evidence; "
        "outside-tolerance evidence remains unresolved"
    )


if __name__ == "__main__":
    main()
