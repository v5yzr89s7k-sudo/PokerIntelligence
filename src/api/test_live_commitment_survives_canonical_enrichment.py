from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


SEAT = "seat_upper_right"


def make_hand():
    players = [
        {
            "seat": SEAT,
            "name": "",
            "stack_bb": 100.0,
            "is_hero": False,
            "is_active": True,
        },
        {
            "seat": "hero",
            "name": "",
            "stack_bb": 50.0,
            "is_hero": True,
            "is_active": True,
        },
    ]

    hand = CanonicalHand().start_hand(
        hand_id="test-live-presentation",
        players=players,
        hero_cards=["As", "Kd"],
        hero_position="HJ",
        positions={
            SEAT: "UTG",
            "hero": "HJ",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"

    return hand


def main():
    original_store = sm.CANONICAL_STORE

    with TemporaryDirectory() as tmp:
        try:
            root = Path(tmp)

            store = CanonicalHandStore(
                json_path=root / "canonical_hand.json",
                text_path=root / "current_hand.txt",
            )

            sm.CANONICAL_STORE = store

            hand = make_hand()
            store.save(hand)

            state = sm.default_state()
            state["phase"] = "PREFLOP"
            state["canonical_snapshot_ready"] = True
            state["hand_token"] = "test-live-presentation"

            state["pending_live_commitments"] = {
                f"PREFLOP:{SEAT}": {
                    "seat": SEAT,
                    "street": "PREFLOP",
                    "action": "BET_OR_RAISE",
                    "source": "bet_region_appeared",
                    "ts": 2.0,
                }
            }

            state = sm.refresh_live_presentation(state)

            before = store.text_path.read_text()

            print(
                "===== BEFORE CANONICAL ENRICHMENT ====="
            )
            print(before)

            assert "UTG bets or raises" in before

            # Ordinary asynchronous canonical enrichment must not
            # erase presentation ownership still held by state.
            hand = store.load()
            hand.players[SEAT].name = "LownWolf"

            sm.canonical_save(
                hand,
                state=state,
            )

            after = store.text_path.read_text()

            print(
                "===== AFTER CANONICAL ENRICHMENT ====="
            )
            print(after)

            assert "UTG" in after
            assert "LownWolf" in after

            assert "bets or raises" in after, (
                "BUG: ordinary canonical persistence erased "
                "an already-published fast live commitment"
            )

            # Canonical JSON must remain presentation-free.
            restored = store.load()

            assert not [
                action
                for action in restored.actions
                if action.seat == SEAT
            ], (
                "presentation-only commitment leaked into "
                "authoritative canonical actions"
            )

            print(
                "PASS: state-machine canonical persistence "
                "cannot erase live presentation ownership"
            )

        finally:
            sm.CANONICAL_STORE = original_store


if __name__ == "__main__":
    main()
