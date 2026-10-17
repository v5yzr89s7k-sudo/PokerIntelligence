from src.v017.frame_hand_observer import FrameHandObserver
from src.v017.run_live_observer import reconcile_frame_evidence


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
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
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
        hand_id="post-boundary-new-street-action",
    )

    # Physical flop exists, but PREFLOP chronology has not caught up.
    boundary = {
        "frame": 13,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
    }

    result = observer.admit_street_boundary(
        boundary,
        action_order=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        board=[
            "As",
            "Kd",
            "7c",
        ],
        complete_pending=False,
    )

    assert result == ()
    assert observer.hand.street == "PREFLOP"
    assert observer.pending_street_boundaries

    # This stack decrease happens physically AFTER the flop appeared.
    # It therefore belongs to FLOP, not PREFLOP.
    admitted = observer.admit_quantitative_observation(
        quantitative(
            20,
            "utg",
            48.0,
        )
    )

    assert admitted == ()

    retained = [
        row
        for row in observer.pending_quantitative_evidence
        if (
            row.get("frame") == 20
            and row.get("seat") == "utg"
        )
    ]

    assert len(retained) == 1

    # Give the already-proven boundary authority to close unresolved
    # prior-street ownership WITHOUT inventing poker actions.
    observer.pending_street_boundaries[0][
        "complete_pending"
    ] = True

    before_actions = len(
        observer.hand.semantic_actions()
    )

    reconcile_frame_evidence(observer)

    assert observer.hand.street == "FLOP"

    # The post-boundary evidence must have been consumed now.
    assert not [
        row
        for row in observer.pending_quantitative_evidence
        if (
            row.get("frame") == 20
            and row.get("seat") == "utg"
        )
    ]

    admitted_events = [
        event
        for event in observer.events
        if (
            event.get("type")
            == "QUANTITATIVE_ADMITTED"
            and event.get("frame") == 20
            and event.get("seat") == "utg"
        )
    ]

    assert len(admitted_events) == 1, admitted_events

    event = admitted_events[0]

    assert event["physical_delta_bb"] == 2.0
    assert event["semantic_action"] == "BET"

    actions = observer.hand.semantic_actions()

    new_actions = actions[before_actions:]

    assert len(new_actions) == 2, new_actions

    preflop_action = new_actions[0]
    assert preflop_action["street"] == "PREFLOP"
    assert preflop_action["seat"] == "bb"
    assert preflop_action["action"] == "CHECK"

    action = new_actions[1]

    assert action["street"] == "FLOP"
    assert action["seat"] == "utg"
    assert action["action"] == "BET"
    assert action["amount_bb"] == 2.0

    # No missing PREFLOP actor may have been fabricated into a
    # CHECK/FOLD/CALL merely to release chronology.
    fabricated = [
        row
        for row in actions
        if (
            row["street"] == "PREFLOP"
            and row["action"] not in {
                "POST_SMALL_BLIND",
                "POST_BIG_BLIND",
            }
        )
    ]

    assert fabricated == [
        {
            "sequence": 3,
            "street": "PREFLOP",
            "seat": "bb",
            "position": "BB",
            "name": "BB",
            "action": "CHECK",
            "amount_bb": None,
            "raise_to_bb": None,
        }
    ], fabricated

    print(
        "POST-BOUNDARY QUANTITATIVE -> NEW STREET ACTION: PASS"
    )


if __name__ == "__main__":
    main()
