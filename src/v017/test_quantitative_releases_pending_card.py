"""
V0.17 quantitative -> retained-card reconciliation regression.

A later actor's physical card disappearance may arrive in the same
physical frame that confirms the current actor's quantitative action.

The disappearance must remain physical until chronology reaches that
seat, then become authoritative automatically without another frame.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "CO",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "btn",
        "position": "BTN",
        "name": "BTN",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]


def quantitative(frame, seat, value):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "resolved": True,
        "resolved_value": value,
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "btn",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 50.0,
            "btn": 50.0,
            "sb": 50.0,
            "bb": 50.0,
        },
        opponent_seats=[
            "btn",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "hero",
            "btn",
            "sb",
            "bb",
        ],
        hero_seat="hero",
        hand_id=(
            "quantitative-releases-pending-card"
        ),
    )

    assert observer.hand.next_actor == "hero"

    # BTN's cards disappear while Hero is still authoritative.
    result = observer.admit_card_disappearance(
        "btn",
        frame_id=13,
        physical_type=(
            "OPPONENT_CARDS_DISAPPEARED"
        ),
    )

    assert result is None
    assert observer.hand.next_actor == "hero"
    assert len(
        observer.pending_card_disappearances
    ) == 1

    # Hero's quantitative action settles in that same physical frame.
    #
    # Successful admission advances chronology to BTN. The already
    # retained BTN disappearance must then consume automatically.
    emitted = observer.admit_quantitative_observation(
        quantitative(
            13,
            "hero",
            47.4,
        )
    )

    assert emitted

    assert (
        observer.pending_card_disappearances
        == []
    ), observer.pending_card_disappearances

    actions = [
        row
        for row
        in observer.hand.semantic_actions()
        if row["action"] not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    observed = [
        (
            row["seat"],
            row["action"],
            row["raise_to_bb"],
        )
        for row in actions
    ]

    assert observed == [
        (
            "hero",
            "RAISE",
            2.6,
        ),
        (
            "btn",
            "FOLD",
            None,
        ),
    ], observed

    assert observer.hand.next_actor == "sb"

    admitted_btn = [
        event
        for event in observer.events
        if (
            event.get("type")
            == "CARD_DISAPPEARANCE_ADMITTED"
            and event.get("seat") == "btn"
        )
    ]

    assert len(admitted_btn) == 1
    assert admitted_btn[0]["frame"] == 13

    # Atomic publication: no externally visible intermediate product
    # may stop after Hero's raise while BTN's fold was already known.
    assert len(observer.publications) == 1, (
        observer.publications
    )

    publication = observer.publications[0]

    assert publication["next_actor"] == "sb"

    text = publication["text"]

    # Presentation wording is not the semantic contract here.
    # The authoritative assertions above already prove exact action,
    # sizing, frontier advancement, retained frame identity, and one
    # atomic publication. Keep only the stable fold projection check.
    assert "BTN folds" in text

    print()
    print(
        "QUANTITATIVE -> RETAINED CARD: PASS"
    )
    print(
        "SAME-FRAME FRONTIER RELEASE: PASS"
    )
    print(
        "RETAINED FRAME IDENTITY: PASS"
    )
    print(
        "ATOMIC PUBLICATION: PASS"
    )
    print()
    print(
        "V0.17 QUANTITATIVE CARD CATCH-UP: PASS"
    )


if __name__ == "__main__":
    main()
