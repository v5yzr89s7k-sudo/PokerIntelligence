"""
Build complete controlled physical simulation for one ACR hand.

Generator side only.
"""

from pathlib import Path

import argparse
import json
import shutil

import cv2

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)
from src.v017.pixel_lab.acr_simulation_state import (
    compile_simulation_states,
)
from src.v017.pixel_lab.acr_simulator_frame import (
    render_simulation_state,
)


ROOT = Path(__file__).resolve().parents[3]

DEFAULT_HAND_ID = "2826906889"


def build_controlled_hand(
    hand_id=DEFAULT_HAND_ID,
):
    hand_id = str(hand_id)

    out = (
        ROOT
        / "runtime/pixel_lab/observer_input/"
          f"controlled_hand_{hand_id}"
    )

    hand = next(
        hand
        for _, hand in parse_corpus(
            ROOT
            / "runtime/pixel_lab/"
              "acr_hand_histories"
        )
        if hand.hand_id == hand_id
    )

    states = compile_simulation_states(
        hand
    )

    if out.exists():
        shutil.rmtree(
            out
        )

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = []

    print(
        "===== BUILD CONTROLLED HAND ====="
    )
    print(
        "hand =",
        hand_id,
    )
    print(
        "states =",
        len(states),
    )

    for state in states:
        image = render_simulation_state(
            hand=hand,
            state=state,
        )

        filename = (
            f"frame_{state.sequence:04d}.png"
        )

        path = out / filename

        assert cv2.imwrite(
            str(path),
            image,
        ), path

        manifest.append(
            {
                "sequence":
                    state.sequence,
                "filename":
                    filename,
                "phase":
                    state.phase,
                "cause_actor":
                    state.cause_actor,
                "cause_action":
                    state.cause_action,
                "pot_bb":
                    state.pot_bb,
                "board":
                    list(state.board),
            }
        )

        print(
            f"{state.sequence:02d}",
            f"{state.phase:8s}",
            f"{str(state.cause_actor):16s}",
            f"{state.cause_action:18s}",
            f"pot={state.pot_bb:6.2f} BB",
            f"board={' '.join(state.board) or '-'}",
        )

    # PRIVATE generator manifest.
    # Production observer must never read it.
    (
        out
        / "private_truth_manifest.json"
    ).write_text(
        json.dumps(
            {
                "hand_id":
                    hand_id,
                "frame_count":
                    len(states),
                "frames":
                    manifest,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print()
    print(
        "output =",
        out,
    )
    print(
        "png_count =",
        len(
            list(
                out.glob(
                    "frame_*.png"
                )
            )
        ),
    )

    return {
        "hand_id": hand_id,
        "output": out,
        "frame_count": len(states),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Build controlled Pixel Lab PNGs "
            "for one parsed ACR hand."
        )
    )

    parser.add_argument(
        "hand_id",
        nargs="?",
        default=DEFAULT_HAND_ID,
    )

    args = parser.parse_args()

    build_controlled_hand(
        args.hand_id
    )


if __name__ == "__main__":
    main()
