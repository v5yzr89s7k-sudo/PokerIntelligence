"""
V0.17 pending card-disappearance ownership contract.

A physical card disappearance belonging to a later actor must not
skip the authoritative chronology frontier.

But the evidence must survive. Once preceding actors resolve and that
seat becomes authoritative, the retained disappearance must become
exactly one semantic fold without requiring another physical event.
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "utg",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "HJ",
        "name": "HJ",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 40.0,
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


def build():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "utg",
            "hero",
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
            "utg": 50.0,
            "hero": 50.0,
            "sb": 20.0,
            "bb": 40.0,
        },
        opponent_seats=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        hero_seat="hero",
        hand_id="pending-card-disappearance",
    )


def main():
    observer = build()

    assert observer.hand.next_actor == "utg"

    # --------------------------------------------------------
    # Hero/HJ physically raises while UTG remains unresolved.
    # Existing Phase A-C architecture retains this.
    # --------------------------------------------------------

    result = observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    assert result == ()
    assert observer.pending_quantitative_evidence

    # --------------------------------------------------------
    # SB physically folds BEFORE chronology reaches SB.
    #
    # It may not mutate HandEngine now, but it must survive.
    # --------------------------------------------------------

    before_actions = list(
        observer.hand.semantic_actions()
    )

    result = observer.admit_card_disappearance(
        "sb",
        frame_id=11,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert result is None
    assert observer.hand.next_actor == "utg"
    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    assert hasattr(
        observer,
        "pending_card_disappearances",
    ), (
        "MISSING ARCHITECTURE: out-of-order physical "
        "card disappearance has no retained ownership"
    )

    assert len(
        observer.pending_card_disappearances
    ) == 1

    pending = (
        observer.pending_card_disappearances[0]
    )

    assert pending["seat"] == "sb"
    assert pending["frame_id"] == 11
    assert (
        pending["physical_type"]
        == "OPPONENT_CARDS_DISAPPEARED"
    )

    # --------------------------------------------------------
    # UTG now physically folds.
    #
    # Existing automatic quantitative reconciliation consumes
    # Hero/HJ's retained raise. That makes SB authoritative.
    # The already-retained SB disappearance must then consume
    # automatically in the SAME catch-up transaction.
    # --------------------------------------------------------

    result = observer.admit_card_disappearance(
        "utg",
        frame_id=12,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert result == "FOLD"

    assert (
        observer.pending_quantitative_evidence
        == []
    )

    assert (
        observer.pending_card_disappearances
        == []
    ), (
        "MISSING AUTOMATIC CARD RECONCILIATION: "
        f"{observer.pending_card_disappearances}"
    )

    assert observer.hand.next_actor == "bb"

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
            "utg",
            "FOLD",
            None,
        ),
        (
            "hero",
            "RAISE",
            2.0,
        ),
        (
            "sb",
            "FOLD",
            None,
        ),
    ], observed

    # Retained physical frame identity survives semantic delay.
    admitted_sb = [
        event
        for event in observer.events
        if (
            event.get("type")
            == "CARD_DISAPPEARANCE_ADMITTED"
            and event.get("seat") == "sb"
        )
    ]

    assert len(admitted_sb) == 1, admitted_sb
    assert admitted_sb[0]["frame"] == 11

    # --------------------------------------------------------
    # Exactly once.
    # --------------------------------------------------------

    before_count = len(
        observer.hand.actions
    )

    observer.reconcile_pending_card_disappearances()

    assert len(
        observer.hand.actions
    ) == before_count

    assert (
        observer.pending_card_disappearances
        == []
    )

    # Atomic publication: no transient product may stop at UTG
    # or Hero when SB's physical fold was already known.
    assert len(observer.publications) == 1, (
        observer.publications
    )

    publication = observer.publications[0]

    assert publication["next_actor"] == "bb"
    assert publication["action_count"] == 5

    text = publication["text"]

    assert "UTG folds" in text
    assert "HJ raises to 2 BB" in text
    assert "SB folds" in text

    print()
    print(
        "V0.17 PENDING CARD DISAPPEARANCE "
        "RECONCILIATION: PASS"
    )


if __name__ == "__main__":
    main()
