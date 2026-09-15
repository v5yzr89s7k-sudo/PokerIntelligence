"""
v0.16 hand-scoped physical-card action ownership contract.

This state is not poker semantics and not roster ownership.

It records only this fact:

    seat has been positively observed with visible hole cards
    after acquisition of the current hand token.

A later visible->absent transition may become physical action evidence
only for a seat carrying this same-hand ownership.
"""

from src.api import api_event_coordinator as coordinator


def main():
    # --------------------------------------------------------------
    # No hand token means there is no hand-scoped action ownership.
    # --------------------------------------------------------------
    state = {
        "hand_token": None,
    }

    result = coordinator.update_physical_card_action_ownership(
        state,
        visible_seats=["seat_top", "seat_mid_right"],
    )

    assert result is state
    assert state.get("physical_card_action_ownership") in {
        None,
    }, (
        "tokenless observation created hand ownership"
    )

    # --------------------------------------------------------------
    # First owned frame establishes the same-hand visible baseline.
    # Hero must never enter opponent physical-card ownership.
    # --------------------------------------------------------------
    state["hand_token"] = "hand-a"

    coordinator.update_physical_card_action_ownership(
        state,
        visible_seats=[
            "seat_top",
            "seat_mid_right",
            "hero",
        ],
    )

    ownership = state["physical_card_action_ownership"]

    assert ownership["hand_token"] == "hand-a"
    assert ownership["visible_seats"] == [
        "seat_top",
        "seat_mid_right",
    ]

    # --------------------------------------------------------------
    # Ownership is monotonic during the hand.
    #
    # A later frame may positively reveal another seat. A seat that is
    # currently absent is NOT removed, because its prior same-hand
    # visibility is exactly what authorizes a later disappearance.
    # --------------------------------------------------------------
    coordinator.update_physical_card_action_ownership(
        state,
        visible_seats=[
            "seat_mid_right",
            "seat_lower_right",
        ],
    )

    ownership = state["physical_card_action_ownership"]

    assert ownership["hand_token"] == "hand-a"
    assert ownership["visible_seats"] == [
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
    ], ownership

    # --------------------------------------------------------------
    # New hand token must reset old-hand visibility ownership.
    # --------------------------------------------------------------
    state["hand_token"] = "hand-b"

    coordinator.update_physical_card_action_ownership(
        state,
        visible_seats=[
            "seat_lower_left",
        ],
    )

    ownership = state["physical_card_action_ownership"]

    assert ownership == {
        "hand_token": "hand-b",
        "visible_seats": [
            "seat_lower_left",
        ],
    }, ownership

    assert "seat_top" not in ownership["visible_seats"]
    assert "seat_mid_right" not in ownership["visible_seats"]
    assert "seat_lower_right" not in ownership["visible_seats"]

    # --------------------------------------------------------------
    # Duplicate samples are idempotent.
    # --------------------------------------------------------------
    coordinator.update_physical_card_action_ownership(
        state,
        visible_seats=[
            "seat_lower_left",
            "seat_lower_left",
        ],
    )

    assert state["physical_card_action_ownership"] == {
        "hand_token": "hand-b",
        "visible_seats": [
            "seat_lower_left",
        ],
    }

    print(
        "PASS physical card action ownership state: "
        "token-scoped, monotonic, hero-excluding, new-hand reset"
    )


if __name__ == "__main__":
    main()
