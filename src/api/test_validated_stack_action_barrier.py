import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


HAND_TOKEN = "validated-stack-action-barrier"


def reset_tracker():
    sm._ACTIVE_TRACKER = None
    sm._ACTIVE_HAND_ID = None


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id=HAND_TOKEN,
        players=[
            {
                "seat": "btn",
                "name": "BTN",
                "stack_bb": 58.55,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 11.78,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "bb",
                "name": "BB",
                "stack_bb": 48.57,
                "is_active": True,
            },
        ],
        hero_cards=["Qd", "Ah"],
        hero_position="SB",
        positions={
            "btn": "BTN",
            "hero": "SB",
            "bb": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"
    hand.current_bet_bb = 1.0

    # Forced blind accounting expected by the tracker.
    hand.players["hero"].committed_street_bb = 0.5
    hand.players["hero"].committed_total_bb = 0.5

    hand.players["bb"].committed_street_bb = 1.0
    hand.players["bb"].committed_total_bb = 1.0

    hand.players_to_act = [
        "btn",
        "hero",
        "bb",
    ]

    hand.dealt_in_seats = [
        "btn",
        "hero",
        "bb",
    ]

    return hand


def make_state():
    state = sm.default_state()
    state["phase"] = "PREFLOP"
    state["hand_token"] = HAND_TOKEN
    state["canonical_snapshot_ready"] = True
    return state


def main():
    reset_tracker()

    hand = make_hand()
    sm.canonical_save(hand)

    state = make_state()

    # BTN commitment candidate opens.
    state = sm.handle_stack_candidate_opened(
        state,
        {
            "type": "stack_candidate_opened",
            "hand_token": HAND_TOKEN,
            "seat": "btn",
            "street": "PREFLOP",
            "sources": ["stack_motion"],
            "ts": 2.0,
        },
    )

    # Hero is physically observed later. BTN correctly blocks chronology.
    state = sm.handle_actor_observed(
        state,
        {
            "type": "actor_observed",
            "hand_token": HAND_TOKEN,
            "seat": "hero",
            "street": "PREFLOP",
            "ts": 3.0,
        },
    )

    hand = sm.canonical_load()

    assert hand.actions == []
    assert hand.players_to_act == [
        "btn",
        "hero",
        "bb",
    ]

    assert state["pending_actor_observations"], (
        "Hero observation was not preserved behind BTN"
    )

    # Stack validation succeeds. This MUST NOT release Hero yet.
    state = sm.handle_stack_candidate_closed(
        state,
        {
            "type": "stack_candidate_closed",
            "hand_token": HAND_TOKEN,
            "seat": "btn",
            "street": "PREFLOP",
            "reason": "validated_stack_transition",
            "ts": 4.0,
        },
    )

    hand = sm.canonical_load()

    assert hand.actions == [], (
        "validated candidate closure released Hero before BTN action"
    )

    assert hand.players_to_act == [
        "btn",
        "hero",
        "bb",
    ]

    key = "PREFLOP:btn"

    assert key in state["unresolved_stack_candidates"]
    assert (
        state["unresolved_stack_candidates"][key]
        .get("awaiting_action")
        is True
    )

    assert state["pending_actor_observations"], (
        "preserved Hero observation was released too early"
    )

    # Now the quantitative action arrives and becomes canonical.
    state = sm.handle_inferred_action(
        state,
        {
            "type": "inferred_action",
            "hand_token": HAND_TOKEN,
            "episode_id": 900001,
            "seat": "btn",
            "street": "PREFLOP",
            "action": "BET_OR_RAISE",
            "confidence": 0.95,
            "measurements": {
                "stack_change": {
                    "delta_bb": 2.0,
                }
            },
            "evidence": [
                "stack_changed",
            ],
            "ts": 4.1,
        },
    )

    hand = sm.canonical_load()

    assert hand.actions, "BTN quantitative action was not canonical"

    btn_actions = [
        action
        for action in hand.actions
        if action.seat == "btn"
    ]

    assert len(btn_actions) == 1

    assert btn_actions[0].action in {
        "RAISE",
        "BET_OR_RAISE",
    }, btn_actions[0]

    assert not hand.players["btn"].folded, (
        "BTN was fabricated as a fold before quantitative action"
    )

    assert (
        key
        not in state["unresolved_stack_candidates"]
    ), (
        "BTN blocker remained after canonical action"
    )

    assert not state["pending_actor_observations"], (
        "Hero observation was not released after BTN action"
    )

    print(
        "PASS validated stack action barrier: "
        "candidate remains blocking after validation, "
        "BTN quantitative action canonicalizes first, "
        "then preserved Hero chronology is released"
    )


if __name__ == "__main__":
    main()
