from src.observer.action_inference_engine import (
    ActionInferenceEngine,
    CALL_OR_RAISE,
    UNKNOWN,
)


def quantitative_episode(
    *,
    episode_id,
    seat="hero",
    prior_committed=True,
    mature=True,
    mode="independent_confirmed",
    confidence=0.98,
):
    return {
        "episode_id": episode_id,
        "seat": seat,
        "street": "PREFLOP",
        "confidence": confidence,
        "evidence_mature": mature,
        "maturity_reason": (
            "quantitative_stack_commitment"
            if mature
            else "unknown"
        ),
        "observation_types": [
            "stack_changed",
        ],
        "observations": [
            {
                "type": "stack_changed",
                "ts": 10.0,
                "seat": seat,
                "street": "PREFLOP",
                "confidence": 1.0,
                "payload": {
                    "previous_stack_bb": 82.20,
                    "current_stack_bb": 79.70,
                    "delta_bb": 2.50,
                    "stack_read_confidence": confidence,
                    "stack_read_mode": mode,
                },
            },
        ],
        "table_context": {
            "positions": {
                "hero": "UTG+1",
                "seat_mid_left": "HJ",
            },
            "prior_voluntary_commitment_seats": (
                ["seat_mid_left"]
                if prior_committed
                else []
            ),
            "prior_occupied_bet_regions": (
                ["seat_mid_left"]
                if prior_committed
                else []
            ),
        },
    }


def test_validated_stack_only_facing_commitment_is_actionable():
    engine = ActionInferenceEngine()

    action = engine.infer_episode(
        quantitative_episode(
            episode_id=1,
            prior_committed=True,
        )
    )

    assert action.action == CALL_OR_RAISE, action

    print(
        "PASS quantitative stack-only commitment: "
        "validated Hero 82.20 -> 79.70 while facing "
        "prior voluntary action becomes CALL_OR_RAISE"
    )


def test_unvalidated_stack_only_remains_unknown():
    engine = ActionInferenceEngine()

    episode = quantitative_episode(
        episode_id=2,
        prior_committed=True,
        mature=False,
        mode="unresolved",
        confidence=0.40,
    )

    # Remove the trusted quantitative contract explicitly.
    episode["observations"][0]["payload"][
        "stack_read_confidence"
    ] = 0.40

    action = engine.infer_episode(
        episode
    )

    assert action.action == UNKNOWN, action

    print(
        "PASS safety: unvalidated stack-only evidence "
        "remains UNKNOWN"
    )


def main():
    test_validated_stack_only_facing_commitment_is_actionable()
    test_unvalidated_stack_only_remains_unknown()

    print()
    print(
        "PASS quantitative stack-only inference contract"
    )


if __name__ == "__main__":
    main()
