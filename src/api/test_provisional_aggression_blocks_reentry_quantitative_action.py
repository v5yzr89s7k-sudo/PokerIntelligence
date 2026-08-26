from unittest.mock import patch

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="provisional-reentry",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 10.28,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "bb",
                "name": "BB",
                "stack_bb": 47.57,
                "is_active": True,
            },
            {
                "seat": "btn",
                "name": "BTN",
                "stack_bb": 56.55,
                "is_active": True,
            },
        ],
        hero_cards=["Qd", "Ah"],
        hero_position="SB",
        positions={
            "hero": "SB",
            "bb": "BB",
            "btn": "BTN",
        },
        started_ts=1.0,
    )

    hand.dealt_in_seats = [
        "hero",
        "bb",
        "btn",
    ]

    hand.set_board(
        ["Jd", "9s", "Tc"],
        ts=2.0,
    )

    hand.current_bet_bb = 0.0
    hand.last_aggressor_seat = None
    hand.players_to_act = [
        "hero",
        "bb",
        "btn",
    ]

    return hand


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    # Replay-0002 shape:
    #
    # Hero acts first. Physical observation of BB proves Hero
    # was skipped with no open bet, therefore Hero CHECKS.
    added = tracker.advance_to_observed_actor(
        "bb",
        blocked_seats=set(),
        ts=3.0,
    )

    assert [
        (item.seat, item.action)
        for item in added
    ] == [
        ("hero", "CHECK"),
    ]

    assert hand.players_to_act == [
        "bb",
        "btn",
    ]

    # BB now has visible commitment evidence, but quantitative
    # stack corroboration has not completed. This is not enough
    # to publish BB BET; it is enough to establish unresolved
    # aggression chronology.
    state = sm.default_state()
    state["phase"] = "FLOP"
    state["canonical_snapshot_ready"] = True
    state["hand_token"] = "provisional-reentry-token"
    state["unresolved_provisional_bets"] = {
        "FLOP:bb": {
            "street": "FLOP",
            "seat": "bb",
            "bet_bb": 3.37,
            "source": "transition",
            "source_request_id": "generic-request",
            "ts": 4.0,
        }
    }

    # Hero's later quantitative response arrives after Hero has
    # already checked and therefore is absent from players_to_act.
    #
    # Production currently computes:
    #   actor_index = -1
    #   earlier_seats = []
    #   provisional_gap = []
    #
    # and admits this as fresh BET_OR_RAISE.
    event = {
        "type": "inferred_action",
        "episode_id": 8,
        "seat": "hero",
        "street": "FLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.75,
        "evidence": [
            "stack_changed",
        ],
        "reason": (
            "seat stack changed and a bet region appeared "
            "without confirmed prior voluntary commitment"
        ),
        "measurements": {
            "stack_change": {
                "changed": True,
                "previous_stack_bb": 10.28,
                "current_stack_bb": 6.90,
                "delta_bb": 3.38,
                "origin_street": "FLOP",
                "stack_read_confidence": 0.95,
                "stack_read_mode": "continuity",
            },
            "table_context": {
                "phase": "FLOP",
                "positions": {
                    "hero": "SB",
                    "bb": "BB",
                    "btn": "BTN",
                },
                "prior_voluntary_commitment_seats": [],
            },
        },
        "ts": 5.0,
    }

    before_actions = [
        item.to_dict()
        for item in hand.actions
    ]
    before_queue = list(
        hand.players_to_act
    )

    with patch.object(
        sm,
        "canonical_load",
        return_value=hand,
    ), patch.object(
        sm,
        "canonical_save",
    ), patch.object(
        sm,
        "tracker_for_hand",
        return_value=tracker,
    ), patch.object(
        sm,
        "write_betting_round_status",
        return_value={
            "street": "FLOP",
            "complete": False,
            "players_owing_action": list(
                hand.players_to_act
            ),
        },
    ):
        state = sm.handle_inferred_action(
            state,
            event,
        )

    after_actions = [
        item.to_dict()
        for item in hand.actions
    ]

    print(
        "queue before Hero quantitative:",
        before_queue,
    )
    print(
        "queue after Hero quantitative:",
        hand.players_to_act,
    )
    print(
        "pending inferred actions:",
        state.get("pending_inferred_actions"),
    )
    print(
        "new canonical actions:",
        after_actions[len(before_actions):],
    )

    # Required invariant:
    #
    # An unresolved provisional aggression can reopen action for
    # players who already acted earlier on the street. Until that
    # aggression is resolved, a later quantitative stack decrease
    # from such a player cannot be admitted as fresh aggression
    # merely because that player is absent from players_to_act.
    assert after_actions == before_actions, (
        "RED: Hero quantitative re-entry crossed unresolved "
        "provisional BB aggression and mutated canonical history"
    )

    pending = list(
        state.get("pending_inferred_actions")
        or []
    )

    assert any(
        item.get("seat") == "hero"
        and item.get("street") == "FLOP"
        for item in pending
    ), (
        "RED: Hero quantitative re-entry was not preserved "
        "while provisional aggression remained unresolved"
    )

    assert hand.players_to_act == before_queue, (
        "RED: unresolved provisional aggression allowed "
        "quantitative re-entry to mutate the action queue"
    )

    print(
        "PASS provisional aggression re-entry contract: "
        "a previously acted player cannot publish a later "
        "quantitative action through unresolved aggression"
    )


if __name__ == "__main__":
    main()
