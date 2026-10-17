"""
Regression from live hand 2026-10-17.

A later actor's confirmed physical commitment may arrive while earlier
actors are unresolved. If retained for blocked predecessors, that
evidence must survive reconciliation of an earlier raise that changes
the betting price.

Ground truth shape:
    earlier actor unresolved
    raiser has confirmed 2 BB commitment
    hero has confirmed 1 BB additional commitment
    hero evidence is retained
    earlier actor folds
    raiser becomes authoritative and raises price to 2 BB
    hero retained evidence must remain available
    hero then becomes authoritative and the retained 1 BB becomes CALL
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "blocker",
        "position": "CO",
        "name": "Blocker",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "raiser",
        "position": "BTN",
        "name": "Raiser",
        "stack_bb": 28.22,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "BB",
        "name": "Hero",
        "stack_bb": 46.43,
        "dealt_in": True,
        "is_hero": True,
    },
]


def obs(frame, seat, value):
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
            "blocker",
            "raiser",
            "hero",
        ],
        small_blind_seat="raiser",
        big_blind_seat="hero",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "blocker": 50.0,
            "raiser": 28.22,
            "hero": 46.43,
        },
        opponent_seats=[
            "blocker",
            "raiser",
        ],
        quantitative_seats=[
            "blocker",
            "raiser",
            "hero",
        ],
        hero_seat="hero",
        hand_id="blocked-call-survives-price-change",
    )

    assert observer.hand.next_actor == "blocker"
    assert observer.hand.current_price_bb == 1.0

    # Physical evidence arrives while blocker is unresolved.
    #
    # Raiser has committed 2 BB total from a 0.5 BB blind:
    # physical decrease = 1.5 BB.
    raiser_obs = obs(
        5,
        "raiser",
        26.72,
    )

    # Hero BB has committed 2 BB total from a 1 BB blind:
    # physical decrease = 1 BB.
    hero_obs = obs(
        5,
        "hero",
        45.43,
    )

    assert observer.admit_quantitative_observation(
        raiser_obs
    ) == ()

    assert observer.admit_quantitative_observation(
        hero_obs
    ) == ()

    retained = {
        row["seat"]: row
        for row in observer.pending_quantitative_evidence
    }

    assert "raiser" in retained
    assert "hero" in retained

    assert (
        retained["hero"]["retained_current_price_bb"]
        == 1.0
    )

    # Earlier unresolved actor is now objectively resolved as fold.
    assert observer.hand.observe_fold(
        "blocker"
    ) == "FOLD"

    assert observer.hand.next_actor == "raiser"

    # Reconcile original physical evidence in frame order.
    #
    # Raiser must become RAISE to 2 BB. Hero's already-confirmed
    # observation must NOT disappear merely because current_price
    # changed from 1 -> 2.
    observer.reconcile_pending_evidence()

    actions = observer.hand.semantic_actions()

    raiser_actions = [
        row
        for row in actions
        if (
            row["seat"] == "raiser"
            and row["action"]
            not in {
                "POST_SMALL_BLIND",
                "POST_BIG_BLIND",
            }
        )
    ]

    hero_actions = [
        row
        for row in actions
        if (
            row["seat"] == "hero"
            and row["action"]
            not in {
                "POST_SMALL_BLIND",
                "POST_BIG_BLIND",
            }
        )
    ]

    retained_hero = [
        row
        for row in observer.pending_quantitative_evidence
        if row.get("seat") == "hero"
    ]

    print()
    print("raiser_actions =", raiser_actions)
    print("hero_actions =", hero_actions)
    print("retained_hero =", retained_hero)
    print("current_price =", observer.hand.current_price_bb)
    print("next_actor =", observer.hand.next_actor)
    print()

    assert len(raiser_actions) == 1
    assert raiser_actions[0]["action"] == "RAISE"
    assert observer.hand.current_price_bb == 2.0

    assert len(hero_actions) == 1, (
        "RED: confirmed Hero commitment was lost when "
        "earlier reconciliation changed betting price"
    )

    assert hero_actions[0]["action"] == "CALL", (
        "RED: retained Hero physical commitment was not "
        "reconciled as the original CALL"
    )

    assert retained_hero == [], (
        "Hero evidence remained stranded after becoming "
        "authoritative"
    )

    assert observer.hand.next_actor is None

    print(
        "BLOCKED CONFIRMED CALL SURVIVES LATER PRICE CHANGE: PASS"
    )
    print(
        "PHYSICAL EVIDENCE CONSUMED EXACTLY ONCE: PASS"
    )


if __name__ == "__main__":
    main()
