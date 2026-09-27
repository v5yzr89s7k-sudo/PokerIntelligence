"""
Canonical HandEngine temporal identity enrichment contract.

Verified identity enrichment:
  * fills a previously blank PlayerState.name;
  * fills already-admitted blank same-seat HandAction.name values;
  * never changes another seat;
  * never changes poker semantics;
  * is idempotent for the same verified identity;
  * rejects a conflicting nonblank identity;
  * rejects an unknown physical seat;
  * ignores blank enrichment.
"""

from copy import deepcopy

from src.v017.hand_engine import HandEngine


def build_hand():
    players = [
        {
            "seat": "seat_upper_left",
            "position": "UTG",
            "name": "",
            "stack_bb": 41.52,
            "dealt_in": True,
        },
        {
            "seat": "hero",
            "position": "BB",
            "name": "Hero",
            "stack_bb": 100.0,
            "dealt_in": True,
        },
    ]

    return HandEngine(
        players=players,
        action_order=[
            "seat_upper_left",
            "hero",
        ],
        small_blind_seat="seat_upper_left",
        big_blind_seat="hero",
    )


def semantic_snapshot(hand):
    return [
        (
            action.sequence,
            action.street,
            action.seat,
            action.position,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in hand.actions
    ]


def main():
    hand = build_hand()

    # Forced blind action is admitted during HandEngine construction
    # while the opponent identity is unresolved.
    target_actions = [
        action
        for action in hand.actions
        if action.seat == "seat_upper_left"
    ]

    assert target_actions
    assert all(
        action.name == ""
        for action in target_actions
    )

    before_semantics = semantic_snapshot(hand)
    before_other_player = deepcopy(
        hand.players["hero"]
    )

    changed = hand.enrich_player_identity(
        "seat_upper_left",
        "VerifiedOpponent",
    )

    assert changed is True

    assert (
        hand.players["seat_upper_left"].name
        == "VerifiedOpponent"
    )

    target_actions = [
        action
        for action in hand.actions
        if action.seat == "seat_upper_left"
    ]

    assert all(
        action.name == "VerifiedOpponent"
        for action in target_actions
    )

    # No poker semantic field changed.
    assert semantic_snapshot(hand) == before_semantics

    # Another physical player is untouched.
    assert (
        hand.players["hero"]
        == before_other_player
    )

    # Same verified identity is idempotent.
    assert (
        hand.enrich_player_identity(
            "seat_upper_left",
            "VerifiedOpponent",
        )
        is False
    )

    assert semantic_snapshot(hand) == before_semantics

    # Blank input has no authority.
    assert (
        hand.enrich_player_identity(
            "seat_upper_left",
            "",
        )
        is False
    )

    # An established verified identity is immutable.
    try:
        hand.enrich_player_identity(
            "seat_upper_left",
            "DifferentOpponent",
        )
    except ValueError as exc:
        assert "identity conflict" in str(exc)
    else:
        raise AssertionError(
            "conflicting verified identity was accepted"
        )

    # Physical topology is immutable.
    try:
        hand.enrich_player_identity(
            "seat_not_present",
            "Invented",
        )
    except ValueError as exc:
        assert "unknown player seat" in str(exc)
    else:
        raise AssertionError(
            "unknown seat identity was accepted"
        )

    assert semantic_snapshot(hand) == before_semantics

    print(
        "HANDENGINE IDENTITY ENRICHMENT CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
