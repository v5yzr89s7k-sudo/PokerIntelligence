from pathlib import Path

import numpy as np

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    FrameObservationResult,
)
import src.v017.run_live_observer as live


def main():
    players = [
        {
            "seat": "hero",
            "position": "HJ",
            "name": "Hero",
            "stack_bb": 20.0,
            "dealt_in": True,
            "is_hero": True,
        },
        {
            "seat": "sb",
            "position": "SB",
            "name": "SB",
            "stack_bb": 50.0,
            "dealt_in": True,
        },
        {
            "seat": "villain",
            "position": "BB",
            "name": "Villain",
            "stack_bb": 50.0,
            "dealt_in": True,
        },
    ]

    observer = FrameHandObserver(
        players=players,
        action_order=["hero", "sb", "villain"],
        small_blind_seat="sb",
        big_blind_seat="villain",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 20.0,
            "sb": 49.5,
            "villain": 49.0,
        },
        opponent_seats=["sb", "villain"],
        quantitative_seats=["hero"],
        hero_seat="hero",
        hand_id="hero-zero-completion",
    )

    observer.quantitative_retry_pending["hero"] = {
        "attempts": 0,
        "first_frame": 10,
        "last_frame": 10,
        "commitment_seen": False,
        "reason": "hero_action_completion",
    }

    state = live.FrameTransactionState()

    original = observer.process_frame
    calls = {"count": 0}

    def fake_process_frame(
        image,
        frame_id=None,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        calls["count"] += 1

        return FrameObservationResult(
            frame_id=frame_id,
            events=(
                {
                    "frame": frame_id,
                    "type": "STACK_QUANTITATIVE_OBSERVATION",
                    "seat": "hero",
                    "prior": 20.0,
                    "reader_value": 0.0,
                    "resolved": True,
                    "resolved_value": 0.0,
                    "candidates": ((0.0, 1),),
                    "confidence": 0.9,
                    "votes": 1,
                    "mode": "native_green_fast",
                    "physical_delta_bb": 20.0,
                },
            ),
            changed=False,
            text=None,
        )

    observer.process_frame = fake_process_frame

    try:
        image = np.zeros(
            (696, 934, 3),
            dtype=np.uint8,
        )

        live.process_frame_transaction(
            observer,
            image,
            Path("/tmp/hero_zero_completion.png"),
            10,
            state,
        )

        live.process_frame_transaction(
            observer,
            image,
            Path("/tmp/hero_zero_completion.png"),
            11,
            state,
        )

        hero = observer.hand.players["hero"]

        assert hero.all_in is True, (
            "RED: confirmed Hero zero stack after physical "
            "Hero action completion was not admitted as all-in"
        )

        assert observer.trusted_stacks["hero"] == 0.0

        hero_actions = [
            row
            for row in observer.hand.semantic_actions()
            if (
                row["seat"] == "hero"
                and row["action"]
                not in {
                    "POST_SMALL_BLIND",
                    "POST_BIG_BLIND",
                }
            )
        ]

        assert hero_actions, hero_actions

        print(
            "HERO ACTION COMPLETION + CONFIRMED ZERO STACK "
            "-> ALL-IN: PASS"
        )

    finally:
        state.board_identity_reader.close()
        observer.process_frame = original


if __name__ == "__main__":
    main()
