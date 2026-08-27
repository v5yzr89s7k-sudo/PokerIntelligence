from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HAND = "boundary-passive-quantitative-release"
STREET = "TURN"


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id=HAND,
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 20.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 50.0,
                "is_hero": False,
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

    hand.current_street = STREET
    hand.board = [
        "Ac",
        "7d",
        "2s",
        "9h",
    ]
    hand.players_to_act = [
        "hero",
        "villain",
    ]

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

            tracker = sm.tracker_for_hand(hand)

            # Establish the same semantic condition as production:
            # Villain has a real quantitative commitment, but Hero is
            # chronologically earlier and unresolved.
            quantitative = {
                "type": "inferred_action",
                "hand_token": HAND,
                "episode_id": 1,
                "seat": "villain",
                "street": STREET,
                "action": "BET_OR_RAISE",
                "confidence": 0.99,
                "measurements": {
                    "stack_change": {
                        "changed": True,
                        "previous_stack_bb": 50.0,
                        "current_stack_bb": 45.0,
                        "delta_bb": 5.0,
                        "origin_street": STREET,
                        "stack_read_confidence": 0.99,
                        "stack_read_mode": "independent_confirmed",
                    },
                    "commitment_sequence": True,
                },
                "evidence": [
                    "stack_changed",
                    "bet_region_occupied",
                ],
                "ts": 5.0,
            }

            state = sm.default_state()
            state.update({
                "phase": STREET,
                "hand_token": HAND,
                "canonical_snapshot_ready": True,
                "unresolved_stack_candidates": {
                    "TURN:villain": {
                        "seat": "villain",
                        "street": STREET,
                        "awaiting_action": True,
                    },
                },
            })

            # Normal quantitative ingestion must defer Villain behind Hero.
            state = sm.handle_inferred_action(
                state,
                quantitative,
            )

            pending_before = list(
                state.get("pending_inferred_actions")
                or []
            )

            print(
                "pending before boundary:",
                [
                    (
                        item.get("seat"),
                        item.get("street"),
                        item.get("action"),
                    )
                    for item in pending_before
                ],
            )

            assert any(
                item.get("seat") == "villain"
                and item.get("street") == STREET
                for item in pending_before
            ), (
                "fixture failed: Villain quantitative action "
                "was not deferred behind Hero"
            )

            # Hero has no quantitative commitment. The physical next-street
            # boundary now arrives through the same production handler used
            # by preserved boundary replay.
            state["unresolved_stack_candidates"].pop(
                "TURN:hero",
                None,
            )

            # Production only consumes an old-street boundary result while
            # the corresponding next-street board is physically confirmed and
            # pending behind unresolved old-street chronology.
            state["pending_board_events"] = [
                {
                    "board": [
                        "Ac",
                        "7d",
                        "2s",
                        "9h",
                        "3c",
                    ],
                    "ts": 5.5,
                }
            ]

            boundary_result = {
                "type": "boundary_stack_result",
                "request_id": "boundary-release",
                "hand_token": HAND,
                "street": STREET,
                "ts": 6.0,
                "observations": [
                    {
                        "seat": "hero",
                        "stack_bb": 20.0,
                        "confidence": 0.99,
                    },
                ],
            }

            state = sm.handle_boundary_stack_result(
                state,
                boundary_result,
                reconsider_observed_after_candidate_release=True,
            )

            canonical = sm.canonical_load()

            actions = [
                (
                    action.seat,
                    action.action,
                    action.street,
                )
                for action in canonical.actions
                if str(action.street).upper() == STREET
            ]

            pending_after = list(
                state.get("pending_inferred_actions")
                or []
            )

            print(
                "actions after boundary:",
                actions,
            )

            print(
                "pending after boundary:",
                [
                    (
                        item.get("seat"),
                        item.get("street"),
                        item.get("action"),
                    )
                    for item in pending_after
                ],
            )

            assert any(
                seat == "hero"
                and action == "CHECK"
                for seat, action, street in actions
            ), (
                "fixture failed: boundary did not resolve Hero CHECK"
            )

            assert any(
                seat == "villain"
                and action in {"BET", "BET_OR_RAISE", "RAISE"}
                for seat, action, street in actions
            ), (
                "RED: boundary passive chronology exposed Villain "
                "as the next actor but did not replay Villain's "
                "already-qualified deferred quantitative action"
            )

            assert not any(
                item.get("seat") == "villain"
                and item.get("street") == STREET
                for item in pending_after
            ), (
                "RED: accepted Villain quantitative action remained "
                "stranded in pending_inferred_actions"
            )

            print(
                "PASS boundary passive advancement releases "
                "deferred quantitative action"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
