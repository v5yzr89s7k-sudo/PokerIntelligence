from pathlib import Path
import json

import cv2

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)
from src.vision.stack_reader import (
    read_stack_native_fast,
)


ROOT = Path(__file__).resolve().parents[2]

CAPTURES = sorted(
    (
        ROOT
        / "runtime/window_captures"
    ).glob(
        "acr_table_20260917_1515*.png"
    )
)

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)


class ControlledClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)


def make_observer(clock):
    players = [
        {
            "seat": "seat_upper_right",
            "position": "UTG",
            "name": "seat_upper_right",
            "stack_bb": 92.75,
            "dealt_in": True,
        },
        {
            "seat": "seat_mid_right",
            "position": "HJ",
            "name": "seat_mid_right",
            "stack_bb": 22.94,
            "dealt_in": True,
        },
        {
            "seat": "seat_lower_right",
            "position": "CO",
            "name": "seat_lower_right",
            "stack_bb": 80.81,
            "dealt_in": True,
        },
        {
            "seat": "hero",
            "position": "BTN",
            "name": "Hero",
            "stack_bb": 46.92,
            "dealt_in": True,
        },
        {
            "seat": "seat_mid_left",
            "position": "SB",
            "name": "seat_mid_left",
            "stack_bb": 16.68,
            "dealt_in": True,
        },
        {
            "seat": "seat_top",
            "position": "BB",
            "name": "seat_top",
            "stack_bb": 59.35,
            "dealt_in": True,
        },
    ]

    observer = FrameHandObserver(
        players=players,
        action_order=[
            "seat_upper_right",
            "seat_mid_right",
            "seat_lower_right",
            "hero",
            "seat_mid_left",
            "seat_top",
        ],
        small_blind_seat="seat_mid_left",
        big_blind_seat="seat_top",
        geometry=GEOMETRY,
        trusted_stacks={
            "seat_upper_right": 92.75,
            "seat_mid_right": 22.94,
            "seat_lower_right": 80.81,
            "hero": 46.92,
            "seat_mid_left": 16.68,
            "seat_top": 59.35,
        },
        opponent_seats=[
            "seat_upper_right",
            "seat_mid_right",
            "seat_lower_right",
            "seat_mid_left",
            "seat_top",
        ],
        quantitative_seats=[
            "seat_upper_right",
            "seat_mid_right",
        ],
        hero_seat="hero",
        hand_id="sept17-combined-chronology",
        stack_reader=read_stack_native_fast,
    )

    observer.bet_region_tracker.clock = clock

    return observer


def main():
    assert len(CAPTURES) > 31

    clock = ControlledClock()
    observer = make_observer(clock)
    gate = StackSettlementGate()

    settlements = []
    admissions = []

    print(
        "===== STARTING HAND ====="
    )
    print(
        "next_actor =",
        observer.hand.next_actor,
    )
    print(
        "trusted_stacks =",
        observer.trusted_stacks,
    )
    print()

    for frame_id in range(0, 32):
        if frame_id > 0:
            clock.advance(0.25)

        image = cv2.imread(
            str(CAPTURES[frame_id])
        )

        assert image is not None

        result = observer.process_frame(
            image,
            frame_id=frame_id,
        )

        quantitative = [
            event
            for event in result.events
            if event.get("type")
            == "STACK_QUANTITATIVE_OBSERVATION"
        ]

        for event in quantitative:
            seat = event.get("seat")
            value = event.get(
                "resolved_value"
            )

            commitment = bool(
                seat
                in observer.confirmed_bet_regions
            )

            all_in = bool(
                commitment
                and value is not None
                and abs(float(value)) <= 0.02
            )

            settled = gate.observe(
                event,
                phase=observer.hand.street,
                has_commitment_evidence=commitment,
                all_in_confirmed=all_in,
            )

            print(
                "[Q]",
                f"frame={frame_id}",
                f"seat={seat}",
                f"resolved={event.get('resolved')}",
                f"value={value}",
                f"mode={event.get('mode')}",
                f"commitment={commitment}",
                f"settled={settled}",
            )

            if settled is None:
                continue

            settlements.append(
                (
                    frame_id,
                    settled.seat,
                    settled.prior,
                    settled.value,
                    settled.delta_bb,
                )
            )

            # Match run_live_observer.py exactly:
            #
            # StackSettlementGate authorizes the original physical
            # observation. It does not replace or rewrite that
            # observation before semantic admission.
            admitted = (
                observer
                .admit_quantitative_observation(
                    event
                )
            )

            admissions.append(
                (
                    frame_id,
                    settled.seat,
                    admitted,
                    observer.hand.next_actor,
                )
            )

            print(
                "[ADMISSION]",
                f"frame={frame_id}",
                f"seat={settled.seat}",
                f"result={admitted}",
                f"next_actor={observer.hand.next_actor}",
            )

        if (
            frame_id >= 10
            and (
                quantitative
                or frame_id
                in (12, 13, 17, 18, 25, 30, 31)
            )
        ):
            print(
                "[STATE]",
                f"frame={frame_id}",
                f"next_actor={observer.hand.next_actor}",
                f"bets={sorted(observer.confirmed_bet_regions)}",
                f"retry={observer.quantitative_retry_pending}",
                f"gate_pending={gate.pending}",
            )

    print()
    print(
        "===== SETTLEMENTS ====="
    )

    for row in settlements:
        print(row)

    print()
    print(
        "===== ADMISSIONS ====="
    )

    for row in admissions:
        print(row)

    print()
    print(
        "===== FINAL ACTIONS ====="
    )

    for index, action in enumerate(
        observer.hand.actions,
        1,
    ):
        print(
            index,
            action.street,
            action.seat,
            getattr(
                action,
                "action",
                None,
            ),
            action.amount_bb,
            action.raise_to_bb,
        )

    print()
    print(
        "===== FINAL PRODUCT ====="
    )

    print(
        observer.previous_text
        or "<NO PUBLICATION>"
    )

    print()
    print(
        "===== REQUIRED CHRONOLOGY ====="
    )
    print(
        "UTG must settle/admit before HJ."
    )
    print(
        "Expected UTG physical delta = 6.00 BB."
    )
    print(
        "Expected HJ physical delta = 22.94 BB."
    )

    print()
    print(
        "COMBINED TRACE COMPLETE"
    )


if __name__ == "__main__":
    main()
