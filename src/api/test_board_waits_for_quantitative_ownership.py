from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand_store import CanonicalHandStore


def bootstrap(root):
    sm.CANONICAL_STORE = CanonicalHandStore(
        json_path=root / "canonical_hand.json",
        text_path=root / "current_hand.txt",
    )

    state = sm.default_state()

    state = sm.handle_hero_cards(
        state,
        {
            "type": "hero_cards",
            "hero_cards": ["Ah", "Kd"],
            "ts": 1.0,
        },
    )

    state["hand_token"] = "ownership-test"

    positions = {
        "btn": "BTN",
        "sb": "SB",
        "hero": "BB",
    }

    state = sm.handle_table_context(
        state,
        {
            "type": "table_context",
            "hand_token": state["hand_token"],
            "dealer_button_seat": "btn",
            "hero_position": "BB",
            "dealt_in_seats": [
                "btn",
                "sb",
                "hero",
            ],
            "positions": positions,
            "players": [
                {"seat": "btn"},
                {"seat": "sb"},
                {"seat": "hero"},
            ],
            "ts": 1.1,
        },
    )

    canonical = sm.CANONICAL_STORE.load()
    tracker = sm.tracker_for_hand(canonical)

    # This test isolates quantitative ownership from poker-response
    # obligations. Complete the ordinary PREFLOP action queue through
    # the tracker API rather than manufacturing an empty queue.
    #
    # The board barrier should therefore be tested with poker action
    # obligations genuinely complete while independent quantitative
    # ownership remains alive.
    tracker.commitment_tracker.reset_street(
        "PREFLOP"
    )
    tracker.commitment_tracker.initialize_street_order(
        "PREFLOP",
        [
            "btn",
            "sb",
            "hero",
        ],
    )
    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        [
            "btn",
            "sb",
            "hero",
        ],
    )

    for seat in (
        "btn",
        "sb",
        "hero",
    ):
        tracker.commitment_tracker.consume_pending_action(
            "PREFLOP",
            seat,
        )
        tracker.commitment_tracker.record_action(
            "PREFLOP",
            seat,
        )

    status = tracker.commitment_tracker.round_status(
        "PREFLOP"
    )

    print(
        "synthetic complete-round status:",
        status,
    )

    assert status["complete"] is True, status
    assert (
        status.get("players_owing_action")
        or []
    ) == [], status

    return state


def assert_board_waits(state):
    state = sm.handle_board(
        state,
        {
            "type": "board",
            "board": ["Jd", "9s", "Tc"],
            "ts": 2.0,
        },
    )

    canonical = sm.CANONICAL_STORE.load()

    assert state["phase"] == "PREFLOP"
    assert canonical.current_street == "PREFLOP"
    assert canonical.board == []
    assert len(
        state.get("pending_board_events")
        or []
    ) == 1

    return state


def main():
    old_store = sm.CANONICAL_STORE

    try:
        # --------------------------------------------------------
        # Validated transition awaiting canonical action blocks.
        # --------------------------------------------------------
        with TemporaryDirectory() as tmp:
            state = bootstrap(Path(tmp))

            state["unresolved_stack_candidates"] = {
                "PREFLOP:btn": {
                    "seat": "btn",
                    "street": "PREFLOP",
                    "sources": ["stack_motion"],
                    "awaiting_action": True,
                }
            }

            state = assert_board_waits(state)

            state["unresolved_stack_candidates"] = {}

            state = sm.release_pending_board_if_ready(
                state
            )

            canonical = sm.CANONICAL_STORE.load()

            assert state["phase"] == "FLOP"
            assert canonical.current_street == "FLOP"

            print(
                "PASS: awaiting_action blocks board promotion"
            )

        # --------------------------------------------------------
        # Provisional quantitative bet ownership blocks.
        # --------------------------------------------------------
        with TemporaryDirectory() as tmp:
            state = bootstrap(Path(tmp))

            state["unresolved_provisional_bets"] = {
                "PREFLOP:hero": {
                    "seat": "hero",
                    "street": "PREFLOP",
                    "bet_bb": 2.0,
                }
            }

            state = assert_board_waits(state)

            state["unresolved_provisional_bets"] = {}

            state = sm.release_pending_board_if_ready(
                state
            )

            canonical = sm.CANONICAL_STORE.load()

            assert state["phase"] == "FLOP"
            assert canonical.current_street == "FLOP"

            print(
                "PASS: provisional bet blocks board promotion"
            )

        # --------------------------------------------------------
        # Independent physical commitment evidence DOES block
        # before OCR/action classification finishes.
        # --------------------------------------------------------
        with TemporaryDirectory() as tmp:
            state = bootstrap(Path(tmp))

            state["unresolved_stack_candidates"] = {
                "PREFLOP:btn": {
                    "seat": "btn",
                    "street": "PREFLOP",
                    "sources": [
                        "stack_motion",
                        "bet_region_appeared",
                    ],
                }
            }

            state = assert_board_waits(state)

            ownership = sm.unresolved_board_ownership(
                state,
                "PREFLOP",
            )

            assert ownership[
                "commitment_candidates"
            ] == ["btn"], ownership

            state["unresolved_stack_candidates"] = {}

            state = sm.release_pending_board_if_ready(
                state
            )

            canonical = sm.CANONICAL_STORE.load()

            assert state["phase"] == "FLOP"
            assert canonical.current_street == "FLOP"

            print(
                "PASS: physical commitment candidate "
                "blocks board promotion until candidate closes"
            )

        # --------------------------------------------------------
        # Raw stack_motion alone does NOT globally block.
        # --------------------------------------------------------
        with TemporaryDirectory() as tmp:
            state = bootstrap(Path(tmp))

            state["unresolved_stack_candidates"] = {
                "PREFLOP:btn": {
                    "seat": "btn",
                    "street": "PREFLOP",
                    "sources": ["stack_motion"],
                }
            }

            state = sm.handle_board(
                state,
                {
                    "type": "board",
                    "board": ["Jd", "9s", "Tc"],
                    "ts": 2.0,
                },
            )

            canonical = sm.CANONICAL_STORE.load()

            assert state["phase"] == "FLOP"
            assert canonical.current_street == "FLOP"

            print(
                "PASS: raw stack_motion alone does not "
                "indefinitely block board promotion"
            )

    finally:
        sm.CANONICAL_STORE = old_store


if __name__ == "__main__":
    main()
