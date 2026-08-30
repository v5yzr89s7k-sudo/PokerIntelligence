from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        old_store = sm.CANONICAL_STORE
        old_state_path = sm.STATE_PATH

        try:
            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=root / "canonical_hand.json",
                text_path=root / "current_hand.txt",
            )
            sm.STATE_PATH = root / "state.json"

            players = [
                {
                    "seat": "hero",
                    "name": "Hero",
                    "stack_bb": 50.0,
                    "is_hero": True,
                    "is_active": True,
                },
                {
                    "seat": "seat_mid_left",
                    "name": "FoldedPlayer",
                    "stack_bb": 50.0,
                    "is_hero": False,
                    "is_active": True,
                },
            ]

            canonical = CanonicalHand().start_hand(
                hand_id="folded-owner-regression",
                players=players,
                hero_cards=["Ah", "Qd"],
                hero_position="SB",
                positions={
                    "hero": "SB",
                    "seat_mid_left": "UTG",
                },
                started_ts=1.0,
            )

            canonical.current_street = "FLOP"
            canonical.players["seat_mid_left"].folded = True
            canonical.players["seat_mid_left"].active = False

            sm.CANONICAL_STORE.save(canonical)

            state = sm.default_state()
            state.update({
                "phase": "FLOP",
                "canonical_snapshot_ready": True,
                "hand_token": "hand-token",
                "unresolved_stack_candidates": {},
                "unresolved_provisional_bets": {},
            })

            state = sm.handle_stack_candidate_opened(
                state,
                {
                    "type": "stack_candidate_opened",
                    "hand_token": "hand-token",
                    "seat": "seat_mid_left",
                    "street": "FLOP",
                    "sources": ["bet_region_appeared"],
                    "ts": 2.0,
                },
            )

            key = "FLOP:seat_mid_left"

            assert key not in state["unresolved_stack_candidates"], (
                "folded player acquired stack-candidate ownership"
            )

            state = sm.handle_provisional_bet_opened(
                state,
                {
                    "type": "provisional_bet_opened",
                    "hand_token": "hand-token",
                    "seat": "seat_mid_left",
                    "street": "FLOP",
                    "source": "transition",
                    "bet_bb": 3.0,
                    "ts": 2.1,
                },
            )

            assert key not in state["unresolved_provisional_bets"], (
                "folded player acquired provisional-bet ownership"
            )

            ownership = sm.unresolved_board_ownership(
                state,
                "FLOP",
            )

            assert not ownership["blocked"], ownership

            print(
                "PASS: folded/inactive player cannot reacquire "
                "postflop commitment ownership"
            )

        finally:
            sm.CANONICAL_STORE = old_store
            sm.STATE_PATH = old_state_path


if __name__ == "__main__":
    main()
