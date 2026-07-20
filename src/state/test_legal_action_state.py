from src.state.canonical_hand import CanonicalHand
from src.state.legal_action_state import (
    BET,
    CALL,
    CHECK,
    FOLD,
    RAISE,
    derive_legal_action_state,
)
from src.state.street_commitment_tracker import (
    StreetCommitmentState,
)


def make_hand():
    return CanonicalHand().start_hand(
        hand_id="legal-action-state",
        players=[
            {
                "seat": "seat_top",
                "name": "UTG",
                "stack_bb": 40,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 40,
                "is_hero": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BB",
        positions={
            "seat_top": "UTG",
            "hero": "BB",
        },
        started_ts=1000.0,
    )


def test_closed_betting_allows_check_or_bet():
    hand = make_hand()

    state = StreetCommitmentState(
        street="PREFLOP",
        street_order=[
            "seat_top",
            "hero",
        ],
        pending_to_act=[
            "seat_top",
            "hero",
        ],
        betting_open=False,
    )

    legal = derive_legal_action_state(
        hand,
        state,
        "seat_top",
    )

    assert legal.action_due is True
    assert legal.legal_actions == [
        CHECK,
        BET,
    ]
    assert legal.call_amount_bb == 0.0


def test_open_betting_requires_fold_call_or_raise():
    hand = make_hand()

    hand.players["hero"].committed_by_street[
        "PREFLOP"
    ] = 1.0

    state = StreetCommitmentState(
        street="PREFLOP",
        street_order=[
            "seat_top",
            "hero",
        ],
        needs_response_from=[
            "hero",
        ],
        current_price=3.5,
        betting_open=True,
        last_aggressor="seat_top",
    )

    legal = derive_legal_action_state(
        hand,
        state,
        "hero",
    )

    assert legal.action_due is True
    assert legal.owes_response is True
    assert legal.legal_actions == [
        FOLD,
        CALL,
        RAISE,
    ]
    assert legal.committed_bb == 1.0
    assert legal.current_price_bb == 3.5
    assert legal.call_amount_bb == 2.5


def test_non_responder_has_no_action_due():
    hand = make_hand()

    state = StreetCommitmentState(
        street="PREFLOP",
        street_order=[
            "seat_top",
            "hero",
        ],
        needs_response_from=[
            "hero",
        ],
        current_price=2.5,
        betting_open=True,
        last_aggressor="seat_top",
    )

    legal = derive_legal_action_state(
        hand,
        state,
        "seat_top",
    )

    assert legal.action_due is False
    assert legal.legal_actions == []
    assert legal.owes_response is False


def test_folded_player_has_no_legal_actions():
    hand = make_hand()

    player = hand.players["hero"]
    player.folded = True
    player.active = False

    state = StreetCommitmentState(
        street="PREFLOP",
        needs_response_from=[
            "hero",
        ],
        current_price=2.5,
        betting_open=True,
    )

    legal = derive_legal_action_state(
        hand,
        state,
        "hero",
    )

    assert legal.action_due is False
    assert legal.legal_actions == []


def test_all_in_player_has_no_legal_actions():
    hand = make_hand()

    hand.players["hero"].all_in = True

    state = StreetCommitmentState(
        street="PREFLOP",
        needs_response_from=[
            "hero",
        ],
        current_price=10.0,
        betting_open=True,
    )

    legal = derive_legal_action_state(
        hand,
        state,
        "hero",
    )

    assert legal.action_due is False
    assert legal.legal_actions == []


def test_unknown_seat_has_no_legal_actions():
    hand = make_hand()

    state = StreetCommitmentState(
        street="PREFLOP",
        pending_to_act=[
            "missing",
        ],
    )

    legal = derive_legal_action_state(
        hand,
        state,
        "missing",
    )

    assert legal.action_due is False
    assert legal.legal_actions == []


def test_serialization():
    hand = make_hand()

    state = StreetCommitmentState(
        street="PREFLOP",
        pending_to_act=[
            "hero",
        ],
    )

    legal = derive_legal_action_state(
        hand,
        state,
        "hero",
    )

    data = legal.to_dict()

    assert data["seat"] == "hero"
    assert data["action_due"] is True
    assert data["legal_actions"] == [
        CHECK,
        BET,
    ]


if __name__ == "__main__":
    test_closed_betting_allows_check_or_bet()
    test_open_betting_requires_fold_call_or_raise()
    test_non_responder_has_no_action_due()
    test_folded_player_has_no_legal_actions()
    test_all_in_player_has_no_legal_actions()
    test_unknown_seat_has_no_legal_actions()
    test_serialization()

    print("LegalActionState regression tests passed.")
