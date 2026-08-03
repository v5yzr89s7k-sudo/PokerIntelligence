from src.observer.action_inference_engine import (
    ActionInferenceEngine,
    BET_OR_RAISE,
)

episode = {
    "episode_id": 101,
    "seat": "hero",
    "street": "FLOP",
    "closed": True,
    "confidence": 0.80,
    "observation_types": [
        "bet_region_occupied",
        "stack_changed",
        "bet_region_cleared",
    ],
    "observations": [
        {
            "type": "bet_region_cleared",
            "ts": 103.0,
            "payload": {"cleared": True},
        },
        {
            "type": "stack_changed",
            "ts": 102.0,
            "payload": {"delta_bb": 2.5},
        },
        {
            "type": "bet_region_occupied",
            "ts": 101.0,
            "payload": {"occupied": True},
        },
    ],
}

engine = ActionInferenceEngine()
result = engine.infer_episode(episode)

assert result.action == BET_OR_RAISE

timeline = result.measurements["timeline"]

assert [item["type"] for item in timeline] == [
    "bet_region_occupied",
    "stack_changed",
    "bet_region_cleared",
]

assert [item["ts"] for item in timeline] == [
    101.0,
    102.0,
    103.0,
]

assert [item["offset_ms"] for item in timeline] == [
    0.0,
    1000.0,
    2000.0,
]

assert result.measurements["timeline_types"] == [
    "bet_region_occupied",
    "stack_changed",
    "bet_region_cleared",
]

assert result.measurements["timeline_duration_ms"] == 2000.0

print("Temporal inference timeline test passed.")

invalid_order_episode = {
    **episode,
    "episode_id": 102,
    "observations": [
        {
            "type": "stack_changed",
            "ts": 101.0,
            "payload": {"delta_bb": 2.5},
        },
        {
            "type": "bet_region_occupied",
            "ts": 102.0,
            "payload": {"occupied": True},
        },
    ],
}

invalid_result = engine.infer_episode(invalid_order_episode)

assert invalid_result.action == "UNKNOWN", invalid_result.to_dict()

print("Temporal commitment order test passed.")

pending_stack_episode = {
    **episode,
    "episode_id": 103,
    "observations": [
        {
            "type": "stack_changed",
            "ts": 101.0,
            "payload": {"delta_bb": 2.5},
        },
        {
            "type": "bet_region_occupied",
            "ts": 101.5,
            "payload": {"occupied": True},
        },
    ],
}

pending_stack_result = engine.infer_episode(
    pending_stack_episode
)

assert pending_stack_result.action == BET_OR_RAISE
assert (
    pending_stack_result.measurements["stack_lead_ms"]
    == 500.0
)

stale_stack_episode = {
    **episode,
    "episode_id": 104,
    "observations": [
        {
            "type": "stack_changed",
            "ts": 101.0,
            "payload": {"delta_bb": 2.5},
        },
        {
            "type": "bet_region_occupied",
            "ts": 102.0,
            "payload": {"occupied": True},
        },
    ],
}

stale_stack_result = engine.infer_episode(
    stale_stack_episode
)

assert stale_stack_result.action == "UNKNOWN"
assert (
    stale_stack_result.measurements["stack_lead_ms"]
    == 1000.0
)

print("Pending-stack temporal window test passed.")
