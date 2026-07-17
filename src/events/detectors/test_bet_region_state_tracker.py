from src.events.detectors.bet_region_state_tracker import (
    BetRegionStateTracker,
)


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def occupancy(hero=False):
    return {
        "hero": {
            "occupied": hero,
            "foreground_area": 100 if hero else 0,
        },
    }


def test_first_frame_is_baseline_only():
    clock = FakeClock()
    tracker = BetRegionStateTracker(clock=clock)

    result = tracker.update(occupancy(hero=True))

    assert result["hero"]["appeared"] is False
    assert result["hero"]["cleared"] is False
    assert result["hero"]["occupied"] is True


def test_short_on_flicker_is_not_confirmed():
    clock = FakeClock()
    tracker = BetRegionStateTracker(clock=clock)

    tracker.update(occupancy(hero=False))

    candidate = tracker.update(occupancy(hero=True))
    assert candidate["hero"]["appeared"] is False
    assert candidate["hero"]["occupied"] is False
    assert candidate["hero"]["raw_occupied"] is True

    clock.advance(0.05)
    result = tracker.update(occupancy(hero=False))

    assert result["hero"]["appeared"] is False
    assert result["hero"]["occupied"] is False


def test_persistent_on_becomes_confirmed():
    clock = FakeClock()
    tracker = BetRegionStateTracker(clock=clock)

    tracker.update(occupancy(hero=False))
    tracker.update(occupancy(hero=True))

    clock.advance(0.16)
    result = tracker.update(occupancy(hero=True))

    assert result["hero"]["appeared"] is True
    assert result["hero"]["occupied"] is True
    assert result["hero"]["raw_occupied"] is True


def test_short_off_flicker_is_not_confirmed():
    clock = FakeClock()
    tracker = BetRegionStateTracker(clock=clock)

    tracker.update(occupancy(hero=True))

    candidate = tracker.update(occupancy(hero=False))
    assert candidate["hero"]["cleared"] is False
    assert candidate["hero"]["occupied"] is True
    assert candidate["hero"]["raw_occupied"] is False

    clock.advance(0.05)
    result = tracker.update(occupancy(hero=True))

    assert result["hero"]["cleared"] is False
    assert result["hero"]["occupied"] is True


def test_persistent_off_becomes_confirmed_clear():
    clock = FakeClock()
    tracker = BetRegionStateTracker(clock=clock)

    tracker.update(occupancy(hero=True))
    tracker.update(occupancy(hero=False))

    clock.advance(0.16)
    result = tracker.update(occupancy(hero=False))

    assert result["hero"]["cleared"] is True
    assert result["hero"]["occupied"] is False


def test_occupied_duration_is_recorded():
    clock = FakeClock()
    tracker = BetRegionStateTracker(clock=clock)

    tracker.update(occupancy(hero=False))
    tracker.update(occupancy(hero=True))

    clock.advance(0.16)
    tracker.update(occupancy(hero=True))

    clock.advance(0.40)
    result = tracker.update(occupancy(hero=True))

    assert result["hero"]["occupied_duration_ms"] >= 400.0


if __name__ == "__main__":
    tests = [
        test_first_frame_is_baseline_only,
        test_short_on_flicker_is_not_confirmed,
        test_persistent_on_becomes_confirmed,
        test_short_off_flicker_is_not_confirmed,
        test_persistent_off_becomes_confirmed_clear,
        test_occupied_duration_is_recorded,
    ]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print("ALL BET REGION DEBOUNCE TESTS PASSED")
