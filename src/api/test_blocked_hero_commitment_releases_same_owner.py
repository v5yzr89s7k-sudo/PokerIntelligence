import copy
import tempfile
from pathlib import Path

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="blocked-hero-release-same-owner",
        players=[
            {
                "seat": "utg",
                "name": "UTG",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
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

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        store = CanonicalHandStore(
            json_path=root / "canonical_hand.json",
            text_path=root / "current_hand.txt",
        )

        sm.CANONICAL_STORE = store

        try:
            hand = make_hand()
            store.save(hand)

            state = sm.default_state()

            state.update({
                "phase": "PREFLOP",
                "hand_token": hand.hand_id,
                "canonical_snapshot_ready": True,
                "dealt_in_seats": [
                    "utg",
                    "hero",
                ],
                "positions": {
                    "utg": "UTG",
                    "hero": "BB",
                },
            })

            event = {
                "type": "actor_observed",
                "hand_token": hand.hand_id,
                "street": "PREFLOP",
                "seat": "hero",
                "ts": 10.0,
                "source": "bet_region_appeared",
                "commitment_visible": True,
            }

            print("===== BLOCK HERO =====")
            print(
                "queue_before:",
                store.load().players_to_act,
            )

            state = sm.handle_actor_observed(
                state,
                copy.deepcopy(event),
            )

            blocked_hand = store.load()

            blocked_owners = [
                item
                for item in (
                    state.get("action_timeline")
                    or []
                )
                if item.get("hand_token")
                == hand.hand_id
                and item.get("street")
                == "PREFLOP"
                and item.get("seat")
                == "hero"
            ]

            print(
                "queue_blocked:",
                blocked_hand.players_to_act,
            )
            print(
                "blocked_owners:",
                blocked_owners,
            )
            print(
                "pending_actor_observations:",
                state.get(
                    "pending_actor_observations"
                ),
            )

            assert (
                blocked_hand.players_to_act
                == ["utg", "hero"]
            ), (
                "setup failure: blocked Hero observation "
                "consumed unresolved UTG chronology"
            )

            assert len(blocked_owners) == 1, (
                "setup failure: blocked Hero must have "
                "exactly one durable ActionTimeline owner"
            )

            assert (
                blocked_owners[0].get("action")
                == "COMMITMENT"
            ), (
                "setup failure: blocked Hero owner must "
                "remain generic COMMITMENT"
            )

            original_key = blocked_owners[0]["key"]

            canonical_hero_before = [
                action
                for action in blocked_hand.actions
                if action.street == "PREFLOP"
                and action.seat == "hero"
                and action.action.upper()
                not in {
                    "POST_SMALL_BLIND",
                    "POST_BIG_BLIND",
                    "POST_ANTE",
                }
            ]

            assert canonical_hero_before == [], (
                "setup failure: blocked Hero commitment "
                "must not already be canonical"
            )

            # -------------------------------------------------
            # Simulate authoritative predecessor completion.
            #
            # We are testing the release boundary, not UTG's
            # perception mechanism. UTG's obligation is now
            # definitively gone; Hero becomes canonical head.
            # -------------------------------------------------

            released_hand = store.load()

            released_hand.players_to_act = [
                "hero",
            ]

            store.save(released_hand)

            print()
            print("===== RELEASE PREDECESSOR =====")
            print(
                "queue_released:",
                store.load().players_to_act,
            )

            # The real system invokes this after the blocker
            # disappears / predecessor action becomes canonical.
            state = sm.replay_pending_actor_observations(
                state
            )

            final_hand = store.load()

            hero_owners = [
                item
                for item in (
                    state.get("action_timeline")
                    or []
                )
                if item.get("hand_token")
                == hand.hand_id
                and item.get("street")
                == "PREFLOP"
                and item.get("seat")
                == "hero"
            ]

            canonical_hero = [
                action
                for action in final_hand.actions
                if action.street == "PREFLOP"
                and action.seat == "hero"
                and action.action.upper()
                not in {
                    "POST_SMALL_BLIND",
                    "POST_BIG_BLIND",
                    "POST_ANTE",
                }
            ]

            print()
            print("===== AFTER RELEASE REPLAY =====")
            print(
                "queue:",
                final_hand.players_to_act,
            )
            print(
                "hero_owners:",
                hero_owners,
            )
            print(
                "canonical_hero:",
                [
                    (
                        action.seat,
                        action.action,
                        action.amount_bb,
                        action.raise_to_bb,
                    )
                    for action in canonical_hero
                ],
            )
            print(
                "pending_actor_observations:",
                state.get(
                    "pending_actor_observations"
                ),
            )

            assert len(hero_owners) == 1, (
                "RED: releasing blocked Hero created or "
                "lost ActionTimeline ownership; exactly "
                "one durable owner must survive"
            )

            assert (
                hero_owners[0].get("key")
                == original_key
            ), (
                "RED: blocked Hero release replaced the "
                "original ActionTimeline owner instead "
                "of refining the same action identity"
            )

            assert (
                hero_owners[0].get("action")
                != "COMMITMENT"
            ), (
                "RED: Hero became canonical queue head "
                "but the retained physical COMMITMENT "
                "was never semantically released/refined"
            )

            assert len(canonical_hero) == 1, (
                "RED: released Hero physical action was "
                "not projected exactly once to canonical "
                "chronology"
            )

            assert (
                canonical_hero[0].action.upper()
                == str(
                    hero_owners[0].get("action")
                    or ""
                ).upper()
            ), (
                "RED: canonical Hero semantic does not "
                "match the surviving ActionTimeline owner"
            )

            print()
            print(
                "PASS: blocked Hero COMMITMENT releases "
                "through the same durable owner and "
                "projects exactly once"
            )

        finally:
            sm.CANONICAL_STORE = original_store


if __name__ == "__main__":
    main()
