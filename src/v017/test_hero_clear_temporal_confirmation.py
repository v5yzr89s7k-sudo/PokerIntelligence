def clear_confirmed(sequence, required=3):
    streak = 0

    for visible in sequence:
        if not visible:
            streak += 1
        else:
            streak = 0

        if streak >= required:
            return True

    return False


def main():
    # Single transient false-negative must not authorize a new hand.
    assert not clear_confirmed(
        [True, True, False, True, True]
    )

    # Two clear frames are still insufficient.
    assert not clear_confirmed(
        [True, False, False, True]
    )

    # Three consecutive clear frames authorize transition.
    assert clear_confirmed(
        [True, False, False, False]
    )

    print("HERO CLEAR TEMPORAL CONTRACT: PASS")


if __name__ == "__main__":
    main()
