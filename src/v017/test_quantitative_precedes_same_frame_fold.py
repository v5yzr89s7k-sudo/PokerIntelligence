"""
V0.17 same-frame quantitative chronology before fold authority.

One physical frame may contain:

    current actor's cards disappear
    later actor's stack decreases

At zero price, later-seat quantitative evidence proves that every
zero-price predecessor completed action before that later actor could
act.

Therefore:

    BB no commitment -> CHECK
    Hero commitment  -> BET
    retained BB card disappearance -> FOLD

Raw physical event-list order must not determine semantic chronology.
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
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]


def quantitative(
    frame,
    seat,
    value,
):
    return {
        "frame": frame,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "resolved": True,
        "resolved_value": value,
    }


def main():
    # Preflop order is Hero -> BB.
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=["bb"],
        quantitative_seats=[
            "hero",
            "bb",
        ],
        hero_seat="hero",
        hand_id=(
            "same-frame-check-bet-fold"
        ),
    )

    # HandEngine constructor has already posted:
    #
    #   Hero SB = 0.5
    #   BB      = 1.0
    #
    # Hero completes to the 1 BB price; BB is already there and
    # completes without additional commitment. This closes preflop
    # through ordinary HandEngine authority.
    assert observer.hand.next_actor == "hero"

    assert (
        observer.hand.observe_stack_commitment(
            "hero",
            0.5,
        )
        == "CALL"
    )

    assert observer.hand.next_actor == "bb"

    assert (
        observer.hand.observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )

    assert observer.hand.next_actor is None

    # Begin a clean heads-up flop with BB first.
    observer.hand.start_street(
        "FLOP",
        [
            "bb",
            "hero",
        ],
        board=[
            "Jd",
            "9s",
            "Tc",
        ],
    )

    assert observer.hand.street == "FLOP"
    assert observer.hand.next_actor == "bb"
    assert observer.hand.current_price_bb == 0.0

    # Align trusted quantitative state with the post-blind/preflop
    # physical state for this isolated flop test.
    observer.trusted_stacks[
        "hero"
    ] = 49.0

    observer.trusted_stacks[
        "bb"
    ] = 49.0

    # ------------------------------------------------------------
    # SAME PHYSICAL FRAME
    # ------------------------------------------------------------
    #
    # Raw detector ordering exposes BB card disappearance first.
    #
    # Do not grant FOLD authority yet. Preserve the objective evidence
    # with its original physical frame identity.
    observer._retain_pending_card_disappearance(
        "bb",
        frame_id=19,
        physical_type=(
            "OPPONENT_CARDS_DISAPPEARED"
        ),
    )

    assert observer.hand.next_actor == "bb"

    assert (
        len(
            observer.pending_card_disappearances
        )
        == 1
    )

    # Hero's stack then proves a 2.12 BB commitment in the same
    # physical frame.
    #
    # Since Hero is later in the flop action order and BB is still a
    # zero-price predecessor, generic chronology completion must first:
    #
    #   BB -> CHECK
    #
    # then admit:
    #
    #   Hero -> BET 2.12
    #
    # Quantitative catch-up must finally reconcile the retained BB
    # disappearance:
    #
    #   BB -> FOLD
    emitted = (
        observer
        .admit_quantitative_observation(
            quantitative(
                19,
                "hero",
                46.88,
            )
        )
    )

    assert emitted

    actions = [
        row
        for row
        in observer.hand.semantic_actions()
        if row["street"] == "FLOP"
    ]

    observed = [
        (
            row["seat"],
            row["action"],
            row["amount_bb"],
            row["raise_to_bb"],
        )
        for row in actions
    ]

    print(
        "observed flop actions =",
        observed,
    )

    assert observed == [
        (
            "bb",
            "CHECK",
            None,
            None,
        ),
        (
            "hero",
            "BET",
            2.12,
            None,
        ),
        (
            "bb",
            "FOLD",
            None,
            None,
        ),
    ], observed

    assert (
        observer.pending_card_disappearances
        == []
    )

    assert observer.hand.hand_complete

    assert observer.hand.winner_seats == [
        "hero"
    ]

    chronology = [
        event
        for event in observer.events
        if (
            event.get("type")
            == "CHRONOLOGY_COMPLETION"
        )
    ]

    assert len(chronology) == 1, chronology

    assert chronology[0]["seat"] == "bb"

    assert (
        chronology[0]["proved_by"]
        == "hero"
    )

    assert (
        chronology[0][
            "semantic_action"
        ]
        == "CHECK"
    )

    reconciled_fold = [
        event
        for event in observer.events
        if (
            event.get("type")
            == "CARD_DISAPPEARANCE_ADMITTED"
            and event.get("seat")
            == "bb"
        )
    ]

    assert len(reconciled_fold) == 1

    # Physical evidence retains its original frame identity.
    assert (
        reconciled_fold[0]["frame"]
        == 19
    )

    print()
    print(
        "ZERO-PRICE PREDECESSOR -> CHECK: PASS"
    )
    print(
        "LATER QUANTITATIVE -> BET: PASS"
    )
    print(
        "RETAINED SAME-FRAME CARDS -> FOLD: PASS"
    )
    print(
        "CHECK -> BET -> FOLD ORDER: PASS"
    )
    print(
        "RETAINED FRAME IDENTITY: PASS"
    )
    print(
        "EVENT-LIST ORDER OWNS SEMANTICS: NO"
    )
    print()
    print(
        "V0.17 SAME-FRAME CHECK BET FOLD: PASS"
    )


if __name__ == "__main__":
    main()
