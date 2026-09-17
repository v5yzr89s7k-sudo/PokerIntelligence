from pathlib import Path
import json
import pprint

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
            "stack_bb": 86.75,
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
            "seat_upper_right": 86.75,
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
            "seat_mid_right",
        ],
        hero_seat="hero",
        hand_id="sept17-settlement-trace",
        stack_reader=read_stack_native_fast,
    )

    observer.bet_region_tracker.clock = clock

    return observer


def candidate_state(gate):
    # Do not assume the private attribute name.
    result = {}

    for name, value in vars(gate).items():
        if (
            "candidate" in name.lower()
            or "pending" in name.lower()
            or "state" in name.lower()
        ):
            result[name] = value

    return result


def main():
    assert len(CAPTURES) > 31

    clock = ControlledClock()
    observer = make_observer(clock)
    gate = StackSettlementGate()

    seen = []

    for frame_id in range(24, 32):
        if frame_id > 24:
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
                or event.get("seat")
                != "seat_mid_right"
            ):
                continue

            value = event.get(
                "resolved_value"
            )

            commitment = (
                "seat_mid_right"
                in observer.confirmed_bet_regions
            )

            all_in = bool(
                commitment
                and value is not None
                and abs(float(value)) <= 0.02
            )

            print()
            print(
                "================================================"
            )
            print(
                f"REAL EVENT frame={frame_id}"
            )
            print(
                "================================================"
            )

            pprint.pp(event)

            print()
            print(
                "commitment =",
                commitment,
            )
            print(
                "all_in =",
                all_in,
            )

            print()
            print(
                "GATE BEFORE:"
            )
            pprint.pp(
                candidate_state(gate)
            )

            settled = gate.observe(
                event,
                phase=observer.hand.street,
                has_commitment_evidence=commitment,
                all_in_confirmed=all_in,
            )

            print()
            print(
                "SETTLED =",
                settled,
            )

            print()
            print(
                "GATE AFTER:"
            )
            pprint.pp(
                candidate_state(gate)
            )

            seen.append(
                (
                    frame_id,
                    dict(event),
                    settled,
                )
            )

    print()
    print(
        "===== EVENT COUNT ====="
    )
    print(
        len(seen)
    )

    assert [
        row[0]
        for row in seen
    ] == [
        25,
        30,
    ], seen

    first = seen[0][1]
    second = seen[1][1]

    print()
    print(
        "===== FIELD-BY-FIELD DIFFERENCE ====="
    )

    keys = sorted(
        set(first)
        | set(second)
    )

    for key in keys:
        a = first.get(key)
        b = second.get(key)

        marker = (
            "SAME"
            if a == b
            else "DIFF"
        )

        print(
            f"{marker:4s}",
            f"{key:28s}",
            repr(a),
            "->",
            repr(b),
        )

    print()
    print(
        "TRACE COMPLETE"
    )


if __name__ == "__main__":
    main()
