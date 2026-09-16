from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "first",
        "position": "BTN",
        "name": "First",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
]


def build():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "first",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
        },
        hero_seat="hero",
    )


def main():
    observer = build()

    assert observer.next_actor == "first"
    assert len(observer.hand.actions) == 2

    # --------------------------------------------------------
    # Out-of-order physical evidence is NOT semantic authority.
    # --------------------------------------------------------

    action = (
        observer
        .admit_card_disappearance(
            "bb",
            frame_id=10,
        )
    )

    assert action is None
    assert observer.next_actor == "first"
    assert len(observer.hand.actions) == 2
    assert observer.events == []

    # --------------------------------------------------------
    # Authoritative actor disappearance becomes exactly one fold.
    # --------------------------------------------------------

    action = (
        observer
        .admit_card_disappearance(
            "first",
            frame_id=11,
        )
    )

    assert action == "FOLD"
    assert observer.next_actor == "hero"
    assert len(observer.hand.actions) == 3

    semantic = (
        observer.hand
        .semantic_actions()
    )

    assert semantic[-1]["seat"] == "first"
    assert semantic[-1]["action"] == "FOLD"

    assert len(observer.events) == 1
    assert (
        observer.events[0]["frame"]
        == 11
    )
    assert (
        observer.events[0]["seat"]
        == "first"
    )
    assert (
        observer.events[0][
            "semantic_action"
        ]
        == "FOLD"
    )

    # --------------------------------------------------------
    # Duplicate/stale disappearance cannot mutate again because
    # First is no longer authoritative.
    # --------------------------------------------------------

    action = (
        observer
        .admit_card_disappearance(
            "first",
            frame_id=12,
        )
    )

    assert action is None
    assert len(observer.hand.actions) == 3
    assert len(observer.events) == 1

    # --------------------------------------------------------
    # Hero disappearance is admitted only when Hero is pending.
    # --------------------------------------------------------

    action = (
        observer
        .admit_card_disappearance(
            "hero",
            frame_id=13,
            physical_type=(
                "HERO_CARDS_DISAPPEARED_PHYSICAL"
            ),
        )
    )

    assert action == "FOLD"
    assert observer.next_actor == "bb"
    assert len(observer.hand.actions) == 4

    assert (
        observer.events[-1][
            "physical_type"
        ]
        == "HERO_CARDS_DISAPPEARED_PHYSICAL"
    )

    print(
        "V0.17 FRAMEHANDOBSERVER CARD ADMISSION: PASS"
    )


if __name__ == "__main__":
    main()
