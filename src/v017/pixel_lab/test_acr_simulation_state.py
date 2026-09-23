from pathlib import Path

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)
from src.v017.pixel_lab.acr_simulation_state import (
    compile_simulation_states,
)


ROOT = Path(__file__).resolve().parents[3]
HAND_ID = "2826906889"


def main():
    hand = next(
        hand
        for _, hand in parse_corpus(
            ROOT
            / "runtime/pixel_lab/"
              "acr_hand_histories"
        )
        if hand.hand_id == HAND_ID
    )

    states = compile_simulation_states(
        hand
    )

    print(
        "===== PRIVATE SIMULATION STATE ====="
    )
    print(
        "hand =",
        hand.hand_id,
    )
    print(
        "big_blind =",
        hand.big_blind,
    )
    print(
        "states =",
        len(states),
    )

    first = states[0]

    print()
    print("===== STARTING TABLE =====")
    print(
        "button_seat =",
        first.button_seat,
    )
    print(
        "sb_seat =",
        first.small_blind_seat,
    )
    print(
        "bb_seat =",
        first.big_blind_seat,
    )
    print(
        "hero_cards =",
        first.hero_cards,
    )

    for player in first.players:
        print(
            f"seat={player.seat_number}",
            f"{player.name:16s}",
            f"chips={player.stack_chips:8.2f}",
            f"bb={player.stack_bb:7.2f}",
        )

    expected = {
        "MESE": 111.06,
        "SchlomoSmack": 25.46,
        "The_Stranger": 103.72,
        "sandman888": 58.25,
        "Blu3Falc0n": 71.67,
        "FERITIN": 118.11,
        "Dayzdnconfused": 75.92,
        "poker5068": 56.52,
    }

    observed = {
        player.name: player.stack_bb
        for player in first.players
    }

    assert observed == expected, (
        observed,
        expected,
    )

    assert first.button_seat == 4
    assert first.small_blind_seat == 5
    assert first.big_blind_seat == 6
    assert first.hero_cards == (
        "5s",
        "Kc",
    )

    print()
    print("===== STATE PROGRESSION =====")

    for state in states:
        print(
            f"{state.sequence:02d}",
            f"{state.phase:8s}",
            f"{str(state.cause_actor):16s}",
            f"{state.cause_action:18s}",
            f"pot={state.pot_chips:8.2f}",
            f"pot_bb={state.pot_bb:6.2f}",
            f"board={' '.join(state.board) or '-'}",
            (
                f"winner={state.winner}"
                if state.winner
                else ""
            ),
        )

    final = states[-1]

    assert final.board == (
        "8s",
        "7h",
        "7s",
        "Ah",
        "Kh",
    )

    assert final.winner == "The_Stranger"

    assert round(
        float(hand.total_pot),
        2,
    ) == 38400.00

    assert round(
        float(final.pot_chips),
        2,
    ) == 38400.00, (
        final.pot_chips,
        hand.total_pot,
    )

    print()
    print(
        "ACR HISTORY → SIMULATION STATE: PASS"
    )
    print(
        "FINAL POT:",
        final.pot_chips,
        "chips /",
        final.pot_bb,
        "BB",
    )
    print(
        "WINNER:",
        final.winner,
    )


if __name__ == "__main__":
    main()
