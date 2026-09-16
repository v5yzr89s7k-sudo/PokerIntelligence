from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


def obs(frame, seat, prior, value):
    return {
        "frame": frame,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "prior": prior,
        "resolved": True,
        "resolved_value": value,
        "physical_delta_bb":
            round(prior - value, 2),
    }


def build():
    players = [
        {
            "seat": "btn",
            "position": "BTN",
            "name": "BTN",
            "stack_bb": 58.55,
            "dealt_in": True,
        },
        {
            "seat": "hero",
            "position": "SB",
            "name": "Hero",
            "stack_bb": 11.78,
            "dealt_in": True,
        },
        {
            "seat": "bb",
            "position": "BB",
            "name": "BB",
            "stack_bb": 48.57,
            "dealt_in": True,
        },
    ]

    return FrameHandObserver(
        players=players,
        action_order=[
            "btn",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
        },
        trusted_stacks={
            "btn": 58.55,
            "hero": 11.78,
            "bb": 48.57,
        },
        quantitative_seats=[
            "btn",
            "hero",
            "bb",
        ],
        hero_seat="hero",
    )


def main():
    observer = build()

    assert observer.next_actor == "btn"

    # False wake.
    emitted = (
        observer
        .admit_quantitative_observation(
            obs(
                40,
                "btn",
                58.55,
                58.55,
            )
        )
    )

    assert emitted == ()
    assert observer.next_actor == "btn"

    # BTN raise to 2 BB.
    emitted = (
        observer
        .admit_quantitative_observation(
            obs(
                42,
                "btn",
                58.55,
                56.55,
            )
        )
    )

    assert len(emitted) == 1
    assert (
        emitted[0]["semantic_action"]
        == "RAISE"
    )
    assert observer.trusted_stacks[
        "btn"
    ] == 56.55
    assert observer.next_actor == "hero"

    # Hero call 1.5 BB.
    emitted = (
        observer
        .admit_quantitative_observation(
            obs(
                48,
                "hero",
                11.78,
                10.28,
            )
        )
    )

    assert len(emitted) == 1
    assert (
        emitted[0]["semantic_action"]
        == "CALL"
    )
    assert (
        emitted[0][
            "normalized_delta_bb"
        ]
        == 1.5
    )
    assert observer.trusted_stacks[
        "hero"
    ] == 10.28

    # BB call 1 BB.
    emitted = (
        observer
        .admit_quantitative_observation(
            obs(
                51,
                "bb",
                48.57,
                47.57,
            )
        )
    )

    assert len(emitted) == 1
    assert (
        emitted[0]["semantic_action"]
        == "CALL"
    )
    assert (
        emitted[0][
            "normalized_delta_bb"
        ]
        == 1.0
    )
    assert observer.trusted_stacks[
        "bb"
    ] == 47.57

    assert observer.next_actor is None

    # Stale observation uses old physical prior but must be recomputed
    # against authoritative 10.28 and therefore rejected.
    before = len(
        observer.hand.actions
    )

    emitted = (
        observer
        .admit_quantitative_observation(
            obs(
                57,
                "hero",
                11.78,
                10.28,
            )
        )
    )

    assert emitted == ()
    assert len(
        observer.hand.actions
    ) == before
    assert observer.trusted_stacks[
        "hero"
    ] == 10.28

    assert [
        row["action"]
        for row
        in observer.hand.semantic_actions()
    ] == [
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
        "RAISE",
        "CALL",
        "CALL",
    ]

    print(
        "V0.17 FRAMEHANDOBSERVER QUANTITATIVE ADMISSION: PASS"
    )


if __name__ == "__main__":
    main()
