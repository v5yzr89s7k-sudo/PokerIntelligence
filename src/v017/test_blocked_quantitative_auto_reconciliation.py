"""
V0.17 automatic blocked quantitative reconciliation contract.

A resolved physical stack observation belonging to a later actor must not
mutate semantic chronology while an earlier actor is unresolved and facing
a price.

But that physical evidence must survive the temporary chronology block.
Once the predecessor resolves, the retained observation must become
semantically consumable exactly once.

This test is intentionally written against the required architecture.
It should FAIL before retention/reconciliation is implemented.
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


def main():
    observer = FrameHandObserver(
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
        hand_id="blocked-retention-contract",
    )

    assert observer.hand.next_actor == "utg"
    assert observer.hand.current_price_bb == 1.0

    before_actions = list(
        observer.hand.semantic_actions()
    )
    before_hj_stack = observer.trusted_stacks["hero"]

    # --------------------------------------------------------
    # HJ physically commits 2 BB while UTG is still unresolved.
    #
    # This may NOT skip UTG or mutate HandEngine yet.
    # But the physical observation must survive.
    # --------------------------------------------------------

    blocked = observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    assert blocked == ()
    assert observer.hand.next_actor == "utg"
    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    # Semantic quantitative authority must not move merely
    # because evidence was deferred.
    assert (
        observer.trusted_stacks["hero"]
        == before_hj_stack
    )

    # --------------------------------------------------------
    # UTG now objectively folds.
    # This advances the authoritative chronology frontier to HJ.
    # --------------------------------------------------------

    result = observer.admit_card_disappearance(
        "utg",
        frame_id=11,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert result

    # UTG's fold releases the chronology frontier. Production now
    # automatically consumes the already-retained Hero/HJ physical
    # evidence in the same semantic catch-up transaction, so the
    # authoritative next actor has already advanced to SB.
    assert observer.hand.next_actor == "sb"

    # --------------------------------------------------------
    # REQUIRED PRODUCTION CONTRACT:
    #
    # Chronology advanced when UTG folded. Retained HJ/Hero
    # physical evidence must therefore reconcile automatically.
    # No caller may need to invoke reconcile_pending_evidence().
    # --------------------------------------------------------

    assert (
        observer.pending_quantitative_evidence
        == []
    ), (
        "MISSING AUTOMATIC RECONCILIATION: "
        f"{observer.pending_quantitative_evidence}"
    )

    admitted = [
        event
        for event in observer.events
        if event.get("type")
        == "QUANTITATIVE_ADMITTED"
        and event.get("seat") == "hero"
    ]

    assert len(admitted) == 1, admitted

    event = admitted[0]

    assert event["frame"] == 10
    assert event["resolved_value"] == 48.0
    assert event["physical_delta_bb"] == 2.0
    assert event["semantic_action"] == "RAISE"

    assert observer.trusted_stacks["hero"] == 48.0
    assert observer.hand.current_price_bb == 2.0
    assert observer.hand.next_actor == "sb"

    # UTG fold + already-known HJ/Hero raise must be published as
    # one caught-up authoritative state. No transient publication
    # may expose only the fold while withholding retained evidence.
    assert len(observer.publications) == 1, (
        observer.publications
    )

    publication = observer.publications[0]

    assert publication["action_count"] == 4, publication
    assert publication["next_actor"] == "sb", publication

    text = publication["text"]

    assert "UTG folds" in text, text
    assert "HJ raises to 2 BB" in text, text

    actions = [
        row
        for row in observer.hand.semantic_actions()
        if row["action"] not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    assert [
        (
            row["seat"],
            row["action"],
            row["raise_to_bb"],
        )
        for row in actions
    ] == [
        ("utg", "FOLD", None),
        ("hero", "RAISE", 2.0),
    ]

    # --------------------------------------------------------
    # Exactly-once ownership.
    # Reconciliation cannot replay HJ a second time.
    # --------------------------------------------------------

    action_count = len(observer.hand.actions)
    stack_after = observer.trusted_stacks["hero"]

    assert (
        observer.pending_quantitative_evidence
        == []
    )

    assert len(observer.hand.actions) == action_count
    assert observer.trusted_stacks["hero"] == stack_after

    print()
    print(
        "V0.17 BLOCKED QUANTITATIVE "
        "EVIDENCE RETENTION: PASS"
    )


if __name__ == "__main__":
    main()
