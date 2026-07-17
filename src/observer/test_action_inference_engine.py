from src.observer.action_inference_engine import (
    ActionInferenceEngine,
    BET_OR_RAISE,
    CALL,
    FOLD_OR_RESOLVED,
    UNKNOWN,
)


def episode(episode_id, evidence, confidence=0.8, seat="seat_mid_right"):
    return {
        "episode_id": episode_id,
        "seat": seat,
        "street": "PREFLOP",
        "closed": True,
        "confidence": confidence,
        "observation_types": evidence,
        "observations": [],
    }


engine = ActionInferenceEngine()

cases = [
    (
        episode(
            1,
            ["stack_changed", "bet_region_occupied", "pot_changed"],
            0.95,
        ),
        BET_OR_RAISE,
    ),
    (
        episode(
            2,
            ["stack_changed", "pot_changed"],
            0.65,
        ),
        CALL,
    ),
    (
        episode(
            3,
            ["bet_region_cleared"],
            0.35,
        ),
        FOLD_OR_RESOLVED,
    ),
    (
        episode(
            4,
            ["stack_changed"],
            0.40,
        ),
        UNKNOWN,
    ),
]

for item, expected in cases:
    result = engine.infer_episode(item)
    print(result.to_dict())
    assert result.action == expected, (
        result.action,
        expected,
    )

new_actions = engine.ingest_closed([item for item, _ in cases])
assert len(new_actions) == 4

# Duplicate episodes must not be emitted twice.
assert engine.ingest_closed([item for item, _ in cases]) == []

print()
print("ActionInferenceEngine smoke test passed.")
