import time

from src.observer.action_episode_manager import (
    ActionEpisodeManager,
)
from src.observer.action_inference_engine import (
    ActionInferenceEngine,
)
from src.observer.street_episode_scheduler import (
    StreetEpisodeScheduler,
)
from src.observer.observation_types import (
    Observation,
    BET_REGION_OCCUPIED,
    STACK_CHANGED,
)
from src.api.api_event_coordinator import (
    episode_ready_for_inference,
)


SEAT = "seat_lower_right"


def main():

    manager = ActionEpisodeManager(
        idle_timeout=0.01,
        settle_timeout=0.01,
        late_stack_attach_seconds=2.75,
    )

    scheduler = StreetEpisodeScheduler()
    inference = ActionInferenceEngine()

    context = {
        "phase": "PREFLOP",
        "hand_started_at": 1000.0,
        "hero_position": "SB",
        "positions": {
            "seat_mid_left": "UTG",
            "seat_upper_left": "LJ",
            "seat_upper_right": "HJ",
            "seat_mid_right": "CO",
            "seat_lower_right": "BTN",
            "hero": "SB",
            "seat_lower_left": "BB",
        },
        "prior_voluntary_commitment_seats": [],
        "prior_occupied_bet_regions": [],
    }

    manager.set_table_context(context)

    started = time.time()

    print("===== OPEN BTN VISUAL EPISODE =====")

    manager.ingest([
        Observation(
            type=BET_REGION_OCCUPIED,
            ts=started,
            street="PREFLOP",
            seat=SEAT,
            confidence=0.35,
            payload={
                "bet_amount_bb": 2.0,
            },
        )
    ])

    manager.close_idle(
        started + 0.02
    )

    assert len(manager.closed) == 1

    episode = manager.closed[0]

    print(
        "episode:",
        episode.episode_id,
    )
    print(
        "started_ts:",
        episode.started_ts,
    )
    print(
        "ended_ts:",
        episode.ended_ts,
    )
    print(
        "evidence_mature:",
        episode.evidence_mature,
    )

    assert episode.closed
    assert not episode.evidence_mature

    print()
    print("===== BEFORE LATE STACK =====")

    released = scheduler.release(
        manager.closed,
        ready_for_inference=(
            episode_ready_for_inference
        ),
        processed_episode_ids=(
            inference.processed_episode_ids
        ),
    )

    print(
        "released:",
        [
            ep.episode_id
            for ep in released
        ],
    )

    assert released == [], (
        "visual-only BTN episode should wait "
        "for late stack evidence"
    )

    print()
    print("===== ATTACH VALIDATED BTN STACK =====")

    stack_ts = (
        float(episode.ended_ts)
        + 0.50
    )

    manager.ingest([
        Observation(
            type=STACK_CHANGED,
            ts=stack_ts,
            street="PREFLOP",
            seat=SEAT,
            confidence=0.95,
            payload={
                "previous_stack_bb": 58.55,
                "current_stack_bb": 56.55,
                "delta_bb": 2.0,
                "stack_read_confidence": 0.95,
                "stack_read_mode": (
                    "agreement_verified"
                ),
            },
        )
    ])

    episode = manager.closed[0]

    print(
        "ended_ts:",
        episode.ended_ts,
    )
    print(
        "stack_ts:",
        stack_ts,
    )
    print(
        "late age:",
        stack_ts
        - float(episode.ended_ts),
    )
    print(
        "types:",
        [
            item.get("type")
            for item in episode.observations
        ],
    )
    print(
        "mature:",
        episode.evidence_mature,
    )
    print(
        "maturity_reason:",
        episode.maturity_reason,
    )

    reinference_ids = (
        manager.consume_reinference_episode_ids()
    )

    print(
        "reinference_ids:",
        sorted(reinference_ids),
    )

    assert (
        episode.episode_id
        in reinference_ids
    ), (
        "REPRODUCED: late stack attached but "
        "reinference was not requested"
    )

    assert episode.evidence_mature, (
        "REPRODUCED: late validated stack did "
        "not mature BTN episode"
    )

    print()
    print("===== SCHEDULER AFTER LATE STACK =====")

    released = scheduler.release(
        manager.closed,
        ready_for_inference=(
            episode_ready_for_inference
        ),
        processed_episode_ids=(
            inference.processed_episode_ids
        ),
    )

    print(
        "released:",
        [
            ep.episode_id
            for ep in released
        ],
    )

    assert (
        episode in released
    ), (
        "REPRODUCED: mature late-stack BTN "
        "episode was not released"
    )

    print()
    print("===== INFERENCE =====")

    actions = inference.ingest_closed(
        released
    )

    print(
        "action count:",
        len(actions),
    )

    for action in actions:
        print(
            action.to_dict()
        )

    assert len(actions) == 1, (
        "REPRODUCED: released mature BTN "
        "episode produced no inferred action"
    )

    action = actions[0]

    assert action.seat == SEAT
    assert action.street == "PREFLOP"

    assert action.action == "BET_OR_RAISE", (
        "REPRODUCED: BTN 2 BB commitment "
        f"inferred as {action.action}"
    )

    stack = (
        action.measurements
        .get("stack_change")
        or {}
    )

    assert (
        round(
            float(
                stack.get("delta_bb")
                or 0.0
            ),
            2,
        )
        == 2.0
    )

    print()
    print(
        "PASS: closed BTN episode + late "
        "validated stack reaches BET_OR_RAISE"
    )


if __name__ == "__main__":
    main()
