from pathlib import Path


def main():
    path = Path(
        "src/api/api_event_coordinator.py"
    )
    lines = path.read_text().splitlines()

    detector = next(
        i for i, line in enumerate(lines)
        if "changes = local_detector.detect(img)" in line
    )

    snapshot = next(
        i for i in range(detector, len(lines))
        if "local_hero_visible = bool(" in lines[i]
    )

    hero_assign = next(
        i for i in range(snapshot + 1, len(lines))
        if "hero_visible = bool(local_hero_visible)" in lines[i]
    )

    hero_call = next(
        i for i in range(hero_assign + 1, len(lines))
        if "state = maybe_read_hero(" in lines[i]
    )

    snapshot_region = "\n".join(
        lines[snapshot:snapshot + 8]
    )

    call_region = "\n".join(
        lines[hero_assign:hero_call + 10]
    )

    whole_file = "\n".join(lines)

    print("detector_line =", detector + 1)
    print("snapshot_line =", snapshot + 1)
    print("snapshot_consumer_line =", hero_assign + 1)
    print("hero_call_line =", hero_call + 1)

    print()
    print("===== CURRENT-FRAME SNAPSHOT =====")
    print(snapshot_region)

    print()
    print("===== HERO ACQUISITION INPUT =====")
    print(call_region)

    assert (
        "hero_visible = changes.hero_cards_visible"
        not in whole_file
    ), (
        "late narrow Hero visibility reread still exists"
    )

    assert (
        "hero_visible = bool(local_hero_visible)"
        in lines[hero_assign]
    ), (
        "Hero acquisition does not consume the "
        "current-frame visibility snapshot"
    )

    assert (
        "hero_visible," in call_region
    ), (
        "maybe_read_hero does not receive the "
        "snapshot-derived Hero visibility"
    )

    assert (
        snapshot < hero_assign < hero_call
    ), (
        "Hero visibility snapshot ownership ordering is invalid"
    )

    print()
    print(
        "PASS: Hero acquisition consumes immutable "
        "current-frame visibility snapshot"
    )


if __name__ == "__main__":
    main()
