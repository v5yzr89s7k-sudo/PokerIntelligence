from pathlib import Path
import tempfile

import src.api.api_event_state_machine as sm

from src.state.action_timeline import active_actions
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


TOKEN = "blocked-opponent-physical-evidence"


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id=TOKEN,
        players=[
            {
                "seat": "co",
                "name": "CO",
                "stack_bb": 39.27,
                "is_active": True,
            },
            {
                "seat": "btn",
                "name": "BTN",
                "stack_bb": 92.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 12.92,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions={
            "co": "CO",
            "btn": "BTN",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"

    hand.players_to_act = [
        "co",
        "btn",
        "hero",
    ]

    return hand


def voluntary_actions(hand):
    forced = {
        "POST_ANTE",
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
    }

    return [
        action
        for action in hand.actions
        if action.action.upper() not in forced
    ]


def main():
    original_store = sm.CANONICAL_STORE

    with tempfile.TemporaryDirectory() as tmp:
        try:
            root = Path(tmp)

            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=root / "canonical_hand.json",
                text_path=root / "current_hand.txt",
            )

            hand = make_hand()

            state = sm.default_state()

            state.update({
                "phase": "PREFLOP",
                "hand_token": TOKEN,
                "canonical_snapshot_ready": True,

                # CO is the first owned unresolved chronology obligation.
                "observer_acquisition_frontier": {
                    "street": "PREFLOP",
                    "first_owned_seat": "co",
                    "pre_acquisition_seats": [],
                    "owned_queue": [
                        "co",
                        "btn",
                        "hero",
                    ],
                    "ts": 1.0,
                },

                # CO remains unresolved while BTN is positively observed
                # committing chips behind it.
                "unresolved_stack_candidates": {
                    "PREFLOP:co": {
                        "seat": "co",
                        "street": "PREFLOP",
                        "sources": [
                            "bet_region_appeared",
                        ],
                        "ts": 9.0,
                    },
                },
            })

            sm.canonical_save(
                hand,
                state=state,
            )

            event = {
                "type": "actor_observed",
                "hand_token": TOKEN,
                "street": "PREFLOP",
                "seat": "btn",
                "source": "bet_region_appeared",
                "commitment_visible": True,
                "blocked_seats": [
                    "co",
                ],
                "ts": 10.0,
            }

            state = sm.handle_actor_observed(
                state,
                event,
                preserve_if_blocked=True,
            )

            after = sm.canonical_load()

            owners = [
                item
                for item in active_actions(
                    state,
                    TOKEN,
                )
                if (
                    item.get("street") == "PREFLOP"
                    and item.get("seat") == "btn"
                )
            ]

            canonical_actions = voluntary_actions(
                after
            )

            print("queue:", after.players_to_act)
            print("owners:", owners)
            print(
                "canonical_actions:",
                [
                    (
                        a.seat,
                        a.action,
                        a.amount_bb,
                        a.raise_to_bb,
                    )
                    for a in canonical_actions
                ],
            )

            assert after.players_to_act == [
                "co",
                "btn",
                "hero",
            ], (
                "blocked CO physical observation "
                "advanced chronology"
            )

            assert len(owners) == 1, (
                "RED: positively observed blocked opponent "
                "commitment has no durable ActionTimeline owner"
            )

            assert owners[0].get("action") == "COMMITMENT", (
                "RED: blocked opponent physical evidence "
                "received invented poker semantics: "
                + repr(owners[0])
            )

            assert owners[0].get("amount_bb") is None
            assert owners[0].get("raise_to_bb") is None

            assert canonical_actions == [], (
                "RED: generic blocked opponent commitment "
                "was projected into canonical chronology"
            )

            print()
            print(
                "PASS: blocked opponent physical commitment "
                "is durable as generic COMMITMENT without "
                "advancing, classifying, sizing, or projecting "
                "canonical chronology"
            )

        finally:
            sm.CANONICAL_STORE = original_store


if __name__ == "__main__":
    main()
