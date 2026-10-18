"""
Regression: retained PREFLOP card disappearance must never
become a FLOP betting action.
"""

from src.v017.test_pending_card_disappearance_reconciliation import build


def main():
    observer = build()

    observer._retain_pending_card_disappearance(
        "sb",
        frame_id=11,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert observer.hand.street == "PREFLOP"
    assert len(observer.pending_card_disappearances) == 1

    while observer.hand.next_actor is not None:
        seat = observer.hand.next_actor
        player = observer.hand.players[seat]

        if (
            player.street_commitment_bb + 0.02
            < observer.hand.current_price_bb
        ):
            observer.hand.resolve_boundary_completed_actor(seat)
        else:
            observer.hand.observe_no_commitment(seat)

    assert observer.hand.next_actor is None

    observer.hand.start_street(
        "FLOP",
        ["bb", "sb", "hero"],
        board=["As", "Kd", "7c"],
    )

    before = len(observer.hand.actions)

    observer.reconcile_pending_card_disappearances()

    new_actions = observer.hand.semantic_actions()[before:]

    assert not new_actions, (
        "CROSS-STREET CARD OWNERSHIP VIOLATION: "
        f"{new_actions}"
    )

    assert observer.pending_card_disappearances == [], (
        "stale card evidence was not retired"
    )

    # Retain another preflop disappearance, then verify global
    # retirement even when a different actor is next.
    # Separate scenario: old evidence retained behind another actor.
    second = build()
    second._retain_pending_card_disappearance(
        "sb",
        frame_id=12,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    while second.hand.next_actor is not None:
        seat = second.hand.next_actor
        player = second.hand.players[seat]
        if player.street_commitment_bb + 0.02 < second.hand.current_price_bb:
            second.hand.resolve_boundary_completed_actor(seat)
        else:
            second.hand.observe_no_commitment(seat)

    second.hand.start_street(
        "FLOP",
        ["bb", "sb", "hero"],
        board=["As", "Kd", "7c"],
    )

    observer = second

    assert observer.hand.next_actor == "bb"

    before = len(observer.hand.actions)
    observer.reconcile_pending_card_disappearances()

    assert len(observer.hand.actions) == before
    assert observer.pending_card_disappearances == [], (
        "stale evidence survived behind another actor"
    )

    print("CROSS-STREET CARD OWNERSHIP: PASS")


if __name__ == "__main__":
    main()
