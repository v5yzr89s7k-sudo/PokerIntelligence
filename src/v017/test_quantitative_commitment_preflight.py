from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

OBSERVER_PATH = (
    ROOT
    / "src/v017/frame_hand_observer.py"
)


def main():
    source = OBSERVER_PATH.read_text()

    print(
        "===== QUANTITATIVE COMMITMENT "
        "PREFLIGHT CONTRACT ====="
    )

    # --------------------------------------------------------
    # Required architecture.
    #
    # Temporally-settled quantitative evidence is still only
    # physical evidence.
    #
    # Before it reaches HandEngine, FrameHandObserver must
    # preflight that the normalized commitment can represent a
    # legal current-actor transition in the authoritative betting
    # state.
    #
    # HandEngine remains strict and unchanged.
    # --------------------------------------------------------

    required = (
        "def _quantitative_commitment_preflight(",
        "reason=below_current_price",
        "all_in_confirmed",
    )

    missing = [
        token
        for token in required
        if token not in source
    ]

    assert not missing, (
        "MISSING ARCHITECTURE: settled quantitative evidence "
        "has no poker-transition preflight before HandEngine: "
        f"{missing}"
    )

    print(
        "V0.17 QUANTITATIVE COMMITMENT "
        "PREFLIGHT STRUCTURE: PASS"
    )


if __name__ == "__main__":
    main()
