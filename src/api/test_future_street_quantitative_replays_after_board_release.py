from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HAND = "future-street-quantitative-replay"


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

            hand.current_street = "TURN"
            hand.board = ["Ac", "7d", "2s", "9h"]
            hand.players_to_act = []
            sm.canonical_save(hand)

            tracker = sm.tracker_for_hand(hand)

            # TURN is already semantically complete. The RIVER board is
            # physically confirmed but has not yet been promoted.
            tracker.commitment_tracker.reset_street("TURN")
            tracker.commitment_tracker.initialize_street_order(
                "TURN",
                ["hero", "villain"],
            )
            tracker.commitment_tracker.sync_queue(
                "TURN",
                [],
            )

            state = sm.default_state()
            state.update({
                "phase": "TURN",
                "hand_token": HAND,
                "canonical_snapshot_ready": True,
                "board": ["Ac", "7d", "2s", "9h"],
                "pending_board_events": [
                    {
                        "board": [
                            "Ac",
                            "7d",
                            "2s",
                            "9h",
                            "3c",
                        ],
                        "ts": 10.0,
                    }
                ],
            })

            # Real July 22 ordering: Birkam's bet-region onset first proves
            # that Birkam has begun acting on RIVER. Hero is the legitimate
            # earlier actor, so this observation must survive the temporary
            # TURN/RIVER canonical boundary and later resolve Hero CHECK.
            river_actor_observed = {
                "type": "actor_observed",
                "hand_token": HAND,
                "seat": "villain",
                "street": "RIVER",
                "source": "bet_region_appeared",
                "blocked_seats": [],
                "ts": 10.5,
            }

            state = sm.handle_actor_observed(
                state,
                river_actor_observed,
            )

            pending_actor = list(
                state.get("pending_actor_observations")
                or []
            )

            print(
                "pending actor before board release:",
                [
                    (
                        item.get("street"),
                        item.get("seat"),
                        item.get("source"),
                    )
                    for item in pending_actor
                ],
            )

            assert any(
                item.get("street") == "RIVER"
                and item.get("seat") == "villain"
                for item in pending_actor
            ), (
                "RED: future-street actor observation was discarded "
                "while canonical still owned TURN"
            )

            river_bet = {
                "type": "inferred_action",
                "hand_token": HAND,
                "episode_id": 8,
                "seat": "villain",
                "street": "RIVER",
                "action": "BET_OR_RAISE",
                "confidence": 0.99,
                "evidence": [
                    "bet_region_occupied",
                    "stack_changed",
                ],
                "measurements": {
                    "stack_change": {
                        "changed": True,
                        "previous_stack_bb": 50.0,
                        "current_stack_bb": 43.25,
                        "delta_bb": 6.75,
                        "origin_street": "RIVER",
                        "stack_read_confidence": 0.99,
                        "stack_read_mode": "independent_confirmed",
                    },
                    "commitment_sequence": True,
                },
                "ts": 11.0,
            }

            # This action is objectively RIVER evidence. Because canonical
            # chronology still owns TURN, it must survive rather than being
            # rejected as a street mismatch.
            state = sm.handle_inferred_action(
                state,
                river_bet,
            )

            pending = list(
                state.get("pending_inferred_actions")
                or []
            )

            print(
                "pending before board release:",
                [
                    (
                        item.get("street"),
                        item.get("seat"),
                        item.get("action"),
                    )
                    for item in pending
                ],
            )

            assert any(
                item.get("street") == "RIVER"
                and item.get("seat") == "villain"
                and item.get("action") == "BET_OR_RAISE"
                for item in pending
            ), (
                "RED: valid future-street quantitative action was "
                "discarded while canonical still owned the prior street"
            )

            state = sm.release_pending_board_if_ready(
                state
            )

            canonical = sm.canonical_load()

            river_actions = [
                (
                    action.seat,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in canonical.actions
                if str(action.street).upper() == "RIVER"
            ]

            pending_after = list(
                state.get("pending_inferred_actions")
                or []
            )

            print(
                "river actions after release:",
                river_actions,
            )
            print(
                "pending after release:",
                [
                    (
                        item.get("street"),
                        item.get("seat"),
                        item.get("action"),
                    )
                    for item in pending_after
                ],
            )

            assert canonical.current_street == "RIVER"

            # Birkam/Villain was physically observed acting on RIVER before
            # his quantitative bet settled. Once RIVER becomes canonical,
            # replaying that observation must resolve Hero's safe passive
            # predecessor first, then release the already-buffered bet.
            assert len(river_actions) >= 2, (
                "RED: future-street actor observation did not "
                "release RIVER chronology after board promotion"
            )

            assert (
                river_actions[0][0] == "hero"
                and river_actions[0][1] == "CHECK"
            ), (
                "RED: observing Villain act on RIVER did not resolve "
                "Hero's preceding RIVER CHECK"
            )

            assert (
                river_actions[1][0] == "villain"
                and river_actions[1][1]
                in {"BET", "BET_OR_RAISE", "RAISE"}
            ), (
                "RED: Villain's preserved 6.75 BB RIVER bet was not "
                "accepted after Hero's CHECK resolved"
            )

            assert not any(
                item.get("street") == "RIVER"
                and item.get("seat") == "villain"
                for item in pending_after
            ), (
                "RED: accepted RIVER quantitative action remained "
                "stranded after chronology advancement"
            )

            pending_actor_after = list(
                state.get("pending_actor_observations")
                or []
            )

            assert not any(
                item.get("street") == "RIVER"
                and item.get("seat") == "villain"
                for item in pending_actor_after
            ), (
                "RED: consumed RIVER actor observation remained pending"
            )

            print(
                "PASS: future-street actor observation survives the "
                "boundary, resolves Hero CHECK, and releases Villain BET"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
