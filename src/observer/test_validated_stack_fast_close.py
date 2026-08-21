from unittest.mock import patch

from src.observer.action_episode_manager import (
    ActionEpisodeManager,
)
from src.observer.observation_types import (
    Observation,
    STACK_CHANGED,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
)


def stack_obs(
    *,
    ts,
    seat="seat_lower_left",
    street="PREFLOP",
    previous=48.57,
    current=47.57,
):
    return Observation(
        type=STACK_CHANGED,
        street=street,
        seat=seat,
        ts=ts,
        payload={
            "origin_street": street,
            "previous_stack_bb": previous,
            "current_stack_bb": current,
            "delta_bb": round(
                previous - current,
                2,
            ),
            "stack_read_confidence": 0.98,
            "stack_read_mode": "agreement_verified",
            "settled_ms": 900.0,
        },
    )


def visual_obs(kind, ts):
    return Observation(
        type=kind,
        street="PREFLOP",
        seat="seat_lower_left",
        ts=ts,
        payload={},
    )


def test_stack_only_fast_close():
    manager = ActionEpisodeManager(
        idle_timeout=1.25,
    )

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=10.0,
    ):
        manager.ingest([
            stack_obs(ts=10.0),
        ])

    assert manager.active_by_seat == {}
    assert len(manager.closed) == 1

    episode = manager.closed[0]

    assert episode.evidence_mature is True
    assert (
        episode.close_reason
        == "validated_stack_transition"
    )

    assert [
        item.get("type")
        for item in episode.observations
    ] == [STACK_CHANGED]


def test_active_visual_episode_keeps_settlement_lifecycle():
    manager = ActionEpisodeManager(
        idle_timeout=1.25,
        settle_timeout=0.80,
    )

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=20.0,
    ):
        manager.ingest([
            visual_obs(
                BET_REGION_OCCUPIED,
                20.0,
            ),
        ])

    assert len(manager.active_by_seat) == 1

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=20.2,
    ):
        manager.ingest([
            stack_obs(ts=20.2),
        ])

    # Quantitative evidence is decisive. Once the validated stack transition
    # attaches to the visual episode, no idle/settlement delay may remain on
    # the action-publication path.
    assert manager.active_by_seat == {}
    assert len(manager.closed) == 1

    episode = manager.closed[0]

    assert episode.evidence_mature is True
    assert (
        episode.close_reason
        == "validated_stack_transition"
    )


def test_cleared_visual_episode_fast_closes_on_validated_stack():
    manager = ActionEpisodeManager(
        idle_timeout=1.25,
        settle_timeout=0.80,
    )

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=30.0,
    ):
        manager.ingest([
            visual_obs(
                BET_REGION_OCCUPIED,
                30.0,
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=30.1,
    ):
        manager.ingest([
            visual_obs(
                BET_REGION_CLEARED,
                30.1,
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=30.2,
    ):
        manager.ingest([
            stack_obs(ts=30.2),
        ])

    # Even when the visual bet region has already cleared, trusted
    # quantitative stack evidence is decisive. Action publication must not
    # wait for the residual visual settlement window.
    assert manager.active_by_seat == {}
    assert len(manager.closed) == 1

    episode = manager.closed[0]

    assert episode.evidence_mature is True
    assert (
        episode.close_reason
        == "validated_stack_transition"
    )

    assert [
        item.get("type")
        for item in episode.observations
    ] == [
        BET_REGION_OCCUPIED,
        BET_REGION_CLEARED,
        STACK_CHANGED,
    ]


def main():
    test_stack_only_fast_close()
    test_active_visual_episode_keeps_settlement_lifecycle()
    test_cleared_visual_episode_fast_closes_on_validated_stack()

    print(
        "PASS validated stack fast-close: "
        "trusted quantitative evidence closes immediately "
        "with or without a preceding visual episode"
    )


if __name__ == "__main__":
    main()
