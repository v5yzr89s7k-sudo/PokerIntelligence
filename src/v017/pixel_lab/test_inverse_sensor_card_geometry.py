from pathlib import Path
import json

from src.v017.pixel_lab.acr_pixel_renderer import (
    _inverse_sensor_rect,
)


ROOT = Path(__file__).resolve().parents[3]

CANONICAL = json.loads(
    (
        ROOT / "config/geometry.json"
    ).read_text()
)


def main():
    seats = (
        "seat_upper_left",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
    )

    for seat in seats:
        for card_name in (
            "card_1",
            "card_2",
        ):
            source = (
                CANONICAL[
                    "hole_cards"
                ][seat][card_name]
            )

            target = _inverse_sensor_rect(
                source
            )

            assert target["width"] > 0
            assert target["height"] > 0

            print(
                seat,
                card_name,
                "canonical=",
                source,
                "native_target=",
                target,
            )

    print(
        "FULL-FRAME INVERSE SENSOR GEOMETRY: PASS"
    )
    print(
        "V0.17 INVERSE CARD GEOMETRY: PASS"
    )


if __name__ == "__main__":
    main()
