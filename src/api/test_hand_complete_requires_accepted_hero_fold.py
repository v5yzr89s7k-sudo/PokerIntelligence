import src.api.api_event_state_machine as sm


class DummyCanonical:
    def __init__(self):
        self.finished = None

    def add_pot_result(self, **kwargs):
        pass

    def finish(self, *, result, ended_ts):
        self.finished = (result, ended_ts)


class DummyStore:
    def archive(self):
        return "/tmp/synthetic-terminal-archive.txt"


def live_state():
    state = sm.default_state()
    state["phase"] = "TURN"
    state["canonical_snapshot_ready"] = True
    state["hand_token"] = "synthetic-hand"
    return state


def main():
    # --------------------------------------------------------
    # 1. No accepted canonical fold:
    #    fold-derived completion must be rejected.
    # --------------------------------------------------------
    state = live_state()

    state = sm.handle_hand_complete(
        state,
        {
            "type": "hand_complete",
            "result": "Hero folded on river",
            "ts": 10.0,
        },
    )

    assert state["phase"] == "TURN", state
    assert not state.get("hand_complete"), state

    # --------------------------------------------------------
    # 2. Accepted fold exists, but owns a different street:
    #    completion must still be rejected.
    # --------------------------------------------------------
    state = live_state()
    state["accepted_hero_fold_street"] = "TURN"

    state = sm.handle_hand_complete(
        state,
        {
            "type": "hand_complete",
            "result": "Hero folded on river",
            "ts": 11.0,
        },
    )

    assert state["phase"] == "TURN", state
    assert not state.get("hand_complete"), state

    # --------------------------------------------------------
    # 3. Accepted fold owns the claimed street:
    #    existing terminal path remains authorized.
    #
    #    Stub persistence only; we are testing causal ownership,
    #    not CanonicalStore I/O.
    # --------------------------------------------------------
    state = live_state()
    state["phase"] = "RIVER"
    state["accepted_hero_fold_street"] = "RIVER"

    dummy = DummyCanonical()

    old_load = sm.canonical_load
    old_save = sm.canonical_save
    old_store = sm.CANONICAL_STORE
    old_summary = sm.write_validation_summary
    old_reset = sm.reset_tracker

    try:
        sm.canonical_load = lambda: dummy
        sm.canonical_save = lambda canonical: None
        sm.CANONICAL_STORE = DummyStore()
        sm.write_validation_summary = (
            lambda canonical, archived: None
        )
        sm.reset_tracker = lambda: None

        state = sm.handle_hand_complete(
            state,
            {
                "type": "hand_complete",
                "result": "Hero folded on river",
                "ts": 12.0,
            },
        )

    finally:
        sm.canonical_load = old_load
        sm.canonical_save = old_save
        sm.CANONICAL_STORE = old_store
        sm.write_validation_summary = old_summary
        sm.reset_tracker = old_reset

    assert state["phase"] == "WAITING", state
    assert dummy.finished == (
        "Hero folded on river",
        12.0,
    ), dummy.finished

    print(
        "PASS: fold-derived hand_complete requires "
        "accepted same-street canonical Hero fold"
    )


if __name__ == "__main__":
    main()
