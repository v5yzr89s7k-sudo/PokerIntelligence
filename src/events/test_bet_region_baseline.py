import numpy as np

import src.events.local_event_detector as local_module
from src.events.detectors.bet_region_detector import bet_region_occupancy
from src.events.detectors.frame_baseline import FrameBaseline
from src.events.local_event_detector import LocalEventDetector


RECT = {
    "x": 0,
    "y": 0,
    "width": 40,
    "height": 30,
}

GEOMETRY = {
    "bet_regions": {
        "hero": RECT,
    },
}


def bright_frame():
    frame = np.zeros((40, 50, 3), dtype=np.uint8)
    frame[0:30, 0:40] = 255
    return frame


def dark_frame():
    return np.zeros((40, 50, 3), dtype=np.uint8)


# ============================================================
# Test 1:
# Once a baseline exists, legacy brightness cannot independently
# mark an unchanged region as occupied.
# ============================================================

baseline = FrameBaseline(
    pixel_threshold=18,
    blur_size=3,
)

bright = bright_frame()
assert baseline.capture(
    "bet_region:hero",
    bright,
    RECT,
)

result = bet_region_occupancy(
    bright,
    GEOMETRY,
    baseline=baseline,
)

hero = result["hero"]

assert hero["baseline_ready"] is True
assert hero["legacy_occupied"] is True
assert hero["baseline_changed"] is False
assert hero["visual_present"] is True
assert hero["occupied"] is False


# ============================================================
# Test 2:
# A confirmed clear refreshes that seat's baseline to the current
# empty frame.
# ============================================================

original_geom = local_module.GEOM
original_functions = {
    "hero_changed": local_module.hero_changed,
    "board_changed": local_module.board_changed,
    "pot_changed": local_module.pot_changed,
    "dealer_changed": local_module.dealer_changed,
    "action_buttons_changed": local_module.action_buttons_changed,
    "action_buttons_visible": local_module.action_buttons_visible,
    "stack_change_details": local_module.stack_change_details,
    "bet_region_occupancy": local_module.bet_region_occupancy,
    "count_board_cards": local_module.count_board_cards,
    "hero_cards_visible": local_module.hero_cards_visible,
    "hero_nameplate_blinking": local_module.hero_nameplate_blinking,
}

try:
    local_module.GEOM = GEOMETRY

    local_module.hero_changed = lambda *_: False
    local_module.board_changed = lambda *_: False
    local_module.pot_changed = lambda *_: False
    local_module.dealer_changed = lambda *_: False
    local_module.action_buttons_changed = lambda *_: False
    local_module.action_buttons_visible = lambda *_: False
    local_module.stack_change_details = lambda *_: {}
    local_module.count_board_cards = lambda *_: 0
    local_module.hero_cards_visible = lambda *_: False
    local_module.hero_nameplate_blinking = lambda *_: False

    detector = LocalEventDetector()

    initial = bright_frame()
    cleared = dark_frame()

    detector.previous_frame = initial
    detector.reset_bet_region_baseline(initial)

    local_module.bet_region_occupancy = lambda *_args, **_kwargs: {
        "hero": {
            "occupied": False,
        }
    }

    detector.bet_region_tracker.initialized = True
    detector.bet_region_tracker.confirmed = {
        "hero": True,
    }
    detector.bet_region_tracker.confirm_on_seconds = 0.0
    detector.bet_region_tracker.confirm_off_seconds = 0.0

    # First reading starts the clear candidate; the second confirms it.
    detector.detect(cleared)
    changes = detector.detect(cleared)

    assert "hero" in changes.bet_region_cleared

    refreshed = detector.bet_region_baseline.difference(
        "bet_region:hero",
        cleared,
        RECT,
    )

    assert refreshed["baseline_ready"] is True
    assert refreshed["difference_ratio"] == 0.0
    assert refreshed["changed_pixels"] == 0

finally:
    local_module.GEOM = original_geom

    for name, function in original_functions.items():
        setattr(local_module, name, function)


print("Bet-region baseline regression tests passed.")
