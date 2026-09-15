from pathlib import Path


def main():
    path = Path(
        "src/api/api_event_coordinator.py"
    )

    lines = path.read_text().splitlines()

    detector = next(
        i
        for i, line in enumerate(lines)
        if "changes = local_detector.detect(img)" in line
    )

    hero_calls = [
        i
        for i, line in enumerate(lines)
        if (
            "state = maybe_read_hero(" in line
            and i > detector
        )
    ]

    assert hero_calls, (
        "maybe_read_hero call after detector not found"
    )

    hero = hero_calls[0]

    # These are representative semantic/observer stages that must not
    # precede Hero acquisition ownership for the current frame.
    semantic_markers = (
        "emit_fast_actor_observations(",
        "process_current_frame_physical_card_ownership(",
        "process_stack_change_measurements_async(",
        "runtime.observer.ingest_changes(",
        "runtime.action_episode_manager",
        "inference_engine",
    )

    blockers = []

    for i in range(
        detector + 1,
        hero,
    ):
        line = lines[i]

        if any(
            marker in line
            for marker in semantic_markers
        ):
            blockers.append(
                (i + 1, line.strip())
            )

    print(
        "detector_line=",
        detector + 1,
    )

    print(
        "hero_line=",
        hero + 1,
    )

    print(
        "distance_lines=",
        hero - detector,
    )

    print()

    print(
        "semantic_stages_before_hero="
    )

    for item in blockers:
        print(
            " ",
            item,
        )

    assert not blockers, (
        "RED: current-frame Hero acquisition is delayed "
        "behind semantic/action/stack processing"
    )

    # Keep the fast path physically close enough that future refactors
    # cannot silently push it back behind expensive semantics again.
    assert hero - detector <= 40, (
        "RED: Hero acquisition is not on the immediate "
        "post-perception fast path"
    )

    print()
    print(
        "PASS: Hero acquisition owns current-frame "
        "visibility before semantic processing"
    )


if __name__ == "__main__":
    main()
