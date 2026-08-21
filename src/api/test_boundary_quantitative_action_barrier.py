from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm

from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


HAND_TOKEN = "boundary-quantitative-action-barrier"


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
    hand.current_bet_bb = 2.0

    # Hero has posted only the 0.5 BB small blind.
    hand.players["hero"].committed_street_bb = 0.5
    hand.players["hero"].committed_total_bb = 0.5
    hand.players["hero"].committed_by_street["PREFLOP"] = 0.5

    hand.players["bb"].committed_street_bb = 1.0
    hand.players["bb"].committed_total_bb = 1.0
    hand.players["bb"].committed_by_street["PREFLOP"] = 1.0

    # BTN's 2 BB raise is already canonical.
    hand.players["btn"].committed_street_bb = 2.0
    hand.players["btn"].committed_total_bb = 2.0
    hand.players["btn"].committed_by_street["PREFLOP"] = 2.0

    hand.players_to_act = ["hero", "bb"]

    hand.dealt_in_seats = [
        "btn",
        "hero",
        "bb",
    ]

    return hand


def make_tracker(hand):
    tracker = BettingRoundTracker(hand)
    ct = tracker.commitment_tracker

    ct.initialize_street_order(
        "PREFLOP",
        ["btn", "hero", "bb"],
    )

    ct.open_response_queue(
        "PREFLOP",
        "btn",
        ["btn", "hero", "bb"],
    )

    ct.record_action(
        "PREFLOP",
        "btn",
        current_price=2.0,
        last_aggressor="btn",
        betting_open=True,
    )

    return tracker


def make_state():
    state = sm.default_state()
    state["phase"] = "FLOP"
    state["hand_token"] = HAND_TOKEN
    state["canonical_snapshot_ready"] = True
    state["board"] = ["2c", "7d", "Jh"]

    # This is the critical Run-3 condition:
    # Hero stack motion has already been detected, but its validated
    # quantitative inferred_action has not yet reached canonical state.
    state["unresolved_stack_candidates"] = {
        "PREFLOP:hero": {
            "seat": "hero",
            "street": "PREFLOP",
            "sources": ["stack_motion"],
            "awaiting_action": False,
        }
    }

    return state


def boundary_result():
    return {
        "type": "boundary_stack_result",
        "request_id": "run3-boundary-result",
        "hand_token": HAND_TOKEN,
        "street": "PREFLOP",
        "boundary_ts": 5.0,
        "ts": 6.0,
        "observations": [
            {
                "seat": "hero",
                "observation": {
                    # Boundary evidence sees the terminal 10.28 stack.
                    # Without the barrier this resolves Hero CALL immediately.
                    "seat": "hero",
                    "stack_bb": 10.28,
                    "confidence": 0.98,
                    "votes": 5,
                    "mode": "independent_confirmed",
                    "frame_path": "/tmp/run3-boundary.png",
                    "frame_ts": 5.0,
                    "local_board_count": 0,
                },
            },
        ],
    }


