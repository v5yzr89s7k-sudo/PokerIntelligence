from pathlib import Path
import tempfile

import src.api.api_event_state_machine as sm

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


ACTOR = "actor"


def build_hand():
    hand = CanonicalHand().start_hand(
        hand_id="future-street-presentation",
        players=[
            {
                "seat": ACTOR,
                "name": "Actor",
                "stack_bb": None,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=[],
        hero_position="unknown",
        positions={
            ACTOR: "X",
        },
        started_ts=1.0,
    )

    hand.dealt_in_seats = [
        ACTOR,
    ]

    hand.current_street = "PREFLOP"

    return hand


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        original_store = sm.CANONICAL_STORE
        original_tracker = sm._ACTIVE_TRACKER
        original_hand_id = sm._ACTIVE_HAND_ID

        try:
            store = CanonicalHandStore(
                json_path=(
                    root
                    / "canonical_hand.json"
                ),
                text_path=(
                    root
                    / "current_hand.txt"
                ),
            )

            sm.CANONICAL_STORE = store
            sm._ACTIVE_TRACKER = None
            sm._ACTIVE_HAND_ID = None

            hand = build_hand()
            store.save(hand)

            before = store.load()

            before_street = (
                before.current_street
            )

            before_actions = [
                (
                    action.seat,
                    action.street,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in before.actions
            ]

            before_queue = list(
                before.players_to_act
                or []
            )

            state = sm.default_state()

            state["phase"] = (
                before_street
            )

            state[
                "hand_token"
            ] = "future-presentation-test"

            state[
                "canonical_snapshot_ready"
            ] = True

            state[
                "pending_live_commitments"
            ] = {}

            event = {
                "type": "actor_observed",
                "hand_token": (
                    "future-presentation-test"
                ),
                "street": "FLOP",
                "seat": ACTOR,
                "source": (
                    "bet_region_appeared"
                ),
                "commitment_visible": True,
                "blocked_seats": [],
                "ts": 2.0,
            }

            state = (
                sm.handle_actor_observed(
                    state,
                    event,
                )
            )

            pending = dict(
                state.get(
                    "pending_live_commitments"
                )
                or {}
            )

            after = store.load()

            after_actions = [
                (
                    action.seat,
                    action.street,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in after.actions
            ]

            print(
                "pending presentation:",
                pending,
            )

            print(
                "canonical street:",
                after.current_street,
            )

            print(
                "canonical queue:",
                after.players_to_act,
            )

            print(
                "canonical actions:",
                after_actions,
            )

            assert pending, (
                "RED: trustworthy immediate-next-street "
                "physical commitment was discarded "
                "instead of entering presentation state"
            )

            assert any(
                str(
                    item.get("street")
                    or ""
                ).upper()
                == str(
                    event.get("street")
                    or ""
                ).upper()
                and str(
                    item.get("seat")
                    or ""
                )
                == ACTOR
                for item in pending.values()
                if isinstance(
                    item,
                    dict,
                )
            ), (
                "RED: presentation state does not own "
                "the observed future-street commitment"
            )

            live_path = (
                root
                / "current_hand.txt"
            )

            live_text = (
                live_path.read_text()
                if live_path.exists()
                else ""
            )

            print()
            print(
                "===== PRESENTATION TXT ====="
            )
            print(live_text)

            observed_street = str(
                event.get("street")
                or ""
            ).upper()

            assert observed_street in live_text, (
                "RED: physically observed next street "
                "is absent from live TXT while canonical "
                "board recognition is still pending"
            )

            presentation_item = next(
                item
                for item in pending.values()
                if (
                    isinstance(item, dict)
                    and str(
                        item.get("street")
                        or ""
                    ).upper()
                    == observed_street
                    and str(
                        item.get("seat")
                        or ""
                    )
                    == ACTOR
                )
            )

            presentation_action = str(
                presentation_item.get("action")
                or ""
            ).upper()

            rendered_verb = {
                "BET": "bets",
                "BET_OR_RAISE": "bets or raises",
                "CALL_OR_RAISE": "calls or raises",
                "COMMITMENT": "commits chips",
            }.get(
                presentation_action
            )

            assert rendered_verb, (
                "test received unsupported presentation action"
            )

            assert rendered_verb in live_text.lower(), (
                "RED: future-street physical commitment "
                "entered presentation ownership but was "
                "not rendered into live TXT"
            )

            assert (
                after.current_street
                == before_street
            ), (
                "presentation-only evidence "
                "advanced canonical street"
            )

            assert (
                list(
                    after.players_to_act
                    or []
                )
                == before_queue
            ), (
                "presentation-only evidence "
                "mutated canonical chronology queue"
            )

            assert (
                after_actions
                == before_actions
            ), (
                "presentation-only evidence "
                "created a canonical action"
            )

            print(
                "PASS future-street presentation: "
                "immediate-next-street physical evidence "
                "enters presentation ownership without "
                "canonical mutation"
            )

        finally:
            sm.CANONICAL_STORE = (
                original_store
            )

            sm._ACTIVE_TRACKER = (
                original_tracker
            )

            sm._ACTIVE_HAND_ID = (
                original_hand_id
            )


if __name__ == "__main__":
    main()
