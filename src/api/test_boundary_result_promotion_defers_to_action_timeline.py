from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_state_machine as sm
from src.state.action_timeline import (
    observe_action,
    active_actions,
)
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HAND = "boundary-promoter-single-owner"


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id=HAND,
        players=[
            {
                "seat": "raiser",
                "name": "Raiser",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "folder",
                "name": "Folder",
                "stack_bb": 40.0,
                "is_active": True,
            },
        ],
        hero_cards=[],
        hero_position="unknown",
        positions={
            "raiser": "BTN",
            "folder": "BB",
        },
        started_ts=1.0,
    )

    hand.players["raiser"].committed_by_street[
        "PREFLOP"
    ] = 7.0

    hand.players["folder"].committed_by_street[
        "PREFLOP"
    ] = 1.0

    # Boundary result arrives after the board has already
    # advanced, matching retrospective promotion semantics.
    hand.set_board(
        ["2c", "7d", "Jh"],
        ts=10.0,
    )

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

            ct.reset_street("PREFLOP")

            ct.initialize_street_order(
                "PREFLOP",
                ["raiser", "folder"],
            )

            ct.open_response_queue(
                "PREFLOP",
                "raiser",
                ["raiser", "folder"],
            )

            ct.record_action(
                "PREFLOP",
                "raiser",
                current_price=7.0,
                last_aggressor="raiser",
                betting_open=True,
            )

            status = ct.round_status(
                "PREFLOP"
            )

            assert (
                status["players_owing_action"]
                == ["folder"]
            ), status

            state = sm.default_state()

            state.update({
                "phase": "FLOP",
                "physical_street": "FLOP",
                "hand_token": HAND,
                "canonical_snapshot_ready": True,
                "unresolved_stack_candidates": {},
                "unresolved_provisional_bets": {},
                "preserved_inferred_actions": {},
            })

            # Durable physical owner says the player already
            # performed a commitment action.
            state = observe_action(
                state,
                hand_token=HAND,
                street="PREFLOP",
                seat="folder",
                action="BET_OR_RAISE",
                ts=8.0,
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
                ct.round_status("PREFLOP"),
            )

            canonical = sm.canonical_load()

            # Call the exact production promoter currently used
            # by state-machine boundary reconciliation.
            promotion = (
                sm.promote_boundary_observation(
                    hand=canonical,
                    commitment_tracker=ct,
                    street="PREFLOP",
                    seat="folder",
                    observation={
                        "seat": "folder",
                        "stack_bb": 40.0,
                        "confidence": 0.98,
                        "votes": 4,
                        "mode": "agreement_verified",
                        "frame_path": (
                            "/tmp/"
                            "boundary_promoter_owner.png"
                        ),
                        "frame_ts": 9.0,
                    },
                )
            )

            after = active_actions(
                state,
                hand_token=HAND,
            )

            canonical_actions = [
                (
                    action.seat,
                    action.action,
                    action.street,
                    action.source,
                )
                for action in canonical.actions
                if (
                    action.seat == "folder"
                    and str(
                        action.street or ""
                    ).upper()
                    == "PREFLOP"
                )
            ]

            print()
            print("===== AFTER =====")
            print("promotion:", promotion)
            print("timeline:", after)
            print(
                "canonical:",
                canonical_actions,
            )
            print(
                "tracker:",
                ct.round_status("PREFLOP"),
            )

            owner = [
                item
                for item in after
                if (
                    item.get("seat")
                    == "folder"
                    and item.get("street")
                    == "PREFLOP"
                )
            ]

            assert len(owner) == 1, owner

            assert (
                owner[0]["action"]
                == "BET_OR_RAISE"
            ), owner

            competing = [
                item
                for item in canonical_actions
                if item[1] == "FOLD"
            ]

            assert competing == [], (
                "RED: boundary result promoter bypassed "
                "ActionTimeline and authored canonical "
                "FOLD for a seat whose durable action "
                "owner is BET_OR_RAISE"
            )

            print()
            print(
                "PASS: boundary result promotion "
                "cannot bypass durable action ownership"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
