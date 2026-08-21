import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


HAND_TOKEN = "physical-repair-test"


def reset_tracker():
    sm._ACTIVE_TRACKER = None
    sm._ACTIVE_HAND_ID = None


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="physical-repair-test",
        players=[
            {
                "seat": "seat_mid_left",
                "name": "UTG",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "seat_upper_left",
                "name": "LJ",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "seat_upper_right",
                "name": "HJ",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BB",
        positions={
            "seat_mid_left": "UTG",
            "seat_upper_left": "LJ",
            "seat_upper_right": "HJ",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"
    hand.current_bet_bb = 1.0

    hand.players_to_act = [
        "seat_mid_left",
        "seat_upper_left",
        "seat_upper_right",
        "hero",
    ]

    hand.dealt_in_seats = list(
        hand.players_to_act
    )

    return hand


def make_state():
    state = sm.default_state()

    state["phase"] = "PREFLOP"
    state["hand_token"] = HAND_TOKEN
    state["canonical_snapshot_ready"] = True

    return state


def test_later_physical_completion_repairs_missed_predecessor():
    reset_tracker()

    hand = make_hand()
    sm.canonical_save(hand)

    state = make_state()

    # UTG's direct card-disappearance observation was missed.
    #
    # LJ now physically disappears. Chronology proves UTG has already
    # completed its action. With no unresolved commitment evidence,
    # actor_observed may safely infer UTG FOLD. Then LJ is queue head
    # and its direct physical completion resolves LJ FOLD.
    state = sm.handle_physical_actor_completed(
        state,
        {
            "type": "physical_actor_completed",
            "hand_token": HAND_TOKEN,
            "seat": "seat_upper_left",
            "street": "PREFLOP",
            "source": "opponent_hole_cards_disappeared",
            "ts": 2.0,
        },
    )

    hand = sm.canonical_load()

    actions = [
        (action.seat, action.action)
        for action in hand.actions
    ]

    assert actions == [
        ("seat_mid_left", "FOLD"),
        ("seat_upper_left", "FOLD"),
    ], actions

    assert hand.players["seat_mid_left"].folded
    assert hand.players["seat_upper_left"].folded

    assert hand.players_to_act == [
        "seat_upper_right",
        "hero",
    ], hand.players_to_act

    print(
        "PASS physical chronology repair: "
        "missed UTG fold is inferred from later LJ completion, "
        "then LJ physical fold resolves normally"
    )


def test_commitment_blocker_prevents_repair_through_utg():
    reset_tracker()

    hand = make_hand()
    sm.canonical_save(hand)

    state = make_state()

    # Independent commitment evidence for UTG makes a passive-fold
    # inference unsafe.
    state = sm.handle_stack_candidate_opened(
        state,
        {
            "type": "stack_candidate_opened",
            "hand_token": HAND_TOKEN,
            "seat": "seat_mid_left",
            "street": "PREFLOP",
            "sources": [
                "bet_region_appeared",
            ],
            "ts": 1.5,
        },
    )

    state = sm.handle_physical_actor_completed(
        state,
        {
            "type": "physical_actor_completed",
            "hand_token": HAND_TOKEN,
            "seat": "seat_upper_left",
            "street": "PREFLOP",
            "source": "opponent_hole_cards_disappeared",
            "ts": 2.0,
        },
    )

    hand = sm.canonical_load()

    assert not hand.players["seat_mid_left"].folded
    assert not hand.players["seat_upper_left"].folded

    assert hand.actions == []

    assert hand.players_to_act == [
        "seat_mid_left",
        "seat_upper_left",
        "seat_upper_right",
        "hero",
    ]

    print(
        "PASS physical chronology blocker: "
        "later physical completion cannot infer through "
        "earlier independent commitment evidence"
    )


if __name__ == "__main__":
    test_later_physical_completion_repairs_missed_predecessor()
    test_commitment_blocker_prevents_repair_through_utg()
