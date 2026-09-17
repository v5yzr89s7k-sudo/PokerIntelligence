from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

observer = (
    ROOT
    / "src/v017/frame_hand_observer.py"
).read_text()

runner = (
    ROOT
    / "src/v017/run_live_observer.py"
).read_text()


def main():
    required_observer = (
        "bet_region_occupancy",
        "BetRegionStateTracker",
        "FrameBaseline",
        "self.confirmed_bet_regions",
        "def observe_bet_regions(",
        "self.observe_bet_regions(",
    )

    for token in required_observer:
        assert token in observer, token

    required_runner = (
        "has_commitment_evidence",
        "observer.confirmed_bet_regions",
        "all_in_confirmed",
        "settlement_gate.observe(",
    )

    for token in required_runner:
        assert token in runner, token

    print(
        "V0.17 LIVE BET-REGION SETTLEMENT WIRING: PASS"
    )


if __name__ == "__main__":
    main()
