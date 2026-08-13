from unittest.mock import patch

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def make_hand():
    players = [
        {
            "seat": "hero",
            "name": "poker5068",
            "stack_bb": 83.20,
            "is_hero": True,
            "is_active": True,
        },
        {
            "seat": "seat_lower_right",
            "name": "warreneen",
            "stack_bb": 75.08,
            "is_hero": False,
            "is_active": True,
        },
    ]

    return CanonicalHand().start_hand(
        hand_id="terminal-result-test",
        players=players,
        hero_cards=["8s", "4h"],
        hero_position="UTG+1",
        positions={
            "hero": "UTG+1",
            "seat_lower_right": "UTG",
        },
        started_ts=1.0,
    )


def test_winner_event_preserves_seat():
    state = sm.default_state()
    state["phase"] = "RIVER"
    state["canonical_snapshot_ready"] = True

    state = sm.handle_winner_detected(
        state,
        {
            "type": "winner_detected",
            "seat": "seat_lower_right",
            "confidence": 0.98,
            "ts": 10.0,
        },
    )

    assert (
        state["winner_seat"]
        == "seat_lower_right"
    )

    print(
        "PASS winner state: canonical seat preserved "
        "at terminal boundary"
    )


def test_terminal_pot_bypasses_ordinary_high_pot_hold():
    state = sm.default_state()
    state["phase"] = "RIVER"
    state["canonical_snapshot_ready"] = True
    state["pending_high_pot"] = None

    hand = make_hand()
    hand.expected_pot_bb = 7.0
    hand.pot_bb = 7.0

    saved = []

    with (
        patch.object(
            sm,
            "canonical_load",
            return_value=hand,
        ),
        patch.object(
            sm,
            "canonical_save",
            side_effect=lambda value: saved.append(value),
        ),
    ):
        state = sm.handle_pot_update(
            state,
            {
                "type": "pot_update",
                "pot_bb": 117.33,
                "terminal": True,
                "ts": 20.0,
            },
        )

    assert saved
    assert round(hand.pot_bb, 2) == 117.33
    assert state["final_pot_bb"] == 117.33
    assert state["pending_high_pot"] is None

    print(
        "PASS terminal pot: authoritative final pot "
        "117.33 bypasses ordinary high-pot confirmation"
    )


def test_hand_complete_promotes_structured_result():
    state = sm.default_state()
    state["phase"] = "RIVER"
    state["canonical_snapshot_ready"] = True
    state["winner_seat"] = "seat_lower_right"
    state["final_pot_bb"] = 117.33

    hand = make_hand()

    archived_hand = []

    with (
        patch.object(
            sm,
            "canonical_load",
            return_value=hand,
        ),
        patch.object(
            sm,
            "canonical_save",
            side_effect=lambda value: archived_hand.append(value),
        ),
        patch.object(
            sm.CANONICAL_STORE,
            "archive",
            return_value="test-archive",
        ),
        patch.object(
            sm,
            "write_validation_summary",
        ),
        patch.object(
            sm,
            "reset_tracker",
        ),
    ):
        sm.handle_hand_complete(
            state,
            {
                "type": "hand_complete",
                "result": "Board cleared after river",
                "ts": 30.0,
            },
        )

    assert len(hand.pots) == 1, hand.pots

    pot = hand.pots[0]

    assert pot["pot_type"] == "final_pot"
    assert pot["amount_bb"] == 117.33
    assert pot["winners"] == [
        "seat_lower_right"
    ]

    assert hand.closed is True

    print(
        "PASS completed result: winner seat and final pot "
        "promoted before canonical archive"
    )


def main():
    test_winner_event_preserves_seat()
    test_terminal_pot_bypasses_ordinary_high_pot_hold()
    test_hand_complete_promotes_structured_result()

    print()
    print(
        "PASS terminal winner/pot contract"
    )


if __name__ == "__main__":
    main()
