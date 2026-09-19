from pathlib import Path
import json

from src.v017.pixel_lab.acr_pixel_renderer import (
    BOARD_ORDER,
    _inverse_sensor_rect,
)


ROOT = Path(__file__).resolve().parents[3]

CANONICAL = json.loads(
    (
        ROOT / "config/geometry.json"
    ).read_text()
)


def main():
    for card_name in BOARD_ORDER:
        source = (
            CANONICAL[
                "board"
            ][card_name]
        )

        target = _inverse_sensor_rect(
            source
        )

        assert target["width"] > 0
        assert target["height"] > 0

        assert (
            target["x"]
            + target["width"]
            <= 3456
        )

        assert (
            target["y"]
            + target["height"]
            <= 2168
        )

        print(
            card_name,
            "canonical=",
            source,
            "native_target=",
            target,
        )

    print(
        "FULL-FRAME INVERSE BOARD GEOMETRY: PASS"
    )
    print(
        "V0.17 INVERSE BOARD GEOMETRY: PASS"
    )


if __name__ == "__main__":
    main()
