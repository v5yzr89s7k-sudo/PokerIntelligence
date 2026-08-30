from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HAND = "boundary-motion-passive-test"
STREET = "TURN"


def make_hand():
    players = [
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 20.0,
            "stack_text": "20.0 BB",
            "is_hero": True,
            "is_active": True,
        },
        {
            "seat": "villain",
            "name": "Villain",
            "stack_bb": 50.0,
            "stack_text": "50.0 BB",
            "is_hero": False,
            "is_active": True,
        },
    ]

    positions = {
        "hero": "SB",
        "villain": "BB",
    }

    hand = CanonicalHand().start_hand(
        hand_id=HAND,
        players=players,
        hero_cards=["Ah", "Kd"],
        hero_position="SB",
        positions=positions,
        started_ts=1.0,
    )

    hand.dealt_in_seats = [
        "hero",
        "villain",
    ]

    hand.current_street = STREET
    hand.board = [
        "Jd",
        "9s",
        "Tc",
        "9h",
    ]

    # Use the July 22 semantic condition we actually care about:
    # both TURN actors remain unresolved when the RIVER boundary arrives.
    hand.players_to_act = [
        "villain",
        "hero",
    ]

    return hand


def bootstrap_tracker(hand):
    tracker = sm.tracker_for_hand(hand)

    ct = tracker.commitment_tracker
    ct.reset_street(STREET)
    ct.initialize_street_order(
        STREET,
        ["villain", "hero"],
    )
    ct.sync_queue(
        STREET,
        ["villain", "hero"],
    )

    return tracker


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

            tracker = bootstrap_tracker(
                sm.canonical_load()
            )

            state = sm.default_state()
            state.update({
                "phase": STREET,
                "hand_token": HAND,
                "canonical_snapshot_ready": True,
                "pending_board_events": [{
                    "board": [
                        "Jd",
                        "9s",
                        "Tc",
                        "9h",
                        "7h",
                    ],
                    "ts": 10.0,
                }],
                "unresolved_stack_candidates": {
                    "TURN:villain": {
                        "seat": "villain",
                        "street": STREET,
                        "sources": ["stack_motion"],
                        "awaiting_action": False,
                        "ts": 8.0,
                    },
                    "TURN:hero": {
                        "seat": "hero",
                        "street": STREET,
                        "sources": ["stack_motion"],
                        "awaiting_action": False,
                        "ts": 8.1,
                    },
                },
            })

            ownership = sm.unresolved_board_ownership(
                state,
                STREET,
            )

            print("ownership:", ownership)

            assert ownership["blocked"] is False
            assert ownership["commitment_candidates"] == []

            canonical = sm.canonical_load()

            state, resolved = (
                sm.resolve_silent_boundary_obligations(
                    state,
                    canonical=canonical,
                    tracker=tracker,
                    street=STREET,
                    observed_seats=set(),
                    reconsider_observed_after_candidate_release=False,
                )
            )

            print("resolved:", resolved)

            actions = [
                (
                    action.seat,
                    action.action,
                    action.street,
                )
                for action in canonical.actions
                if str(action.street).upper() == STREET
            ]

            print("actions:", actions)

            assert actions == [
                ("villain", "CHECK", STREET),
                ("hero", "CHECK", STREET),
            ], (
                "RED: raw motion-only candidates vetoed "
                "uniquely implied TURN checks despite "
                "no quantitative commitment ownership"
            )

            print(
                "PASS: motion-only hypotheses cannot veto "
                "passive next-street boundary chronology"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
