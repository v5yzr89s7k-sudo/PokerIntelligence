from pathlib import Path
import tempfile

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


def make_hand():
    hand = CanonicalHand()

    hand.start_hand(
        hand_id="boundary-candidate-release-test",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "seat_mid_right",
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
            "seat_mid_right": "BB",
        },
        started_ts=1.0,
    )

    hand.set_board(
        ["Jd", "9s", "Tc", "9h"],
        ts=2.0,
    )

    return hand


def main():
    original_store = sm.CANONICAL_STORE
    original_tracker = sm._ACTIVE_TRACKER
    original_hand_id = sm._ACTIVE_HAND_ID

    with tempfile.TemporaryDirectory() as tmp:
        try:
            sm.CANONICAL_STORE = CanonicalHandStore(
                Path(tmp) / "canonical_hand.json"
            )
            sm._ACTIVE_TRACKER = None
            sm._ACTIVE_HAND_ID = None

            hand = make_hand()
            sm.canonical_save(hand)

            state = sm.default_state()
            state["phase"] = "TURN"
            state["hand_token"] = "test-token"
            state["canonical_snapshot_ready"] = True
            state["board"] = [
                "Jd",
                "9s",
                "Tc",
                "9h",
            ]

            tracker = sm.tracker_for_hand(hand)

            owing = (
                tracker.commitment_tracker
                .players_owing_action("TURN")
            )

            print("initial owing:", owing)

            assert owing
            assert owing[0] == "hero"

            # Current architecture: confirmed RIVER is preserved behind
            # incomplete TURN chronology.
            state["pending_board_events"] = [{
                "board": [
                    "Jd",
                    "9s",
                    "Tc",
                    "9h",
                    "7h",
                ],
                "ts": 10.0,
            }]

            # Hero owns unresolved quantitative evidence.
            state["unresolved_stack_candidates"] = {
                "TURN:hero": {
                    "seat": "hero",
                    "street": "TURN",
                    "sources": ["stack_motion"],
                    "ts": 8.0,
                }
            }

            # Retrospective boundary observation says Hero's stack was
            # unchanged at the physical TURN->RIVER boundary.
            result = {
                "type": "boundary_stack_result",
                "request_id": "boundary-release-test",
                "hand_token": "test-token",
                "street": "TURN",
                "boundary_ts": 9.0,
                "ts": 9.5,
                "observations": [{
                    "seat": "hero",
                    "observation": {
                        "seat": "hero",
                        "stack_bb": (
                            hand.players["hero"]
                            .last_confirmed_stack_bb
                        ),
                        "confidence": 0.99,
                        "votes": 5,
                        "mode": "independent_segmentation",
                        "frame_path": "/tmp/turn_boundary.png",
                        "frame_ts": 9.0,
                    },
                }],
            }

            state = sm.handle_boundary_stack_result(
                state,
                result,
            )

            hand = sm.canonical_load()

            # Quantitative blocker correctly prevents premature CHECK.
            checks_before = [
                action
                for action in hand.actions
                if action.street == "TURN"
                and action.seat == "hero"
                and action.action == "CHECK"
            ]

            print(
                "checks before candidate close:",
                checks_before,
            )

            assert not checks_before

            preserved_key = "test-token:TURN"

            preserved = (
                state.get("preserved_boundary_evidence")
                or {}
            )

            print(
                "preserved before close:",
                list(preserved),
            )

            assert preserved_key in preserved

            # The candidate is disproved/removed without a validated
            # quantitative transition. This is the missing release edge.
            state = sm.handle_stack_candidate_closed(
                state,
                {
                    "type": "stack_candidate_closed",
                    "seat": "hero",
                    "street": "TURN",
                    "hand_token": "test-token",
                    "reason": "candidate_removed",
                    "ts": 11.0,
                },
            )

            assert "TURN:hero" not in (
                state.get("unresolved_stack_candidates")
                or {}
            )

            hand = sm.canonical_load()

            checks_after = [
                action
                for action in hand.actions
                if action.street == "TURN"
                and action.seat == "hero"
                and action.action == "CHECK"
            ]

            print(
                "checks after candidate close:",
                [
                    (
                        action.seat,
                        action.action,
                        action.street,
                    )
                    for action in checks_after
                ],
            )

            print(
                "phase after candidate close:",
                state.get("phase"),
            )

            print(
                "board after candidate close:",
                state.get("board"),
            )

            assert len(checks_after) == 1, (
                "RED: preserved TURN boundary evidence was not "
                "reconsidered when its quantitative blocker disappeared"
            )

            # Once Hero's passive action resolves, normal chronology may
            # continue. This test does not require Villain to be inferred;
            # it only proves the blocker-release transaction.
            print(
                "PASS candidate removal replays preserved "
                "boundary evidence"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
