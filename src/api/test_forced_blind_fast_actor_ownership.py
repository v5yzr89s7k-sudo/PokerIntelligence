from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SB = "seat_top"
BB = "seat_upper_right"
UTG = "seat_mid_right"


def make_state():
    state = c.fresh_state()

    state["phase"] = "PREFLOP"
    state["hand_token"] = "test-hand"
    state["terminal_action_frozen"] = False

    # Authoritative preflop topology already known.
    state["positions"] = {
        SB: "SB",
        BB: "BB",
        UTG: "UTG",
    }

    # Contract state for the test:
    #
    # These seats own forced chips that existed at hand bootstrap.
    # Until their bootstrap occupancy has physically cleared,
    # an appearance must not become voluntary actor evidence.
    state["forced_blind_bootstrap_pending_clear"] = {
        SB: True,
        BB: True,
    }

    return state


def appeared(*seats):
    changes = ChangeSet()
    changes.bet_region_appeared = list(seats)
    return changes


def cleared(*seats):
    changes = ChangeSet()
    changes.bet_region_cleared = list(seats)
    return changes


def fresh_appeared(*seats):
    """
    Detector-confirmed new physical occupancy generation.

    Unlike a bare synthetic appeared edge, this carries the actual
    BetRegionStateTracker transition identity proving the immediately
    preceding confirmed state was unoccupied.
    """
    changes = ChangeSet()
    changes.bet_region_appeared = list(seats)
    changes.bet_region_transitions = {
        seat: {
            "previous_occupied": False,
            "current_occupied": True,
            "appeared": True,
            "cleared": False,
            "changed": True,
            "origin_street": "PREFLOP",
        }
        for seat in seats
    }
    return changes


def capture_events(fn):
    emitted = []
    original_emit = c.emit

    try:
        c.emit = emitted.append
        fn()
    finally:
        c.emit = original_emit

    return emitted


def actor_events(events):
    return [
        event
        for event in events
        if event.get("type") == "actor_observed"
    ]


def test_initial_small_blind_appearance_is_not_actor():
    state = make_state()

    events = capture_events(
        lambda: c.emit_fast_actor_observations(
            state,
            appeared(SB),
            street="PREFLOP",
        )
    )

    actors = actor_events(events)

    print("initial SB actors:", actors)

    assert actors == [], (
        "BUG: forced SB bootstrap occupancy became "
        "voluntary actor evidence"
    )


def test_initial_big_blind_appearance_is_not_actor():
    state = make_state()

    events = capture_events(
        lambda: c.emit_fast_actor_observations(
            state,
            appeared(BB),
            street="PREFLOP",
        )
    )

    actors = actor_events(events)

    print("initial BB actors:", actors)

    assert actors == [], (
        "BUG: forced BB bootstrap occupancy became "
        "voluntary actor evidence"
    )


def test_non_blind_appearance_still_emits_immediately():
    state = make_state()

    events = capture_events(
        lambda: c.emit_fast_actor_observations(
            state,
            appeared(UTG),
            street="PREFLOP",
        )
    )

    actors = actor_events(events)

    print("UTG actors:", actors)

    assert len(actors) == 1
    assert actors[0]["seat"] == UTG


def test_fresh_blind_generation_retires_stale_bootstrap_ownership():
    state = make_state()

    events = capture_events(
        lambda: c.emit_fast_actor_observations(
            state,
            fresh_appeared(SB),
            street="PREFLOP",
        )
    )

    actors = actor_events(events)

    print("fresh-generation SB actors:", actors)
    print(
        "remaining forced ownership:",
        state.get(
            "forced_blind_bootstrap_pending_clear"
        ),
    )

    assert len(actors) == 1, (
        "BUG: detector-confirmed fresh SB generation "
        "was suppressed as bootstrap blind occupancy"
    )

    assert actors[0]["seat"] == SB

    assert SB not in set(
        state.get(
            "forced_blind_bootstrap_pending_clear"
        )
        or []
    ), (
        "BUG: fresh SB generation did not retire stale "
        "forced-blind bootstrap ownership"
    )


def test_blind_can_act_after_physical_clear():
    state = make_state()

    # This expresses the intended ownership transition.
    #
    # Production does not implement it yet. The RED regression
    # deliberately requires the fast-actor path to consume clear
    # evidence and release bootstrap forced-chip ownership.
    capture_events(
        lambda: c.emit_fast_actor_observations(
            state,
            cleared(SB),
            street="PREFLOP",
        )
    )

    events = capture_events(
        lambda: c.emit_fast_actor_observations(
            state,
            appeared(SB),
            street="PREFLOP",
        )
    )

    actors = actor_events(events)

    print("post-clear SB actors:", actors)

    assert len(actors) == 1, (
        "BUG: SB remained suppressed after forced blind "
        "occupancy physically cleared"
    )

    assert actors[0]["seat"] == SB


def main():
    tests = [
        test_initial_small_blind_appearance_is_not_actor,
        test_initial_big_blind_appearance_is_not_actor,
        test_non_blind_appearance_still_emits_immediately,
        test_fresh_blind_generation_retires_stale_bootstrap_ownership,
        test_blind_can_act_after_physical_clear,
    ]

    for test in tests:
        print()
        print("=" * 78)
        print(test.__name__)
        print("=" * 78)

        test()

        print("PASS", test.__name__)

    print()
    print("ALL FORCED-BLIND FAST-ACTOR TESTS PASSED")


if __name__ == "__main__":
    main()
