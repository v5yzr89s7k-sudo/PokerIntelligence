from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_state_machine as sm
from src.state.action_timeline import (
    observe_action,
    active_actions,
)
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HAND = "boundary-single-owner"
STREET = "PREFLOP"


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id=HAND,
        players=[
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 80.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 55.44,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["2c", "9s"],
        hero_position="BB",
        positions={
            "villain": "HJ",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.dealt_in_seats = [
        "villain",
        "hero",
    ]
    hand.current_street = STREET
    hand.players_to_act = ["hero"]

    return hand


def main():
    original_store = sm.CANONICAL_STORE
    original_tracker = sm._ACTIVE_TRACKER
    original_hand_id = sm._ACTIVE_HAND_ID

    with TemporaryDirectory() as tmp:
        try:
            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=Path(tmp) / "canonical.json",
                text_path=Path(tmp) / "current_hand.txt",
            )

            sm._ACTIVE_TRACKER = None
            sm._ACTIVE_HAND_ID = None

            hand = make_hand()
            sm.canonical_save(hand)

            tracker = sm.tracker_for_hand(
                sm.canonical_load()
            )

            ct = tracker.commitment_tracker

            # Reproduce the relevant September condition:
            #
            # Villain has opened betting. Hero remains in the
            # tracker queue and therefore appears to owe a
            # response at the physical FLOP boundary.
            ct.reset_street(STREET)

            ct.initialize_street_order(
                STREET,
                ["villain", "hero"],
            )

            ct.sync_queue(
                STREET,
                ["hero"],
            )

            # Establish a genuinely open betting round through the
            # authoritative commitment tracker. Hero must remain owing
            # a response, exactly as in the September failure.
            ct.record_commitment(
                STREET,
                "villain",
            )

            ct.open_response_queue(
                STREET,
                aggressor="villain",
                eligible_seats=[
                    "villain",
                    "hero",
                ],
            )

            # Mirror the production transition after a resolved
            # aggressor. open_response_queue() owns response ordering;
            # record_action() owns the authoritative betting state.
            ct.record_action(
                STREET,
                "villain",
                current_price=7.0,
                last_aggressor="villain",
                betting_open=True,
            )

            status = ct.round_status(STREET)

            assert status["betting_open"] is True, (
                "fixture failure: betting round did not open"
            )

            assert status["players_owing_action"] == [
                "hero"
            ], status

            state = sm.default_state()

            state.update({
                "phase": STREET,
                "hand_token": HAND,
                "canonical_snapshot_ready": True,

                # Critical reproduction:
                # all temporary commitment blockers are gone.
                "unresolved_stack_candidates": {},
                "unresolved_provisional_bets": {},
                "preserved_inferred_actions": {},
            })

            # But the durable semantic owner still knows Hero
            # physically acted.
            state = observe_action(
                state,
                hand_token=HAND,
                street=STREET,
                seat="hero",
                action="BET_OR_RAISE",
                ts=5.0,
                source="bet_region_appeared",
                confidence=0.70,
                evidence=[
                    "bet_region_appeared",
                ],
            )

            before = active_actions(
                state,
                hand_token=HAND,
            )

            print("===== BEFORE =====")
            print("timeline:", before)

            print(
                "tracker:",
                ct.round_status(STREET),
            )

            canonical = sm.canonical_load()

            state, resolved = (
                sm.resolve_silent_boundary_obligations(
                    state,
                    canonical=canonical,
                    tracker=tracker,
                    street=STREET,
                    observed_seats=set(),
                    reconsider_observed_after_candidate_release=True,
                )
            )

            timeline_after = active_actions(
                state,
                hand_token=HAND,
            )

            canonical_after = sm.canonical_load()

            # resolve_silent_boundary_obligations mutates the
            # canonical object supplied to it before the store
            # is necessarily refreshed, so inspect both.
            canonical_actions = [
                (
                    action.seat,
                    action.action,
                    action.street,
                )
                for action in canonical.actions
                if (
                    str(action.street).upper()
                    == STREET
                    and action.seat == "hero"
                )
            ]

            stored_actions = [
                (
                    action.seat,
                    action.action,
                    action.street,
                )
                for action in canonical_after.actions
                if (
                    str(action.street).upper()
                    == STREET
                    and action.seat == "hero"
                )
            ]

            print()
            print("===== AFTER =====")
            print("resolved:", resolved)
            print("timeline:", timeline_after)
            print(
                "canonical object:",
                canonical_actions,
            )
            print(
                "canonical store:",
                stored_actions,
            )
            print(
                "tracker:",
                ct.round_status(STREET),
            )

            # ------------------------------------------------
            # SINGLE-OWNER INVARIANT
            # ------------------------------------------------

            hero_owner = [
                item
                for item in timeline_after
                if (
                    item.get("seat") == "hero"
                    and item.get("street") == STREET
                )
            ]

            assert len(hero_owner) == 1, hero_owner

            assert (
                hero_owner[0]["action"]
                == "BET_OR_RAISE"
            ), hero_owner

            false_boundary_fold = any(
                seat == "hero"
                and action == "FOLD"
                for seat, action, street
                in canonical_actions
            )

            assert not false_boundary_fold, (
                "RED: boundary passive resolver bypassed "
                "ActionTimeline and authored a competing "
                "Hero FOLD despite an existing durable "
                "Hero BET_OR_RAISE owner"
            )

            assert not any(
                item.get("seat") == "hero"
                and item.get("action") == "FOLD"
                for item in resolved
            ), resolved

            # v0.16 DERIVED OBLIGATION INVARIANT
            #
            # Once ActionTimeline proves Hero already acted on this
            # street, no secondary obligation representation may retain
            # Hero as still pending. Otherwise a later betting-state
            # transition can resurrect an already-consumed actor.
            final_status = (
                tracker.commitment_tracker.round_status(
                    STREET
                )
            )

            assert (
                "hero"
                not in final_status[
                    "players_owing_action"
                ]
            ), final_status

            assert (
                "hero"
                not in final_status[
                    "needs_response_from"
                ]
            ), (
                "RED: durable action owner cleared the open-bet "
                "response queue but Hero still survives in "
                "needs_response_from"
            )

            assert (
                "hero"
                not in final_status[
                    "pending_to_act"
                ]
            ), (
                "RED: durable action owner left Hero in the "
                "secondary pending_to_act queue; a later "
                "betting-state transition can resurrect the "
                "already-observed actor"
            )

            print()
            print(
                "PASS: boundary passive recovery "
                "cannot author around ActionTimeline"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
