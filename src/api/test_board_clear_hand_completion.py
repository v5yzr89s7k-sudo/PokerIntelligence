from src.api.api_event_coordinator import (
    fresh_state,
    maybe_complete_early,
    maybe_complete_hand,
)


def run_non_river_clear_test(phase):
    state = fresh_state()
    state["phase"] = phase

    for expected in range(1, 4):
        state = maybe_complete_early(state, 0, True)
        assert state["board_clear_seen"] == expected, (
            phase,
            "after maybe_complete_early",
            expected,
            state["board_clear_seen"],
        )

        state = maybe_complete_hand(state, 0)
        assert state["phase"] == phase
        assert state["board_clear_seen"] == expected, (
            phase,
            "maybe_complete_hand destroyed counter",
            expected,
            state["board_clear_seen"],
        )

    # Fourth clear observation must terminate and return fresh coordinator state.
    state = maybe_complete_early(state, 0, True)

    assert state["phase"] == "WAITING", (phase, state)
    assert state["board_clear_seen"] == 0, (phase, state)

    print(f"PASS {phase}: four board-clear observations reset hand to WAITING")


def main():
    run_non_river_clear_test("FLOP")
    run_non_river_clear_test("TURN")
    print("PASS board-clear hand completion regression")


if __name__ == "__main__":
    main()
