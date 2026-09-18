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
        "seat": "seat_mid_right",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": 31.01,
    },
    {
        "seat": "hero",
        "position": "HJ",
        "name": "Hero",
        "stack_bb": 18.30,
    },
    {
        "seat": "seat_lower_left",
        "position": "CO",
        "name": "CO",
        "stack_bb": 31.11,
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
]


def observation(
    seat,
    frame,
    prior,
    value,
):
    return {
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "frame": frame,
        "resolved": True,
        "resolved_value": value,
        "prior": prior,
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        # Exact Live #2 authoritative chronology at failure.
        #
        # The live log proves seat_lower_left was next_actor while
        # seat_mid_right and hero remained later pending actors.
        action_order=[
            "seat_lower_left",
            "seat_mid_right",
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
            row["seat"]: row["stack_bb"]
            for row in PLAYERS
        },
        opponent_seats=[
            "seat_mid_right",
            "seat_lower_left",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "seat_mid_right",
            "hero",
            "seat_lower_left",
        ],
        hero_seat="hero",
        hand_id="live2-adversarial",
    )

    gate = StackSettlementGate()

    # Exact Live #2 corruption pattern.
    frames = {
        24: (
            observation(
                "seat_mid_right",
                24,
                31.01,
                30.91,
            ),
            observation(
                "hero",
                24,
                18.30,
                18.20,
            ),
        ),
        25: (
            observation(
                "hero",
                25,
                18.30,
                18.20,
            ),
            observation(
                "seat_lower_left",
                25,
                31.11,
                31.01,
            ),
        ),
        26: (
            observation(
                "seat_lower_left",
                26,
                31.11,
                31.01,
            ),
        ),
    }

    admitted = []

    for frame in (24, 25, 26):
        result = process_quantitative_frame(
            observer,
            gate,
            frames[frame],
        )

        print()
        print("frame =", frame)

        print(
            "rejected =",
            [
                row["seat"]
                for row
                in result.rejected_common_mode
            ],
        )

        print(
            "deferred =",
            [
                (
                    row["seat"],
                    row["resolved_value"],
                )
                for row in result.deferred
            ],
        )

        print(
            "settled =",
            [
                (
                    row.seat,
                    row.prior,
                    row.value,
                    row.delta_bb,
                )
                for row in result.settled
            ],
        )

        print(
            "admitted =",
            [
                (
                    row.get("seat"),
                    row.get("action"),
                )
                for row in result.admitted
            ],
        )

        print(
            "pending =",
            gate.pending,
        )

        admitted.extend(
            result.admitted
        )

    print()
    print(
        "semantic actions =",
        observer.hand.semantic_actions(),
    )

    print(
        "trusted stacks =",
        observer.trusted_stacks,
    )

    # --------------------------------------------------------
    # REQUIRED SAFETY CONTRACT
    #
    # The three staggered 0.10 BB shifts are correlated
    # measurement corruption, not poker actions.
    #
    # No semantic action may be created and no trusted stack
    # may move.
    # --------------------------------------------------------

    assert admitted == [], (
        "LIVE #2 REPRODUCED: staggered 0.10 BB "
        "measurement corruption acquired semantic authority"
    )

    assert len(
        observer.hand.semantic_actions()
    ) == 2, (
        "LIVE #2 REPRODUCED: false quantitative "
        "action entered HandEngine"
    )

    assert (
        observer.trusted_stacks[
            "seat_mid_right"
        ]
        == 31.01
    )

    assert (
        observer.trusted_stacks["hero"]
        == 18.30
    ), (
        "LIVE #2 REPRODUCED: Hero false 0.10 "
        "transition mutated trusted stack"
    )

    assert (
        observer.trusted_stacks[
            "seat_lower_left"
        ]
        == 31.11
    ), (
        "LIVE #2 REPRODUCED: CO false 0.10 "
        "transition mutated trusted stack"
    )

    print()
    print(
        "V0.17 LIVE #2 STAGGERED FALSE STACK "
        "SEQUENCE: PASS"
    )


if __name__ == "__main__":
    main()
