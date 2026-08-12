from src.state.recent_stack_observations import (
    RecentStackObservations,
)


def trusted(
    store,
    seat,
    value,
    ts,
    *,
    confidence=0.98,
    votes=2,
    frame=None,
):
    return store.add(
        seat=seat,
        stack_bb=value,
        confidence=confidence,
        votes=votes,
        mode="agreement_verified",
        frame_path=frame or f"/tmp/{seat}_{ts}.png",
        ts=ts,
    )


def test_untrusted_reads_are_rejected():
    store = RecentStackObservations()

    assert not trusted(
        store,
        "seat_top",
        28.36,
        1.0,
        confidence=0.75,
        votes=1,
    )

    assert store.history("seat_top") == []


def test_history_is_bounded():
    store = RecentStackObservations(max_per_seat=3)

    for i in range(5):
        assert trusted(
            store,
            "seat_top",
            30.0 - i,
            float(i),
        )

    history = store.history("seat_top")

    assert len(history) == 3
    assert [x.stack_bb for x in history] == [
        28.0,
        27.0,
        26.0,
    ]


def test_duplicate_frame_is_not_double_counted():
    store = RecentStackObservations()

    assert trusted(
        store,
        "seat_top",
        28.36,
        10.0,
        frame="/tmp/frame70.png",
    )

    assert not trusted(
        store,
        "seat_top",
        28.36,
        10.0,
        frame="/tmp/frame70.png",
    )

    assert len(store.history("seat_top")) == 1


def test_boundary_selection_never_uses_future_evidence():
    store = RecentStackObservations()

    trusted(store, "seat_top", 28.36, 70.0)
    trusted(store, "seat_top", 25.00, 82.0)

    selected = store.strongest_recent(
        "seat_top",
        not_after_ts=79.0,
    )

    assert selected is not None
    assert selected.stack_bb == 28.36
    assert selected.ts == 70.0


def test_replay_0002_shape_preserves_earlier_bb_evidence():
    store = RecentStackObservations(max_per_seat=8)

    # Replay 0002 shape:
    # BB has trusted evidence before the final boundary frame.
    trusted(
        store,
        "seat_top",
        28.36,
        70.0,
        frame="0070_full.png",
    )

    # Other responders have trusted evidence close to the boundary.
    for seat, value in [
        ("seat_mid_right", 93.41),
        ("seat_lower_left", 64.13),
        ("seat_mid_left", 19.82),
        ("seat_upper_left", 37.94),
    ]:
        trusted(
            store,
            seat,
            value,
            79.0,
            frame="0079_full.png",
        )

    bb = store.strongest_recent(
        "seat_top",
        not_after_ts=79.0,
        max_age_seconds=10.0,
    )

    assert bb is not None
    assert bb.stack_bb == 28.36
    assert bb.frame_path == "0070_full.png"

    assert (
        store.strongest_recent(
            "seat_mid_right",
            not_after_ts=79.0,
            max_age_seconds=10.0,
        ).stack_bb
        == 93.41
    )


def test_store_has_no_canonical_semantics():
    store = RecentStackObservations()

    trusted(
        store,
        "seat_mid_right",
        93.41,
        79.0,
    )

    payload = store.to_dict()

    text = repr(payload)

    assert "action" not in text.lower()
    assert "canonical" not in text.lower()
    assert "current_price" not in text.lower()


if __name__ == "__main__":
    tests = [
        test_untrusted_reads_are_rejected,
        test_history_is_bounded,
        test_duplicate_frame_is_not_double_counted,
        test_boundary_selection_never_uses_future_evidence,
        test_replay_0002_shape_preserves_earlier_bb_evidence,
        test_store_has_no_canonical_semantics,
    ]

    for test in tests:
        test()

    print(
        "PASS recent stack observations: "
        "trusted visual evidence is retained in bounded per-seat history "
        "without canonical or poker-semantic authority"
    )
