from pathlib import Path


def main():
    p = Path(
        "src/api/api_event_coordinator.py"
    )

    lines = p.read_text().splitlines()

    detector = next(
        i for i, line in enumerate(lines)
        if "changes = local_detector.detect(img)" in line
    )

    hero_call = next(
        i for i, line in enumerate(lines)
        if (
            "state = maybe_read_hero(" in line
            and i > detector
        )
    )

    provisional = next(
        (
            i
            for i in range(
                detector + 1,
                hero_call,
            )
            if (
                'provisional_hand_token = uuid.uuid4().hex'
                in lines[i]
            )
        ),
        None,
    )

    hand_token_write = next(
        (
            i
            for i in range(
                detector + 1,
                hero_call,
            )
            if (
                'state["hand_token"] = provisional_hand_token'
                in lines[i]
            )
        ),
        None,
    )

    print(
        "detector_line=",
        detector + 1,
    )

    print(
        "hero_confirmation_line=",
        hero_call + 1,
    )

    print(
        "provisional_token_line=",
        (
            provisional + 1
            if provisional is not None
            else None
        ),
    )

    print(
        "preconfirmation_hand_token_write=",
        (
            hand_token_write + 1
            if hand_token_write is not None
            else None
        ),
    )

    assert provisional is None, (
        "RED: raw Hero visibility creates provisional "
        "hand ownership before Hero confirmation"
    )

    assert hand_token_write is None, (
        "RED: hand_token is written before "
        "two-frame Hero confirmation"
    )

    print()
    print(
        "PASS: unconfirmed Hero visibility has no "
        "hand-start authority"
    )


if __name__ == "__main__":
    main()
