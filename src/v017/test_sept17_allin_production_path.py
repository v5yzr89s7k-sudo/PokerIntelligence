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

    order = [
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_mid_left",
        "seat_top",
    ]

    observer = FrameHandObserver(
        players=players,
        action_order=order,
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
        hand_id="sept17-allin-production-path",
        stack_reader=read_stack_native_fast,
    )

    # Deterministic debounce clock.
    observer.bet_region_tracker.clock = clock

    return observer


def run_once():
    assert len(CAPTURES) > 31, (
        f"expected saved Sept17 captures, "
        f"found={len(CAPTURES)}"
    )

    clock = ControlledClock()
    observer = make_observer(clock)
    gate = StackSettlementGate()

    settlements = []
    timeline = []

    # Frame 24 is our known pre-action baseline.
    # Continue through the persistent 22.94 BB bet.
    for source_index in range(24, 32):
        image = cv2.imread(
            str(CAPTURES[source_index])
        )

        assert image is not None, (
            CAPTURES[source_index]
        )

        # Live loop is ~capture cost + 0.20 sleep.
        # 0.25 is deliberately above the 0.15 debounce.
        if source_index > 24:
            clock.advance(0.25)

        result = observer.process_frame(
            image,
            frame_id=source_index,
        )

        quantitative = [
            event
            for event in result.events
            if event.get("type")
            == "STACK_QUANTITATIVE_OBSERVATION"
            and event.get("seat")
            == "seat_mid_right"
        ]

        confirmed = (
            "seat_mid_right"
            in observer.confirmed_bet_regions
        )

        row = {
            "frame": source_index,
            "confirmed_bet": confirmed,
            "quantitative": [],
        }

        for event in quantitative:
            value = event.get(
                "resolved_value"
            )

            has_commitment_evidence = bool(
                "seat_mid_right"
                in observer.confirmed_bet_regions
            )

            all_in_confirmed = bool(
                has_commitment_evidence
                and value is not None
                and abs(float(value)) <= 0.02
            )

            settled = gate.observe(
                event,
                phase=observer.hand.street,
                has_commitment_evidence=(
                    has_commitment_evidence
                ),
                all_in_confirmed=(
                    all_in_confirmed
                ),
            )

            row["quantitative"].append({
                "resolved":
                    event.get("resolved"),
                "value":
                    value,
                "commitment":
                    has_commitment_evidence,
                "all_in":
                    all_in_confirmed,
                "settled":
                    settled is not None,
            })

            if settled is not None:
                settlements.append(
                    (
                        source_index,
                        settled.seat,
                        settled.prior,
                        settled.value,
                        settled.delta_bb,
                    )
                )

        timeline.append(row)

    print(
        "===== PRODUCTION-PATH TIMELINE ====="
    )

    for row in timeline:
        print(row)

    print()
    print(
        "settlements =",
        settlements,
    )

    # --------------------------------------------------------
    # Physical contract.
    # --------------------------------------------------------

    assert (
        timeline[0]["confirmed_bet"]
        is False
    ), timeline[0]

    assert any(
        row["confirmed_bet"]
        for row in timeline[1:]
    ), timeline

    # --------------------------------------------------------
    # Quantitative + physical conjunction must actually reach
    # StackSettlementGate and settle the real transition.
    # --------------------------------------------------------

    target = [
        row
        for row in settlements
        if (
            row[1] == "seat_mid_right"
            and abs(row[2] - 22.94) < 0.01
            and abs(row[3] - 0.0) < 0.01
            and abs(row[4] - 22.94) < 0.01
        )
    ]

    assert len(target) == 1, (
        f"expected exactly one 22.94->0 settlement, "
        f"observed={settlements}"
    )

    print()
    print(
        "SEPT17 ALL-IN PRODUCTION PATH: PASS"
    )

    return (
        tuple(settlements),
        tuple(
            (
                row["frame"],
                row["confirmed_bet"],
                tuple(
                    (
                        item["resolved"],
                        item["value"],
                        item["commitment"],
                        item["all_in"],
                        item["settled"],
                    )
                    for item in row["quantitative"]
                ),
            )
            for row in timeline
        ),
    )


def main():
    first = run_once()

    print()
    print(
        "===== INTERNAL DETERMINISM RUN 2 ====="
    )

    second = run_once()

    assert first == second, (
        "production-path replay changed "
        "between identical runs"
    )

    print()
    print(
        "SEPT17 PRODUCTION-PATH DETERMINISM: PASS"
    )


if __name__ == "__main__":
    main()
