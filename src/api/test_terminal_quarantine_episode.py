from src.observer.action_episode_manager import (
    ActionEpisodeManager,
)
from src.observer.observation import Observation


def ingest_if_not_frozen(
    manager,
    state,
    observations,
):
    if state.get("terminal_action_frozen"):
        return []

    manager.ingest(observations)
    return observations


def test_terminal_freeze_blocks_next_hand_stack_episode():
    manager = ActionEpisodeManager()

    state = {
        "phase": "RIVER",
        "terminal_action_frozen": True,
        "terminal_freeze_reason": "winner_detected",
    }

    next_hand_stack = Observation(
        type="stack_changed",
        ts=100.0,
        seat="seat_mid_right",
        street="RIVER",
        confidence=1.0,
        payload={
            "previous_stack_bb": 77.45,
            "current_stack_bb": 76.83,
            "delta_bb": 0.62,
            "stack_read_confidence": 0.98,
            "stack_read_mode": "agreement_verified",
        },
    )

    accepted = ingest_if_not_frozen(
        manager,
        state,
        [next_hand_stack],
    )

    assert accepted == []
    assert not manager.active_by_seat
    assert not manager.closed

    print(
        "PASS terminal quarantine: "
        "next-hand validated stack evidence cannot "
        "originate an old-hand RIVER episode"
    )


def test_normal_river_still_allows_episode():
    manager = ActionEpisodeManager()

    state = {
        "phase": "RIVER",
        "terminal_action_frozen": False,
    }

    legitimate_stack = Observation(
        type="stack_changed",
        ts=50.0,
        seat="seat_mid_right",
        street="RIVER",
        confidence=1.0,
        payload={
            "previous_stack_bb": 77.45,
            "current_stack_bb": 76.83,
            "delta_bb": 0.62,
            "stack_read_confidence": 0.98,
            "stack_read_mode": "agreement_verified",
        },
    )

    accepted = ingest_if_not_frozen(
        manager,
        state,
        [legitimate_stack],
    )

    assert accepted
    assert "seat_mid_right" in manager.active_by_seat

    print(
        "PASS normal river: "
        "validated stack evidence still originates an episode"
    )


def main():
    test_terminal_freeze_blocks_next_hand_stack_episode()
    test_normal_river_still_allows_episode()

    print()
    print(
        "PASS terminal quarantine episode contract"
    )


if __name__ == "__main__":
    main()
