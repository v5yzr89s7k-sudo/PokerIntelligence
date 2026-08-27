from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HAND = "quantitative-authoritative-queue"
STREET = "TURN"


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

            # Deliberately preserve a stale materialized queue.
            hand.players_to_act = [
                "hero",
                "villain",
            ]

            sm.canonical_save(hand)

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

            canonical = sm.canonical_load()
            tracker = sm.tracker_for_hand(canonical)

            # Advance only the authoritative betting-round ownership.
            #
            # Hero's CHECK has already been canonicalized elsewhere in the
            # production boundary transaction. StreetCommitmentTracker owns
            # the outstanding response/traversal obligation, not the semantic
            # action object itself.
            tracker.commitment_tracker.consume_pending_action(
                STREET,
                "hero",
            )

            tracker.commitment_tracker.record_action(
                STREET,
                "hero",
            )

            print(
                "hero tracker action consumed"
            )

            status = (
                tracker.commitment_tracker
                .round_status(STREET)
            )

            owing = list(
                status.get("players_owing_action")
                or []
            )

            print(
                "authoritative owing:",
                owing,
            )

            print(
                "stale canonical queue:",
                list(
                    canonical.players_to_act
                    or []
                ),
            )

            assert owing == ["villain"], (
                "fixture failed: tracker did not expose Villain "
                "as the sole authoritative next actor"
            )

            assert list(
                canonical.players_to_act or []
            ) == [
                "hero",
                "villain",
            ], (
                "fixture failed: canonical queue is not stale"
            )

            sm.canonical_save(canonical)

            event = {
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
                "ts": 3.0,
            }

            state = sm.handle_inferred_action(
                state,
                event,
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

            pending = list(
                state.get("pending_inferred_actions")
                or []
            )

            print(
                "actions:",
                actions,
            )

            print(
                "pending:",
                [
                    (
                        item.get("seat"),
                        item.get("street"),
                        item.get("action"),
                    )
                    for item in pending
                ],
            )

            assert any(
                seat == "villain"
                and action in {
                    "BET",
                    "BET_OR_RAISE",
                    "RAISE",
                }
                for seat, action, street in actions
            ), (
                "RED: quantitative ingestion used stale "
                "canonical.players_to_act instead of authoritative "
                "betting-round ownership"
            )

            assert not any(
                item.get("seat") == "villain"
                for item in pending
            ), (
                "RED: authoritative next actor remained deferred "
                "because of stale canonical queue state"
            )

            print(
                "PASS quantitative replay follows authoritative "
                "betting-round queue"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
