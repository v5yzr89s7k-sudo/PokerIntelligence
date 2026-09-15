from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


TOKEN = "actor-observed-single-seat-ownership"


def main():
    old_store = sm.CANONICAL_STORE

    with TemporaryDirectory() as tmp:
        try:
            root = Path(tmp)

            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=root / "canonical.json",
                text_path=root / "current_hand.txt",
            )

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
                        "seat": "hj",
                        "name": "HJ",
                        "stack_bb": 50.0,
                        "is_active": True,
                    },
                    {
                        "seat": "co",
                        "name": "CO",
                        "stack_bb": 50.0,
                        "is_active": True,
                    },
                    {
                        "seat": "btn",
                        "name": "BTN",
                        "stack_bb": 50.0,
                        "is_active": True,
                    },
                    {
                        "seat": "sb",
                        "name": "SB",
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
                hero_cards=["2c", "9s"],
                hero_position="BB",
                positions={
                    "utg": "UTG",
                    "hj": "HJ",
                    "co": "CO",
                    "btn": "BTN",
                    "sb": "SB",
                    "hero": "BB",
                },
                started_ts=1.0,
            )

            hand.current_street = "PREFLOP"

            hand.players_to_act = [
                "utg",
                "hj",
                "co",
                "btn",
                "sb",
                "hero",
            ]

            sm.CANONICAL_STORE.save(hand)

            state = sm.default_state()
            state["hand_token"] = TOKEN
            state["phase"] = "PREFLOP"
            state["canonical_snapshot_ready"] = True

            before = sm.canonical_load()

            print("===== BEFORE =====")
            print(
                "queue:",
                before.players_to_act,
            )
            print(
                "actions:",
                [
                    (a.seat, a.action, a.source)
                    for a in before.actions
                ],
            )

            state = sm.handle_actor_observed(
                state,
                {
                    "type": "actor_observed",
                    "hand_token": TOKEN,
                    "street": "PREFLOP",
                    "seat": "hero",
                    "source": "bet_region_appeared",
                    "commitment_visible": True,
                    "blocked_seats": [],
                    "ts": 10.0,
                },
            )

            after = sm.canonical_load()

            print()
            print("===== AFTER ACTOR_OBSERVED =====")
            print(
                "queue:",
                after.players_to_act,
            )
            print(
                "actions:",
                [
                    (a.seat, a.action, a.source)
                    for a in after.actions
                ],
            )

            predecessor_seats = {
                "utg",
                "hj",
                "co",
                "btn",
                "sb",
            }

            fabricated = [
                a
                for a in after.actions
                if (
                    a.seat in predecessor_seats
                    and a.source
                    == "action_order_inference"
                )
            ]

            print()
            print(
                "fabricated_predecessors:",
                [
                    (
                        a.seat,
                        a.action,
                        a.source,
                    )
                    for a in fabricated
                ],
            )

            assert fabricated == [], (
                "RED: actor_observed for Hero authored "
                "semantic actions for predecessor seats: "
                + repr([
                    (
                        a.seat,
                        a.action,
                        a.source,
                    )
                    for a in fabricated
                ])
            )

            for seat in predecessor_seats:
                player = after.players[seat]

                assert player.folded is False, (
                    f"RED: actor_observed for Hero "
                    f"folded predecessor {seat}"
                )

                assert player.active is True, (
                    f"RED: actor_observed for Hero "
                    f"made predecessor {seat} inactive"
                )

            # Synchronization must also survive the canonical-store
            # boundary used by record_physical_live_commitment().
            #
            # A tracker-only queue mutation is not sufficient: the next
            # production step reloads CanonicalHand from storage.
            assert after.players_to_act == [
                "utg",
                "hj",
                "co",
                "btn",
                "sb",
                "hero",
            ], (
                "RED: actor observation consumed unowned predecessor "
                "betting obligations: "
                + repr(after.players_to_act)
            )

            from src.state.action_timeline import (
                active_actions,
            )

            durable = active_actions(
                state,
                TOKEN,
            )

            hero_actions = [
                item
                for item in durable
                if (
                    item.get("street") == "PREFLOP"
                    and item.get("seat") == "hero"
                )
            ]

            print(
                "durable_hero_actions:",
                hero_actions,
            )

            assert len(hero_actions) == 1, (
                "RED: later Hero physical commitment was dropped merely "
                "because unresolved predecessor obligations remain ahead "
                "of Hero in canonical chronology"
            )

            assert hero_actions[0]["action"] == "COMMITMENT", (
                "RED: unresolved chronology gave later Hero evidence "
                "premature betting semantics: "
                + repr(hero_actions[0])
            )

            canonical_hero_actions = [
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

            assert canonical_hero_actions == [], (
                "RED: unresolved predecessor chronology allowed Hero "
                "physical evidence to project canonically: "
                + repr(canonical_hero_actions)
            )

            print()
            print(
                "PASS: actor_observed owns only the observed seat, "
                "persists chronology synchronization, and admits that "
                "seat's durable physical action"
            )

        finally:
            sm.CANONICAL_STORE = old_store


if __name__ == "__main__":
    main()
