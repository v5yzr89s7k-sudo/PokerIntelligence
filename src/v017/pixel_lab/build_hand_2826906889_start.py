from pathlib import Path

import cv2

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)
from src.v017.pixel_lab.acr_simulation_state import (
    compile_simulation_states,
)
from src.v017.pixel_lab.acr_simulator_frame import (
    render_starting_table,
)


ROOT = Path(__file__).resolve().parents[3]
HAND_ID = "2826906889"

OUT = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "hand_2826906889_start.png"
)


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

    starting = states[0]

    assert (
        starting.cause_action
        == "STARTING_TABLE"
    )

    image = render_starting_table(
        hand=hand,
        state=starting,
    )

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    assert cv2.imwrite(
        str(OUT),
        image,
    )

    print(
        "===== HAND 2826906889 START ====="
    )

    for player in starting.players:
        print(
            player.seat_number,
            player.name,
            f"{player.stack_bb:.2f} BB",
        )

    print()
    print("button =", starting.button_seat)
    print(
        "hero_cards =",
        starting.hero_cards,
    )
    print("output =", OUT)


if __name__ == "__main__":
    main()
