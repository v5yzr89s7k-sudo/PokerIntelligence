from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_state_machine as sm
from src.state.action_timeline import (
    observe_action,
    active_actions,
)
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HAND = "boundary-handler-single-owner"
STREET = "PREFLOP"


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
        STREET
    ] = 7.0

    hand.players["folder"].committed_by_street[
        STREET
    ] = 1.0

    hand.current_street = STREET
    hand.players_to_act = ["folder"]

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

            canonical = sm.canonical_load()
            tracker = sm.tracker_for_hand(canonical)
            ct = tracker.commitment_tracker

            ct.reset_street(STREET)

            ct.initialize_street_order(
                STREET,
                ["raiser", "folder"],
            )

            ct.open_response_queue(
                STREET,
                "raiser",
                ["raiser", "folder"],
            )

            ct.record_action(
                STREET,
                "raiser",
                current_price=7.0,
                last_aggressor="raiser",
                betting_open=True,
            )

            status = ct.round_status(STREET)

            assert (
                status["players_owing_action"]
                == ["folder"]
            ), status

            state = sm.default_state()

            state.update({
                # Keep old street canonical with a confirmed
                # next-street board waiting. This is explicitly
                # supported by handle_boundary_stack_result().
                "phase": STREET,
                "physical_street": "FLOP",
                "hand_token": HAND,
                "canonical_snapshot_ready": True,
                "pending_board_events": [
                    {
                        "board": [
                            "2c",
                            "7d",
                            "Jh",
                        ],
                        "ts": 10.0,
                    },
                ],
                "unresolved_stack_candidates": {},
                "unresolved_provisional_bets": {},
                "preserved_inferred_actions": {},
            })

            state = observe_action(
                state,
                hand_token=HAND,
                street=STREET,
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
                ct.round_status(STREET),
            )

            result = {
                "type": "boundary_stack_result",
                "request_id": (
                    "boundary-handler-owner"
                ),
                "hand_token": HAND,
                "street": STREET,
                "ts": 9.0,
                "observations": [
                    {
                        "seat": "folder",
                        "observation": {
                            "seat": "folder",
                            "stack_bb": 40.0,
                            "confidence": 0.98,
                            "votes": 4,
                            "mode": (
                                "agreement_verified"
                            ),
                            "frame_path": (
                                "/tmp/"
                                "boundary_handler_owner.png"
                            ),
                            "frame_ts": 9.0,
                        },
                    },
                ],
            }

            state = (
                sm.handle_boundary_stack_result(
                    state,
                    result,
                )
            )

            after = active_actions(
                state,
                hand_token=HAND,
            )

            canonical_after = sm.canonical_load()

            canonical_actions = [
                (
                    action.seat,
                    action.action,
                    action.street,
                    action.source,
                )
                for action in canonical_after.actions
                if (
                    action.seat == "folder"
                    and str(
                        action.street or ""
                    ).upper()
                    == STREET
                )
            ]

            final_tracker = (
                sm.tracker_for_hand(
                    canonical_after
                ).commitment_tracker
            )

            final_status = (
                final_tracker.round_status(
                    STREET
                )
            )

            print()
            print("===== AFTER =====")
            print("timeline:", after)
            print(
                "canonical:",
                canonical_actions,
            )
            print(
                "tracker:",
                final_status,
            )

            owner = [
                item
                for item in after
                if (
                    item.get("seat")
                    == "folder"
                    and item.get("street")
                    == STREET
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
                "RED: handle_boundary_stack_result "
                "allowed boundary promotion to author "
                "canonical FOLD around the existing "
                "ActionTimeline BET_OR_RAISE owner"
            )

            print()
            print(
                "PASS: boundary stack integration "
                "defers to durable action ownership"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
