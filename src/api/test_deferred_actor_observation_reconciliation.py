import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def reset_tracker():
    sm._ACTIVE_TRACKER = None
    sm._ACTIVE_HAND_ID = None


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="deferred-actor-reconciliation",
        players=[
            {
                "seat": "utg",
                "name": "UTG",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "hj",
                "name": "HJ",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "co",
                "name": "CO",
                "stack_bb": 100.0,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="CO",
        positions={
            "utg": "UTG",
            "hj": "HJ",
            "co": "CO",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"
    hand.current_bet_bb = 1.0
    hand.players_to_act = [
        "utg",
        "hj",
        "co",
    ]

    return hand


def make_state():
    state = sm.default_state()
    state["phase"] = "PREFLOP"
    state["hand_token"] = "deferred-token"
    state["canonical_snapshot_ready"] = True
    return state


def test_blocked_actor_replays_after_candidate_closes():
    reset_tracker()

    hand = make_hand()
    sm.canonical_save(hand)
    state = make_state()

    # HJ has possible commitment evidence, so later CO cannot yet prove
    # UTG/HJ passive.
    state = sm.handle_stack_candidate_opened(
        state,
        {
            "type": "stack_candidate_opened",
            "hand_token": "deferred-token",
            "seat": "hj",
            "street": "PREFLOP",
            "sources": ["stack_motion"],
            "ts": 1.5,
        },
    )

    state = sm.handle_actor_observed(
        state,
        {
            "type": "actor_observed",
            "hand_token": "deferred-token",
            "seat": "co",
            "street": "PREFLOP",
            "source": "bet_region_appeared",
            "ts": 2.0,
        },
    )

    hand = sm.canonical_load()

    # Safety is preserved while evidence is unresolved.
    assert hand.actions == []
    assert hand.players_to_act == [
        "utg",
        "hj",
        "co",
    ]

    pending = (
        state.get("pending_actor_observations")
        or []
    )

    assert len(pending) == 1
    assert pending[0]["seat"] == "co"

    # Once the blocker settles without a quantitative action, the already
    # observed CO chronology becomes admissible and must replay.
    state = sm.handle_stack_candidate_closed(
        state,
        {
            "type": "stack_candidate_closed",
            "hand_token": "deferred-token",
            "seat": "hj",
            "street": "PREFLOP",
            "reason": "candidate_removed",
            "ts": 3.0,
        },
    )

    hand = sm.canonical_load()

    assert [
        (a.seat, a.action)
        for a in hand.actions
    ] == [
        ("utg", "FOLD"),
        ("hj", "FOLD"),
    ]

    assert hand.players_to_act == ["co"]

    assert (
        state.get("pending_actor_observations")
        or []
    ) == []


def test_actor_remains_pending_while_another_blocker_exists():
    reset_tracker()

    hand = make_hand()
    sm.canonical_save(hand)
    state = make_state()

    for seat in ("utg", "hj"):
        state = sm.handle_stack_candidate_opened(
            state,
            {
                "type": "stack_candidate_opened",
                "hand_token": "deferred-token",
                "seat": seat,
                "street": "PREFLOP",
                "sources": ["stack_motion"],
                "ts": 1.0,
            },
        )

    state = sm.handle_actor_observed(
        state,
        {
            "type": "actor_observed",
            "hand_token": "deferred-token",
            "seat": "co",
            "street": "PREFLOP",
            "ts": 2.0,
        },
    )

    state = sm.handle_stack_candidate_closed(
        state,
        {
            "type": "stack_candidate_closed",
            "hand_token": "deferred-token",
            "seat": "utg",
            "street": "PREFLOP",
            "reason": "candidate_removed",
            "ts": 3.0,
        },
    )

    hand = sm.canonical_load()

    # HJ still blocks the gap, so nothing is fabricated.
    assert hand.actions == []

    pending = (
        state.get("pending_actor_observations")
        or []
    )
    assert len(pending) == 1

    state = sm.handle_stack_candidate_closed(
        state,
        {
            "type": "stack_candidate_closed",
            "hand_token": "deferred-token",
            "seat": "hj",
            "street": "PREFLOP",
            "reason": "candidate_removed",
            "ts": 4.0,
        },
    )

    hand = sm.canonical_load()

    assert [
        (a.seat, a.action)
        for a in hand.actions
    ] == [
        ("utg", "FOLD"),
        ("hj", "FOLD"),
    ]


def main():
    test_blocked_actor_replays_after_candidate_closes()
    test_actor_remains_pending_while_another_blocker_exists()

    print(
        "PASS deferred actor reconciliation: "
        "blocked physical chronology survives asynchronous "
        "commitment evidence and replays only when safe"
    )


if __name__ == "__main__":
    main()
