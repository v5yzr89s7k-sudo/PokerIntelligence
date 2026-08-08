from src.observer.action_inference_engine import (
    ActionInferenceEngine,
    BET_OR_RAISE,
)


def episode(seat, position):
    return {
        "episode_id": 1,
        "seat": seat,
        "street": "PREFLOP",
        "confidence": 0.75,
        "closed": True,
        "observation_types": [
            "bet_region_occupied",
            "stack_changed",
        ],
        "observations": [
            {
                "type": "bet_region_occupied",
                "ts": 10.0,
                "payload": {},
            },
            {
                "type": "stack_changed",
                "ts": 10.1,
                "payload": {
                    "delta_bb": 1.0,
                },
            },
        ],
        "table_context": {
            "positions": {
                seat: position,
            },
            "prior_voluntary_commitment_seats": [],
            "prior_occupied_bet_regions": [],
        },
    }


engine = ActionInferenceEngine()

sb = engine.infer_episode(
    episode("hero", "SB")
)

assert sb.action == BET_OR_RAISE, sb
assert "small blind" not in sb.reason.lower(), sb

bb = engine.infer_episode(
    {
        **episode("seat_lower_left", "BB"),
        "episode_id": 2,
    }
)

assert bb.action == BET_OR_RAISE, bb
assert "big blind" not in bb.reason.lower(), bb

print(
    "Forced-blind ownership regression passed: "
    "SB/BB episodes remain voluntary candidates."
)
