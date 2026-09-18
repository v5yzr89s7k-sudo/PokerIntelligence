from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
from src.v017.quantitative_transaction import (
    process_quantitative_frame,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


PLAYERS = [
    {
        "seat": "short",
        "position": "UTG",
        "name": "Short",
        "stack_bb": 0.40,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 40.0,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 40.0,
    },
    {
        "seat": "hero",
        "position": "BTN",
        "name": "Hero",
        "stack_bb": 40.0,
        "is_hero": True,
    },
]


def observation(frame):
    return {
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "short",
        "frame": frame,
        "resolved": True,
        "resolved_value": 0.0,
        "prior": 0.40,
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "short",
            "hero",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
        geometry={
            "stack_regions": {},
            "hole_cards": {},
            "hero_cards": {},
            "board": {},
        },
        trusted_stacks={
            "short": 0.40,
            "hero": 40.0,
            "sb": 40.0,
            "bb": 40.0,
        },
        opponent_seats=[
            "short",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "short",
        ],
        hero_seat="hero",
        hand_id="short-allin-propagation",
    )

    # Independent physical commitment evidence has already
    # confirmed that the zero-stack transition is an all-in.
    observer.confirmed_bet_regions = {
        "short",
    }

    gate = StackSettlementGate()

    first = process_quantitative_frame(
        observer,
        gate,
        (observation(10),),
    )

    print("frame10 settled =", first.settled)
    print("frame10 admitted =", first.admitted)

    assert first.settled == ()
    assert first.admitted == ()

    second = process_quantitative_frame(
        observer,
        gate,
        (observation(11),),
    )

    print("frame11 settled =", second.settled)
    print("frame11 admitted =", second.admitted)

    # Settlement must succeed first.
    assert len(second.settled) == 1

    # And the same explicit all-in authority must survive the
    # transaction boundary into semantic admission.
    assert second.admitted, (
        "MISSING ARCHITECTURE: all_in_confirmed was "
        "established by settlement but lost before "
        "semantic admission"
    )

    print()
    print(
        "V0.17 QUANTITATIVE ALL-IN AUTHORITY "
        "PROPAGATION: PASS"
    )


if __name__ == "__main__":
    main()
