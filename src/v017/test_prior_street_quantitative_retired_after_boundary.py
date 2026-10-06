from src.v017.frame_hand_observer import FrameHandObserver


def quantitative(frame, seat, value):
    return {
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "frame": frame,
        "seat": seat,
        "prior_value": 50.0,
        "resolved_value": value,
        "physical_delta_bb": 2.0,
    }


def main():
    observer = object.__new__(FrameHandObserver)

    observer.pending_quantitative_evidence = [
        quantitative(10, "villain", 48.0),
    ]

    # Simulate successful crossing of a physical FLOP boundary at 13.
    # Evidence from frame 10 belongs exclusively to the closed
    # predecessor street and must not remain replayable afterward.
    boundary_frame = 13

    assert observer.pending_quantitative_evidence, (
        "test setup failed"
    )

    # Expected production helper.
    observer.retire_quantitative_evidence_before_boundary(
        boundary_frame
    )

    assert observer.pending_quantitative_evidence == [], (
        "RED: prior-street retained quantitative evidence "
        "survived successful street transition"
    )

    print(
        "PRIOR-STREET RETAINED QUANTITATIVE RETIRED: PASS"
    )


if __name__ == "__main__":
    main()
