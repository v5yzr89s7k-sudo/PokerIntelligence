from pathlib import Path
from tempfile import TemporaryDirectory
import json

import src.api.api_event_state_machine as sm
from src.state.canonical_hand_store import CanonicalHandStore


with TemporaryDirectory() as tmp:
    root = Path(tmp)

    sm.CANONICAL_STORE = CanonicalHandStore(
        json_path=root / "canonical_hand.json",
        text_path=root / "current_hand.txt",
    )

    state = {
        "phase": "WAITING",
        "players": [],
        "positions": {},
        "hero_position": "unknown",
        "board": [],
        "hero_cards": [],
        "hero_to_act": False,
        "hand_complete": False,
        "result": None,
        "forced_blinds_seeded": False,
        "canonical_snapshot_ready": False,
        "pending_board_events": [],
    }

    state = sm.handle_hero_cards(
        state,
        {
            "type": "hero_cards",
            "hero_cards": ["Ad", "Qh"],
            "ts": 100.0,
        },
    )

    state = sm.handle_board(
        state,
        {
            "type": "board",
            "board": ["9s", "As", "Jh"],
            "ts": 110.0,
        },
    )

    assert state["phase"] == "PREFLOP"
    assert state["board"] == []
    assert len(state["pending_board_events"]) == 1

    players = [
        {
            "seat": "seat_upper_right",
            "name": "Villain",
            "stack_bb": 100.0,
            "is_active": True,
        },
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 20.0,
            "is_hero": True,
            "is_active": True,
        },
        {
            "seat": "seat_lower_left",
            "name": "BigBlind",
            "stack_bb": 40.0,
            "is_active": True,
        },
    ]

    state = sm.handle_table_snapshot(
        state,
        {
            "type": "table_snapshot",
            "players": players,
            "dealer_button_seat": "seat_upper_right",
            "ts": 111.0,
        },
    )

    hand = sm.CANONICAL_STORE.load()

    assert state["canonical_snapshot_ready"] is True
    assert state["phase"] == "FLOP"
    assert state["board"] == ["9s", "As", "Jh"]

    blind_actions = [
        action
        for action in hand.actions
        if action.action in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    assert len(blind_actions) == 2
    assert all(
        action.street == "PREFLOP"
        for action in blind_actions
    )

    assert hand.current_street == "FLOP"
    assert hand.board == ["9s", "As", "Jh"]

    print("Late snapshot board buffering regression passed.")
