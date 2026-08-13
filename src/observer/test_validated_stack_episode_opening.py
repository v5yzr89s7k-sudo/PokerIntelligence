from unittest.mock import patch

from src.observer.action_episode_manager import (
    ActionEpisodeManager,
)
from src.observer.observation_types import (
    Observation,
    STACK_CHANGED,
)


def stack_observation(
    *,
    seat="seat_mid_left",
    street="FLOP",
    ts=10.0,
    previous=90.85,
    current=87.71,
    confidence=0.98,
    mode="agreement_verified",
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
            "stack_read_confidence": confidence,
            "stack_read_mode": mode,
            "settled_ms": 1106.8,
        },
    )


def test_validated_stack_opens_quantitative_episode():
    manager = ActionEpisodeManager()

    obs = stack_observation()

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=10.0,
    ):
        manager.ingest([obs])

    assert "seat_mid_left" in manager.active_by_seat

    episode = manager.active_by_seat[
        "seat_mid_left"
    ]

    assert episode.street == "FLOP"
    assert episode.confidence == 0.40
    assert episode.evidence_mature is True
    assert episode.maturity_reason == (
        "quantitative_stack_commitment"
    )

    assert [
        item.get("type")
        for item in episode.observations
    ] == ["stack_changed"]

    assert "seat_mid_left" not in (
        manager.pending_stack_by_seat
    )

    print(
        "PASS validated stack opening: "
        "trusted 90.85 -> 87.71 FLOP transition "
        "originates a quantitative episode"
    )


def test_low_confidence_stack_does_not_open_episode():
    manager = ActionEpisodeManager()

    obs = stack_observation(
        ts=20.0,
        confidence=0.40,
        mode="unresolved",
    )

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=20.0,
    ):
        manager.ingest([obs])

    assert "seat_mid_left" not in manager.active_by_seat
    assert "seat_mid_left" in manager.pending_stack_by_seat

    print(
        "PASS safety: low-confidence unresolved "
        "stack evidence remains pending"
    )


def test_stack_increase_does_not_open_episode():
    manager = ActionEpisodeManager()

    obs = stack_observation(
        ts=40.0,
        previous=87.71,
        current=90.85,
    )

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=40.0,
    ):
        manager.ingest([obs])

    assert "seat_mid_left" not in manager.active_by_seat

    print(
        "PASS safety: stack increase does not "
        "originate a commitment episode"
    )


def main():
    test_validated_stack_opens_quantitative_episode()
    test_low_confidence_stack_does_not_open_episode()
    test_stack_increase_does_not_open_episode()

    print()
    print(
        "PASS validated stack episode contract: "
        "settled trusted quantitative transitions can "
        "survive even when bet-region appearance is missed"
    )


if __name__ == "__main__":
    main()
