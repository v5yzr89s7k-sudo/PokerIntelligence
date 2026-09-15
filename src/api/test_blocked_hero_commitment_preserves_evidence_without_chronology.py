from pathlib import Path
import tempfile

import src.api.api_event_state_machine as sm
from src.state.action_timeline import active_actions
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


TOKEN = "blocked-hero-physical-evidence"


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id=TOKEN,
        players=[
            {
                "seat": "utg",
                "name": "UTG",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions={
            "utg": "UTG",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.players_to_act = [
        "utg",
        "hero",
    ]

    return hand


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
            state["hand_token"] = TOKEN
            state["phase"] = "PREFLOP"
            state["canonical_snapshot_ready"] = True

            # Explicit unresolved predecessor evidence.
            state[
                "unresolved_stack_candidates"
            ] = {
                "PREFLOP:utg": {
                    "seat": "utg",
                    "street": "PREFLOP",
                    "sources": [
                        "stack_motion",
                    ],
                    "ts": 9.0,
                    "awaiting_action": True,
                    "resolved_reason": (
                        "validated_stack_transition"
                    ),
                }
            }

            sm.canonical_save(
                hand,
                state=state,
            )

            before = sm.canonical_load()

            print("===== BEFORE =====")
            print(
                "queue:",
                before.players_to_act,
            )

            event = {
                "type": "actor_observed",
                "hand_token": TOKEN,
                "street": "PREFLOP",
                "seat": "hero",
                "source": "bet_region_appeared",
                "commitment_visible": True,
                "ts": 10.0,
            }

            state = sm.handle_actor_observed(
                state,
                event,
                preserve_if_blocked=True,
            )

            after = sm.canonical_load()

            durable = active_actions(
                state,
                TOKEN,
            )

            hero_actions = [
                item
                for item in durable
                if (
                    item.get("street")
                    == "PREFLOP"
                    and item.get("seat")
                    == "hero"
                )
            ]

            canonical_hero = [
                action
                for action in after.actions
                if (
                    action.street == "PREFLOP"
                    and action.seat == "hero"
                    and action.action not in {
                        "POST_BIG_BLIND",
                        "POST_SMALL_BLIND",
                        "POST_ANTE",
                    }
                )
            ]

            print()
            print("===== AFTER =====")
            print(
                "queue:",
                after.players_to_act,
            )
            print(
                "durable_hero_actions:",
                hero_actions,
            )
            print(
                "canonical_hero_actions:",
                [
                    (
                        action.action,
                        action.amount_bb,
                        action.raise_to_bb,
                    )
                    for action in canonical_hero
                ],
            )

            assert after.players_to_act == [
                "utg",
                "hero",
            ], (
                "RED: blocked Hero observation consumed "
                "the unresolved UTG obligation"
            )

            assert len(hero_actions) == 1, (
                "RED: blocked Hero physical commitment "
                "was not retained by ActionTimeline"
            )

            assert (
                hero_actions[0].get("action")
                == "COMMITMENT"
            ), (
                "RED: blocked Hero evidence was given "
                "premature betting semantics: "
                + repr(hero_actions[0])
            )

            assert canonical_hero == [], (
                "RED: blocked Hero physical evidence "
                "projected canonically before predecessor "
                "chronology was resolved"
            )

            print()
            print(
                "PASS: blocked Hero physical commitment "
                "is durable without consuming or "
                "projecting unresolved chronology"
            )

        finally:
            sm.CANONICAL_STORE = original_store


if __name__ == "__main__":
    main()
