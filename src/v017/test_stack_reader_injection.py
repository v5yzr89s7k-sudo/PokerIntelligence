from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


def fake_reader(_crop):
    return {
        "stack_bb": 9.25,
        "stack_text": "9.25 BB",
        "confidence": 1.0,
        "votes": 1,
        "mode": "fake",
    }


def main():
    players = [
        {
            "seat": "hero",
            "position": "SB",
            "name": "Hero",
            "stack_bb": 10.0,
        },
        {
            "seat": "villain",
            "position": "BB",
            "name": "Villain",
            "stack_bb": 10.0,
        },
    ]

    observer = FrameHandObserver(
        players=players,
        action_order=[
            "hero",
            "villain",
        ],
        small_blind_seat="hero",
        big_blind_seat="villain",
        geometry={
            "stack_regions": {},
            "hole_cards": {},
            "hero_cards": {},
            "board": {},
        },
        trusted_stacks={
            "hero": 10.0,
            "villain": 10.0,
        },
        stack_reader=fake_reader,
    )

    assert (
        observer.stack_reader
        is fake_reader
    )

    print(
        "V0.17 STACK READER INJECTION: PASS"
    )


if __name__ == "__main__":
    main()
