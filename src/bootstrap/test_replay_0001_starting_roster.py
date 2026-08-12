import cv2
import json
from pathlib import Path
from unittest.mock import patch

from src.bootstrap.hero_bootstrap import HeroBootstrap
from src.events.detectors.seat_occupancy_detector import occupied_seats


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/debug/action_sequence/20260812_104222/0001_full.png"
)

GEOMETRY = json.loads(
    (ROOT / "config/geometry.json").read_text()
)


class FakeParticipantCollector:
    def freeze(self, *args, **kwargs):
        return [
            "seat_top",
            "seat_mid_right",
            "seat_lower_right",
            "hero",
            "seat_lower_left",
            "seat_mid_left",
        ]


def main():
    image = cv2.imread(str(FRAME))

    if image is None:
        raise RuntimeError(
            f"Replay 0001 frame missing: {FRAME}"
        )

    image = cv2.resize(
        image,
        (934, 696),
    )

    roster = occupied_seats(
        image,
        GEOMETRY,
    )

    expected_roster = [
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
    ]

    assert roster == expected_roster, (
        roster,
        expected_roster,
    )

    # Replay 0001 ground truth places the dealer button such that Hero is BTN
    # with this seven-seat starting roster.
    #
    # Patch only external acquisition; exercise real position assignment.
    with patch(
        "src.bootstrap.hero_bootstrap.freeze_participants",
        return_value=[
            "seat_top",
            "seat_mid_right",
            "seat_lower_right",
            "hero",
            "seat_lower_left",
            "seat_mid_left",
        ],
    ), patch(
        "src.bootstrap.hero_bootstrap.detect_dealer_button",
        return_value={
            "dealer_button_seat": "hero",
            "confidence": 1.0,
        },
    ):
        result = HeroBootstrap.initialize_hand(
            result={
                "ok": True,
                "hero_cards": ["6c", "8d"],
                "canonical_frame": str(FRAME),
            },
            participant_collector=FakeParticipantCollector(),
            hand_token="replay_0001",
            frozen_ts=0.0,
            starting_roster_seats=roster,
        )

    assert result["frozen_participants"] == [
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
    ]

    assert result["starting_roster_seats"] == expected_roster

    expected_positions = {
        "hero": "BTN",
        "seat_lower_left": "SB",
        "seat_mid_left": "BB",
        "seat_upper_left": "UTG",
        "seat_top": "UTG+1",
        "seat_mid_right": "HJ",
        "seat_lower_right": "CO",
    }

    assert result["positions"] == expected_positions, (
        result["positions"],
        expected_positions,
    )

    print(
        "PASS Replay 0001 starting roster: "
        "7 players, physical LJ slot preserved, Hero BTN"
    )


if __name__ == "__main__":
    main()
