from unittest.mock import patch

from src.observer.action_episode_manager import (
    ActionEpisodeManager,
)
from src.observer.action_inference_engine import (
    ActionInferenceEngine,
    CALL_OR_RAISE,
)
from src.observer.observation_types import (
    Observation,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
    STACK_CHANGED,
)


POSITIONS = {
    "seat_upper_left": "UTG",
    "seat_top": "UTG+1",
    "seat_mid_right": "HJ",
    "seat_lower_right": "CO",
    "hero": "BTN",
    "seat_lower_left": "SB",
    "seat_mid_left": "BB",
}


def main():
    manager = ActionEpisodeManager(
        idle_timeout=1.25,
        settle_timeout=0.80,
    )

    manager.set_table_context({
        "phase": "PREFLOP",
        "positions": POSITIONS,
        "hero_position": "BTN",

        # Hero has already opened to 3.5 BB.
        # This is prior VOLUNTARY commitment.
        "prior_voluntary_commitment_seats": [
            "hero",
        ],

        # BB's blind chips may already occupy its visual bet region.
        # Blind occupancy must not itself be interpreted as prior voluntary
        # action.
        "prior_occupied_bet_regions": [
            "seat_mid_left",
        ],
    })

    # BB action begins.
    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=10.0,
    ):
        manager.ingest([
            Observation(
                type=BET_REGION_OCCUPIED,
                ts=10.0,
                street="PREFLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={
                    "occupied": True,
                },
            ),
        ])

    assert "seat_mid_left" in manager.active_by_seat

    # Real Replay 0001 quantitative transition now recovered by v0.15.4:
    #
    #   65.6 -> 56.6 = 9 BB additional commitment.
    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=10.6,
    ):
        manager.ingest([
            Observation(
                type=STACK_CHANGED,
                ts=10.6,
                street="PREFLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={
                    "previous_stack_bb": 65.6,
                    "current_stack_bb": 56.6,
                    "delta_bb": 9.0,
                    "origin_street": "PREFLOP",
                    "stack_read_mode": "psm13_verification",
                },
            ),
        ])

    # Bet animation clears.
    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=10.8,
    ):
        manager.ingest([
            Observation(
                type=BET_REGION_CLEARED,
                ts=10.8,
                street="PREFLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={
                    "cleared": True,
                },
            ),
        ])

    # Let settlement window close the episode.
    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=11.7,
    ):
        manager.close_idle()

    assert len(manager.closed) == 1, manager.to_dict()

    episode = manager.closed[0]
    item = episode.to_dict()

    print("===== CLOSED EPISODE =====")
    print(item)

    assert item["seat"] == "seat_mid_left"
    assert item["street"] == "PREFLOP"
    assert item["evidence_mature"] is True

    assert item["observation_types"] == [
        BET_REGION_OCCUPIED,
        STACK_CHANGED,
        BET_REGION_CLEARED,
    ], item["observation_types"]

    engine = ActionInferenceEngine()
    inferred = engine.infer_episode(episode)

    print()
    print("===== INFERRED ACTION =====")
    print(inferred.to_dict())

    assert inferred.action == CALL_OR_RAISE, inferred
    assert inferred.seat == "seat_mid_left"
    assert inferred.street == "PREFLOP"

    stack = inferred.measurements.get(
        "stack_change"
    ) or {}

    assert stack.get("previous_stack_bb") == 65.6
    assert stack.get("current_stack_bb") == 56.6
    assert stack.get("delta_bb") == 9.0

    assert inferred.measurements[
        "commitment_sequence"
    ] is True

    print()
    print(
        "PASS Replay 0001 BB inference: "
        "bet region + real 9 BB stack transition "
        "-> CALL_OR_RAISE"
    )


if __name__ == "__main__":
    main()
