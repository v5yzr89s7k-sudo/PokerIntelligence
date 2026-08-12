from src.state.boundary_stack_observation import (
    BoundaryStackObservation,
)


def test_decrease_is_objective_evidence():
    obs = BoundaryStackObservation(
        street="PREFLOP",
        seat="seat_upper_right",
        previous_stack_bb=50.0,
        observed_stack_bb=43.0,
        confidence=0.98,
        votes=2,
        mode="agreement_verified",
        frame_path="boundary.png",
        ts=10.0,
    )

    assert obs.delta_bb == 7.0
    assert obs.stack_decreased is True
    assert obs.stack_unchanged is False

    item = obs.to_dict()

    assert item["street"] == "PREFLOP"
    assert item["seat"] == "seat_upper_right"
    assert item["delta_bb"] == 7.0
    assert item["stack_decreased"] is True


def test_unchanged_stack_is_preserved_as_evidence():
    obs = BoundaryStackObservation(
        street="FLOP",
        seat="seat_top",
        previous_stack_bb=43.0,
        observed_stack_bb=43.0,
        confidence=0.98,
        votes=2,
        mode="agreement_verified",
    )

    assert obs.delta_bb == 0.0
    assert obs.stack_decreased is False
    assert obs.stack_unchanged is True


def test_missing_observation_does_not_invent_delta():
    obs = BoundaryStackObservation(
        street="TURN",
        seat="hero",
        previous_stack_bb=31.5,
        observed_stack_bb=None,
        confidence=0.0,
        votes=0,
        mode="no_read",
    )

    assert obs.delta_bb is None
    assert obs.stack_decreased is False
    assert obs.stack_unchanged is False


def test_missing_baseline_does_not_invent_delta():
    obs = BoundaryStackObservation(
        street="PREFLOP",
        seat="seat_mid_left",
        previous_stack_bb=None,
        observed_stack_bb=80.0,
        confidence=0.98,
        votes=2,
        mode="agreement_verified",
    )

    assert obs.delta_bb is None
    assert obs.stack_decreased is False
    assert obs.stack_unchanged is False


def test_serialization_contains_reader_provenance():
    obs = BoundaryStackObservation(
        street="RIVER",
        seat="seat_lower_right",
        previous_stack_bb=20.0,
        observed_stack_bb=15.5,
        confidence=0.50,
        votes=1,
        mode="segmentation_disagreement",
        frame_path="/tmp/frame.png",
        ts=123.45,
    )

    item = obs.to_dict()

    assert item["confidence"] == 0.50
    assert item["votes"] == 1
    assert item["mode"] == "segmentation_disagreement"
    assert item["frame_path"] == "/tmp/frame.png"
    assert item["ts"] == 123.45
    assert item["delta_bb"] == 4.5


if __name__ == "__main__":
    tests = [
        test_decrease_is_objective_evidence,
        test_unchanged_stack_is_preserved_as_evidence,
        test_missing_observation_does_not_invent_delta,
        test_missing_baseline_does_not_invent_delta,
        test_serialization_contains_reader_provenance,
    ]

    for test in tests:
        test()

    print(
        "PASS boundary stack observation: "
        "objective street-boundary stack evidence is represented "
        "without canonical mutation or poker-semantic inference"
    )
