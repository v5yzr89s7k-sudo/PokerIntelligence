from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2

from src.vision.stack_reader import (
    read_stack,
)
from src.v017.july22_frame_preflop_replay import (
    GEOMETRY,
)

from src.v017.synthetic_lab.frame_source import (
    RecordedFrameSource,
)


@dataclass(frozen=True)
class StackAsset:
    frame: int
    seat: str
    value: Optional[float]
    width: int
    height: int


def crop_stack(frame, seat):
    rect = GEOMETRY["stack_regions"][seat]

    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    return frame[
        y:y + h,
        x:x + w,
    ].copy()


def mine_stack_assets(
    seats,
    *,
    start=1,
    end=135,
):
    source = RecordedFrameSource()
    assets = []

    for number in range(start, end + 1):
        frame = source.load(number)

        for seat in seats:
            crop = crop_stack(
                frame,
                seat,
            )

            result = read_stack(crop)

            value = getattr(
                result,
                "value",
                None,
            )

            if value is None:
                value = getattr(
                    result,
                    "stack_bb",
                    None,
                )

            if value is None:
                try:
                    value = float(result)
                except (
                    TypeError,
                    ValueError,
                ):
                    value = None

            assets.append(
                StackAsset(
                    frame=number,
                    seat=seat,
                    value=(
                        None
                        if value is None
                        else float(value)
                    ),
                    width=crop.shape[1],
                    height=crop.shape[0],
                )
            )

    return tuple(assets)


def unique_resolved_values(assets):
    return tuple(
        sorted(
            {
                round(asset.value, 2)
                for asset in assets
                if asset.value is not None
            }
        )
    )
