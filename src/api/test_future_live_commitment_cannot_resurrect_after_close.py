from pathlib import Path
import tempfile

import src.api.api_event_state_machine as sm

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


ACTOR = "actor"
TOKEN = "future-live-retirement-test"


def build_hand():
    hand = CanonicalHand().start_hand(
        hand_id="future-live-retirement",
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

            state = sm.default_state()

            state["phase"] = "PREFLOP"
            state["hand_token"] = TOKEN
            state[
                "canonical_snapshot_ready"
            ] = True

            event = {
                "type": "actor_observed",
                "hand_token": TOKEN,
                "street": "FLOP",
                "seat": ACTOR,
                "source": "bet_region_appeared",
                "commitment_visible": True,
                "blocked_seats": [],
                "ts": 2.0,
            }

            state = sm.handle_actor_observed(
                state,
                event,
            )

            key = f"FLOP:{ACTOR}"

            pending = dict(
                state.get(
                    "pending_live_commitments"
                )
                or {}
            )

            assert key in pending, (
                "setup failure: future commitment "
                "was not presented"
            )

            text = (
                root
                / "current_hand.txt"
            ).read_text()

            assert (
                "commits chips"
                in text.lower()
            ), (
                "setup failure: future commitment "
                "did not reach TXT"
            )

            print(
                "initial pending:",
                pending,
            )

            print()
            print(
                "===== INITIAL TXT ====="
            )
            print(text)

            # Existing lifecycle close event for the same
            # street/seat. This should permanently retire
            # presentation-only ownership as well.
            state = (
                sm.handle_provisional_bet_closed(
                    state,
                    {
                        "type":
                            "provisional_bet_closed",
                        "hand_token": TOKEN,
                        "street": "FLOP",
                        "seat": ACTOR,
                        "reason": "resolved",
                        "ts": 3.0,
                    },
                )
            )

            pending_after_close = dict(
                state.get(
                    "pending_live_commitments"
                )
                or {}
            )

            print(
                "pending after close:",
                pending_after_close,
            )

            # Force another presentation refresh. If stale
            # ownership survived, the line will resurrect.
            state = (
                sm.refresh_live_presentation(
                    state
                )
            )

            final_pending = dict(
                state.get(
                    "pending_live_commitments"
                )
                or {}
            )

            final_text = (
                root
                / "current_hand.txt"
            ).read_text()

            print()
            print(
                "===== AFTER CLOSE + REFRESH ====="
            )

            print(
                "pending:",
                final_pending,
            )

            print(final_text)

            assert key not in final_pending, (
                "RED: closed future physical "
                "presentation retained stale ownership"
            )

            assert (
                "commits chips"
                not in final_text.lower()
            ), (
                "RED: closed future physical "
                "presentation resurrected in TXT"
            )

            canonical = store.load()

            assert (
                canonical.current_street
                == "PREFLOP"
            ), (
                "presentation retirement mutated "
                "canonical street"
            )

            assert not canonical.actions, (
                "presentation retirement created "
                "canonical action"
            )

            print(
                "PASS: closed future presentation "
                "cannot resurrect"
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
