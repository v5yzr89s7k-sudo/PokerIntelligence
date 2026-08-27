from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="quantitative-authoritative-ownership",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 100.0,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="SB",
        positions={
            "hero": "SB",
            "villain": "BB",
        },
        started_ts=1.0,
    )

    hand.set_board(
        ["Jd", "9s", "Tc", "9h"],
        ts=2.0,
    )

    hand.current_bet_bb = 0.0

    # Materialized CanonicalHand queue deliberately lags.
    hand.players_to_act = [
        "hero",
        "villain",
    ]

    return hand


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    street = "TURN"

    # Durable betting ownership has already consumed Hero.
    tracker.commitment_tracker.consume_pending_action(
        street,
        "hero",
    )

    authoritative_before = (
        tracker.commitment_tracker.players_owing_action(
            street
        )
    )

    canonical_before = list(
        hand.players_to_act
    )

    print(
        "authoritative before:",
        authoritative_before,
    )
    print(
        "canonical before:",
        canonical_before,
    )

    assert authoritative_before == [
        "villain"
    ], authoritative_before

    assert canonical_before == [
        "hero",
        "villain",
    ], canonical_before

    result = tracker.ingest({
        "episode_id": 9001,
        "seat": "villain",
        "street": street,
        "action": "BET_OR_RAISE",
        "confidence": 0.98,
        "measurements": {
            "stack_change": {
                "delta_bb": 3.0,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "continuity",
            },
        },
        "evidence": [
            "stack_changed",
        ],
        "ts": 3.0,
    })

    print(
        "result:",
        (
            None
            if result is None
            else (
                result.seat,
                result.action,
            )
        ),
    )

    print(
        "canonical after:",
        hand.players_to_act,
    )

    print(
        "authoritative after:",
        tracker.commitment_tracker
        .players_owing_action(
            street
        ),
    )

    assert result is not None, (
        "RED: BettingRoundTracker.ingest still "
        "uses stale CanonicalHand.players_to_act "
        "for quantitative admission"
    )

    assert result.seat == "villain"

    assert any(
        action.street == street
        and action.seat == "villain"
        for action in hand.actions
    )

    # Critical safety invariant:
    #
    # Villain's quantitative evidence does not independently
    # establish what stale Hero did. Admission may rely on
    # durable tracker ownership, but it must not reinterpret
    # the stale canonical predecessor as a newly proven action.
    assert not any(
        action.street == street
        and action.seat == "hero"
        for action in hand.actions
    ), [
        (
            action.street,
            action.seat,
            action.action,
        )
        for action in hand.actions
    ]

    authoritative_after = (
        tracker.commitment_tracker
        .players_owing_action(
            street
        )
    )

    assert "villain" not in authoritative_after, (
        authoritative_after
    )

    print(
        "PASS quantitative ingest authoritative "
        "ownership: durable tracker chronology "
        "admits the actor without fabricating "
        "a stale canonical predecessor"
    )


if __name__ == "__main__":
    main()