def main():
    reset_tracker()

    hand = make_hand()

    # Boundary processing happens after the board has physically advanced.
    hand.set_board(
        ["2c", "7d", "Jh"],
        ts=5.5,
    )

    # Build the preserved PREFLOP tracker after the canonical hand has
    # physically advanced to FLOP. Historical boundary reconciliation owns
    # this old-street response queue.
    tracker = make_tracker(hand)
    state = make_state()

    old_store = sm.CANONICAL_STORE
    old_tracker = sm._ACTIVE_TRACKER
    old_hand_id = sm._ACTIVE_HAND_ID
    old_status = sm.BETTING_ROUND_STATUS_PATH

    class FakeStore:
        text_path = Path("/tmp/boundary-barrier-current-hand.txt")

        def load(self):
            return hand

        def save(self, saved):
            assert saved is hand

    with TemporaryDirectory() as td:
        try:
            sm.CANONICAL_STORE = FakeStore()
            sm._ACTIVE_TRACKER = tracker
            sm._ACTIVE_HAND_ID = hand.hand_id
            sm.BETTING_ROUND_STATUS_PATH = (
                Path(td) / "betting_round_status.json"
            )

            state = sm.handle_boundary_stack_result(
                state,
                boundary_result(),
            )

        except Exception:
            sm.CANONICAL_STORE = old_store
            sm._ACTIVE_TRACKER = old_tracker
            sm._ACTIVE_HAND_ID = old_hand_id
            sm.BETTING_ROUND_STATUS_PATH = old_status
            raise

    # Keep FakeStore + the synthetic hand-owned tracker installed for the
    # remainder of this transaction test. Restoration happens only after the
    # complete boundary -> quantitative -> duplicate-boundary sequence.
    hero_actions = [
        action
        for action in hand.actions
        if action.street == "PREFLOP"
        and action.seat == "hero"
        and action.action not in {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    # REQUIRED INVARIANT:
    #
    # Boundary evidence may not canonicalize Hero while Hero has unresolved
    # quantitative commitment evidence. The later quantitative stack action
    # must own the 1.50 BB call.
    assert hero_actions == [], [
        (
            action.action,
            action.amount_bb,
            action.raise_to_bb,
            action.source,
        )
        for action in hero_actions
    ]

    candidate_key = "PREFLOP:hero"

    assert candidate_key in state[
        "unresolved_stack_candidates"
    ]

    boundary_key = (
        f"{HAND_TOKEN}:PREFLOP"
    )

    assert boundary_key in state[
        "preserved_boundary_evidence"
    ], (
        "deferred Hero boundary evidence was cleared "
        "before quantitative action arrived"
    )

    # Faithfully represent the July 22 historical state:
    #
    # BTN's 2 BB open was already quantitatively qualified before Hero's
    # delayed stack transition arrived. Preserved old-street reconciliation
    # requires that semantic evidence explicitly; commitment counters alone
    # are not a substitute for a qualified historical action.
    state["preserved_inferred_actions"] = {
        boundary_key: {
            "hand_token": HAND_TOKEN,
            "street": "PREFLOP",
            "actions_by_seat": {
                "btn": {
                    "type": "inferred_action",
                    "hand_token": HAND_TOKEN,
                    "episode_id": 4,
                    "seat": "btn",
                    "street": "PREFLOP",
                    "action": "BET_OR_RAISE",
                    "delta_bb": 2.0,
                    "confidence": 0.75,
                    "measurements": {
                        "stack_change": {
                            "changed": True,
                            "previous_stack_bb": 58.55,
                            "current_stack_bb": 56.55,
                            "delta_bb": 2.0,
                            "origin_street": "PREFLOP",
                            "stack_read_confidence": 0.95,
                            "stack_read_mode": "continuity",
                            "stack_text": "56.55 BB",
                        },
                    },
                    "evidence": [
                        "stack_changed",
                    ],
                    "reason": (
                        "seat stack changed and a bet region appeared "
                        "without confirmed prior voluntary commitment"
                    ),
                    "ts": 5.9,
                },
            },
        },
    }

    # BTN's objective commitment evidence must also be visible to historical
    # reconciliation, matching the already-established 2 BB open.
    tracker.commitment_tracker.record_commitment(
        "PREFLOP",
        "btn",
    )

    # Validation has now confirmed that the physical stack transition is
    # real. The candidate must remain a blocker until the corresponding
    # inferred_action becomes canonical.
    state = sm.handle_stack_candidate_closed(
        state,
        {
            "type": "stack_candidate_closed",
            "hand_token": HAND_TOKEN,
            "seat": "hero",
            "street": "PREFLOP",
            "reason": "validated_stack_transition",
            "ts": 6.1,
        },
    )

    assert candidate_key in state[
        "unresolved_stack_candidates"
    ]

    assert (
        state["unresolved_stack_candidates"][
            candidate_key
        ].get("awaiting_action")
        is True
    )

    # Exact semantic shape of the July 22 Run-3 Hero quantitative event.
    # The large production payload contains additional diagnostics, but these
    # are the fields consumed by canonical betting semantics.
    state = sm.handle_inferred_action(
        state,
        {
            "type": "inferred_action",
            "hand_token": HAND_TOKEN,
            "episode_id": 6,
            "seat": "hero",
            "street": "PREFLOP",
            "action": "BET_OR_RAISE",
            "confidence": 0.75,
            "measurements": {
                "commitment_sequence": False,
                "stack_change": {
                    "changed": True,
                    "previous_stack_bb": 11.78,
                    "current_stack_bb": 10.28,
                    "delta_bb": 1.5,
                    "origin_street": "PREFLOP",
                    "stack_read_confidence": 0.98,
                    "stack_read_mode": (
                        "independent_confirmed"
                    ),
                    "stack_text": "10.28 BB",
                },
            },
            "evidence": [
                "stack_changed",
            ],
            "reason": (
                "seat stack changed and a bet region appeared "
                "without confirmed prior voluntary commitment"
            ),
            "ts": 6.2,
        },
    )

    hand = sm.canonical_load()

    hero_actions = [
        action
        for action in hand.actions
        if action.street == "PREFLOP"
        and action.seat == "hero"
        and action.action not in {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    assert len(hero_actions) == 1, [
        (
            action.action,
            action.amount_bb,
            action.raise_to_bb,
            action.source,
        )
        for action in hero_actions
    ]

    hero_action = hero_actions[0]

    assert hero_action.action == "CALL", (
        hero_action.action,
        hero_action.amount_bb,
        hero_action.raise_to_bb,
    )

    assert abs(
        float(hero_action.amount_bb) - 1.5
    ) < 1e-9, hero_action.amount_bb

    assert hero_action.raise_to_bb is None, (
        "Hero quantitative call was double-counted into a raise"
    )

    hero = hand.players["hero"]

    # Historical reconciliation updates the old-street ledger without
    # corrupting the canonical hand's current-street live commitment.
    #
    # The synthetic hand is already on FLOP here. Therefore PREFLOP must
    # contain Hero's complete 2.0 BB contribution, while committed_street_bb
    # remains the live/current-street value rather than being rewritten by
    # retrospective repair.
    assert abs(
        float(
            hero.committed_by_street["PREFLOP"]
        ) - 2.0
    ) < 1e-9, hero.committed_by_street

    assert abs(
        float(hero.committed_street_bb) - 0.5
    ) < 1e-9, (
        "historical PREFLOP reconciliation corrupted "
        "current-street live commitment"
    )

    assert candidate_key not in state[
        "unresolved_stack_candidates"
    ], (
        "Hero quantitative candidate survived after "
        "canonical action consumption"
    )

    assert boundary_key not in state[
        "preserved_boundary_evidence"
    ], (
        "preserved boundary evidence survived after "
        "historical quantitative reconciliation"
    )

    # The same retrospective result may arrive/replay again through transport.
    # It must not create a second Hero action after the quantitative action
    # already owns Hero's preflop commitment.
    state = sm.handle_boundary_stack_result(
        state,
        boundary_result(),
    )

    hand = sm.canonical_load()

    hero_actions_after_replay = [
        action
        for action in hand.actions
        if action.street == "PREFLOP"
        and action.seat == "hero"
        and action.action not in {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    assert len(
        hero_actions_after_replay
    ) == 1, [
        (
            action.action,
            action.amount_bb,
            action.raise_to_bb,
            action.source,
        )
        for action in hero_actions_after_replay
    ]

    assert (
        hero_actions_after_replay[0].action
        == "CALL"
    )

    assert abs(
        float(
            hero_actions_after_replay[0].amount_bb
        ) - 1.5
    ) < 1e-9

    print(
        "PASS boundary quantitative transaction: "
        "boundary CALL defers, quantitative 1.5 BB transition "
        "canonicalizes exactly one Hero CALL to 2.0 BB, "
        "candidate/evidence clear, and boundary replay cannot "
        "double-account the commitment"
    )

    sm.CANONICAL_STORE = old_store
    sm._ACTIVE_TRACKER = old_tracker
    sm._ACTIVE_HAND_ID = old_hand_id
    sm.BETTING_ROUND_STATUS_PATH = old_status


if __name__ == "__main__":
    main()
