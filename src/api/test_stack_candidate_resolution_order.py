from pathlib import Path


def main():
    path = Path("src/api/api_event_coordinator.py")
    text = path.read_text()

    anchor = 'reason="validated_stack_transition"'

    if anchor not in text:
        raise AssertionError(
            "validated stack candidate closure anchor missing"
        )

    close_index = text.index(anchor)

    window_start = max(
        0,
        text.rfind(
            "settled_details[seat] = measurement",
            0,
            close_index,
        ),
    )

    block = text[window_start:close_index]

    stack_update_index = block.find(
        '"type": "stack_update"'
    )

    if stack_update_index < 0:
        raise AssertionError(
            "validated transition does not publish stack_update "
            "before candidate resolution"
        )

    close_call_index = block.find(
        "close_pending_stack_candidate("
    )

    # The actual close call begins immediately before the reason anchor,
    # and must occur after stack_update publication.
    if close_call_index >= 0:
        assert stack_update_index < close_call_index

    # Protect the state-machine side of the contract too:
    # closure is what releases preserved chronology.
    sm = Path(
        "src/api/api_event_state_machine.py"
    ).read_text()

    start = sm.index(
        "def handle_stack_candidate_closed"
    )
    end = sm.index(
        "def handle_actor_observed",
        start,
    )
    handler = sm[start:end]

    assert "unresolved_stack_candidates" in handler
    assert "replay_pending_actor_observations(" in handler

    print(
        "PASS stack candidate resolution order: "
        "validated stack_update is published before "
        "candidate closure releases preserved chronology"
    )


if __name__ == "__main__":
    main()
