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


def build(clock):
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
        hand_id="sept17-utg-hj-regression",
        stack_reader=read_stack_native_fast,
    )

    observer.bet_region_tracker.clock = clock

    return observer


def run_once():
    assert len(CAPTURES) > 31

    clock = ControlledClock()
    observer = build(clock)
    gate = StackSettlementGate()

    settlements = []
    admissions = []

    for frame_id in range(32):
        if frame_id:
            clock.advance(0.25)

        image = cv2.imread(
            str(CAPTURES[frame_id])
        )

        assert image is not None

        result = observer.process_frame(
            image,
            frame_id=frame_id,
        )

        for event in result.events:
            if (
                event.get("type")
                != "STACK_QUANTITATIVE_OBSERVATION"
            ):
                continue

            seat = event.get("seat")

            commitment = bool(
                seat
                in observer.confirmed_bet_regions
            )

            value = event.get(
                "resolved_value"
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

            if settled is None:
                continue

            settlements.append(
                (
                    frame_id,
                    settled.seat,
                    round(settled.prior, 2),
                    round(settled.value, 2),
                    round(settled.delta_bb, 2),
                )
            )

            admitted = (
                observer
                .admit_quantitative_observation(
                    event
                )
            )

            if admitted:
                observer.clear_quantitative_ownership(
                    settled.seat
                )
                gate.clear_seat(
                    settled.seat
                )

                admissions.extend(
                    (
                        row["seat"],
                        row["semantic_action"],
                        row["normalized_delta_bb"],
                    )
                    for row in admitted
                )

    assert gate.pending == {}, (
        f"stale settlement candidates: {gate.pending}"
    )

    assert (
        observer.quantitative_retry_pending
        == {}
    ), observer.quantitative_retry_pending

    assert (
        observer.quantitative_confirmation_pending
        == {}
    ), observer.quantitative_confirmation_pending

    semantic = [
        (
            action.seat,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in observer.hand.actions
    ]

    expected_semantic = [
        (
            "seat_mid_left",
            "POST_SMALL_BLIND",
            0.5,
            None,
        ),
        (
            "seat_top",
            "POST_BIG_BLIND",
            1.0,
            None,
        ),
        (
            "seat_upper_right",
            "RAISE",
            None,
            6.0,
        ),
        (
            "seat_mid_right",
            "RAISE",
            None,
            22.94,
        ),
    ]

    assert semantic == expected_semantic, (
        semantic
    )

    assert settlements == [
        (
            18,
            "seat_upper_right",
            92.75,
            86.75,
            6.0,
        ),
        (
            30,
            "seat_mid_right",
            22.94,
            0.0,
            22.94,
        ),
    ], settlements

    assert admissions == [
        (
            "seat_upper_right",
            "RAISE",
            6.0,
        ),
        (
            "seat_mid_right",
            "RAISE",
            22.94,
        ),
    ], admissions

    assert (
        observer.trusted_stacks[
            "seat_upper_right"
        ]
        == 86.75
    )

    assert (
        observer.trusted_stacks[
            "seat_mid_right"
        ]
        == 0.0
    )

    assert (
        observer.hand.next_actor
        == "seat_lower_right"
    )

    text = observer.previous_text or ""

    utg = "UTG raises to 6 BB"
    hj = "HJ raises to 22.94 BB"

    assert utg in text, text
    assert hj in text, text

    assert text.index(utg) < text.index(hj)

    assert (
        text.count(utg) == 1
    )

    assert (
        text.count(hj) == 1
    )

    print(
        "settlements =",
        settlements,
    )
    print(
        "admissions =",
        admissions,
    )
    print(
        "next_actor =",
        observer.hand.next_actor,
    )
    print()
    print(text)

    return (
        tuple(settlements),
        tuple(admissions),
        tuple(semantic),
        text,
    )


def main():
    first = run_once()

    print()
    print(
        "===== INTERNAL RUN 2 ====="
    )

    second = run_once()

    assert first == second

    print()
    print(
        "V0.17 SEPT17 UTG -> HJ PRODUCT CHRONOLOGY: PASS"
    )


if __name__ == "__main__":
    main()
