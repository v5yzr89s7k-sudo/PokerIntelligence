def should_accept_action_observations(state):
    return not bool(
        state.get("terminal_action_frozen")
    )


def test_normal_river_accepts_action_evidence():
    state = {
        "phase": "RIVER",
        "terminal_action_frozen": False,
    }

    assert should_accept_action_observations(
        state
    )

    print(
        "PASS normal river: "
        "action observations remain enabled"
    )


def test_winner_boundary_freezes_old_hand():
    state = {
        "phase": "RIVER",
        "terminal_action_frozen": True,
        "terminal_freeze_reason": "winner_detected",
        "winner_seat": "seat_lower_right",
    }

    assert not should_accept_action_observations(
        state
    )

    print(
        "PASS winner boundary: "
        "old hand rejects new action observations"
    )


def test_board_clear_fallback_freezes_old_hand():
    state = {
        "phase": "RIVER",
        "terminal_action_frozen": True,
        "terminal_freeze_reason": "river_board_clear",
        "winner_seat": None,
    }

    assert not should_accept_action_observations(
        state
    )

    print(
        "PASS board-clear fallback: "
        "old hand rejects new action observations"
    )


def test_terminal_pot_wait_does_not_unfreeze_actions():
    state = {
        "phase": "RIVER",
        "terminal_action_frozen": True,
        "terminal_pot_pending": True,
    }

    assert not should_accept_action_observations(
        state
    )

    print(
        "PASS terminal pot wait: "
        "bookkeeping cannot reopen action ownership"
    )


def main():
    test_normal_river_accepts_action_evidence()
    test_winner_boundary_freezes_old_hand()
    test_board_clear_fallback_freezes_old_hand()
    test_terminal_pot_wait_does_not_unfreeze_actions()

    print()
    print(
        "PASS terminal action-freeze contract"
    )


if __name__ == "__main__":
    main()
