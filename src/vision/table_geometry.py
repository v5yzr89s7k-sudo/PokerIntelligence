from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    x: float
    y: float
    w: float
    h: float


#
# All coordinates are percentages of the normalized table image.
#

SEATS = {
    "seat_top": Region(0.40, 0.10, 0.20, 0.25),

    "seat_upper_left": Region(0.06, 0.18, 0.25, 0.30),

    "seat_upper_right": Region(0.68, 0.18, 0.25, 0.30),

    "seat_mid_left": Region(0.02, 0.42, 0.25, 0.25),

    "seat_mid_right": Region(0.72, 0.42, 0.25, 0.25),

    "seat_lower_left": Region(0.18, 0.62, 0.25, 0.25),

    "seat_lower_right": Region(0.58, 0.62, 0.25, 0.25),

    "hero": Region(0.38, 0.68, 0.25, 0.25),
}


BOARD = Region(
    0.28,
    0.32,
    0.44,
    0.20,
)


HERO_CARDS = Region(
    0.42,
    0.77,
    0.18,
    0.13,
)


ACTION_BUTTONS = Region(
    0.63,
    0.78,
    0.36,
    0.20,
)
