from src.v017.run_live_observer import (
    FrameTransactionResult,
)


def main():
    source = {
        "type": "TEST_EVENT",
        "seat": "hero",
    }

    result = FrameTransactionResult(
        "CONTINUE",
        [source],
    )

    assert result.outcome == "CONTINUE"
    assert result.events == (
        {
            "type": "TEST_EVENT",
            "seat": "hero",
        },
    )

    # Result owns a detached diagnostic copy.
    source["seat"] = "changed"
    assert result.events[0]["seat"] == "hero"

    print("TRANSACTION OUTCOME EXPOSED: PASS")
    print("PHYSICAL EVENTS EXPOSED: PASS")
    print("DIAGNOSTIC COPY DETACHED: PASS")
    print("V0.17 FRAME TRANSACTION RESULT: PASS")


if __name__ == "__main__":
    main()
