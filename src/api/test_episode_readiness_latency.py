import time

from src.api.api_event_coordinator import (
    episode_ready_for_inference,
)
from src.observer.action_episode_manager import (
    LATE_STACK_ATTACH_SECONDS,
)


def make_episode(
    *,
    street,
    age_seconds,
    evidence=None,
):
    now = time.time()

    return {
        "episode_id": 1,
        "seat": "seat_top",
        "street": street,
        "closed": True,
        "started_ts": now - age_seconds - 1.0,
        "ended_ts": now - age_seconds,
        "observation_types": (
            evidence
            or ["bet_region_occupied"]
        ),
        "table_context": {
            "positions": {
                "seat_top": "HJ",
            },
        },
    }


assert episode_ready_for_inference(
    make_episode(
        street="FLOP",
        age_seconds=0.40,
    )
) is False

assert episode_ready_for_inference(
    make_episode(
        street="FLOP",
        age_seconds=0.90,
    )
) is True

assert episode_ready_for_inference(
    make_episode(
        street="PREFLOP",
        age_seconds=0.90,
    )
) is False

assert episode_ready_for_inference(
    make_episode(
        street="PREFLOP",
        age_seconds=LATE_STACK_ATTACH_SECONDS + 0.10,
    )
) is True

assert episode_ready_for_inference(
    make_episode(
        street="TURN",
        age_seconds=0.05,
        evidence=[
            "bet_region_occupied",
            "stack_changed",
        ],
    )
) is True

print("Episode readiness latency regression passed.")
