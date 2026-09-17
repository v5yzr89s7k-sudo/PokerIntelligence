from src.v017.hand_engine import HandEngine
from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "hero",
        "position": "UTG",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "seat_top",
        "position": "UTG+1",
        "name": "seat_top",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "seat_upper_right",
        "position": "LJ",
        "name": "seat_upper_right",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "seat_mid_right",
        "position": "HJ",
        "name": "seat_mid_right",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "seat_lower_right",
        "position": "CO",
        "name": "seat_lower_right",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "seat_lower_left",
        "position": "BTN",
        "name": "seat_lower_left",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "seat_mid_left",
        "position": "SB",
        "name": "seat_mid_left",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "seat_upper_left",
        "position": "BB",
        "name": "seat_upper_left",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]

ORDER = [
    "hero",
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]


def make_hand():
    return HandEngine(
        players=PLAYERS,
        action_order=ORDER,
        small_blind_seat="seat_mid_left",
        big_blind_seat="seat_upper_left",
    )


def main():
    print("===== HERO UTG FIRST-ACTOR CONTRACT =====")

    hand = make_hand()

    print("action_order =", hand.action_order)
    print("pending =", hand.pending_to_act)
    print("next_actor =", hand.next_actor)

    assert hand.action_order[0] == "hero"
    assert hand.next_actor == "hero"
    assert hand.players["hero"].position == "UTG"

    print()
    print("CASE 1: HERO UTG FOLD")

    result = hand.observe_fold("hero")

    print("result =", result)
    print("next_actor =", hand.next_actor)

    assert result == "FOLD"
    assert hand.players["hero"].folded is True
    assert hand.next_actor == "seat_top"

    assert hand.actions[-1].seat == "hero"
    assert hand.actions[-1].position == "UTG"
    assert hand.actions[-1].action == "FOLD"

    print("HERO UTG FOLD: PASS")

    print()
    print("CASE 2: HERO UTG CALL")

    hand = make_hand()

    result = hand.observe_stack_commitment(
        "hero",
        1.0,
    )

    print("result =", result)
    print("next_actor =", hand.next_actor)

    assert result == "CALL"
    assert hand.next_actor == "seat_top"

    assert hand.actions[-1].seat == "hero"
    assert hand.actions[-1].position == "UTG"
    assert hand.actions[-1].action == "CALL"
    assert hand.actions[-1].amount_bb == 1.0

    print("HERO UTG CALL: PASS")

    print()
    print("CASE 3: HERO UTG RAISE")

    hand = make_hand()

    result = hand.observe_stack_commitment(
        "hero",
        2.0,
    )

    print("result =", result)
    print("price =", hand.current_price_bb)
    print("next_actor =", hand.next_actor)
    print("pending =", hand.pending_to_act)

    assert result == "RAISE"
    assert hand.current_price_bb == 2.0
    assert hand.next_actor == "seat_top"

    assert hand.actions[-1].seat == "hero"
    assert hand.actions[-1].position == "UTG"
    assert hand.actions[-1].action == "RAISE"
    assert hand.actions[-1].raise_to_bb == 2.0

    print("HERO UTG RAISE: PASS")

    print()
    print(
        "V0.17 HERO UTG FIRST-ACTOR CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
