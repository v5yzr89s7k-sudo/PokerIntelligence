from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)


def test_open_round_consumes_every_obligation():
    tracker = StreetCommitmentTracker()

    street = "PREFLOP"

    tracker.initialize_street_order(
        street,
        ["raiser", "hero"],
    )

    tracker.sync_queue(
        street,
        ["raiser", "hero"],
    )

    tracker.consume_pending_action(
        street,
        "raiser",
    )

    tracker.open_response_queue(
        street,
        aggressor="raiser",
        eligible_seats=["raiser", "hero"],
    )

    before = tracker.round_status(street)

    print()
    print("===== OPEN ROUND BEFORE =====")
    print(before)

    assert "hero" in (
        before.get("pending_to_act") or []
    ), before

    assert "hero" in (
        before.get("needs_response_from") or []
    ), before

    tracker.consume_observed_action(
        street,
        "hero",
    )

    after = tracker.round_status(street)

    print()
    print("===== OPEN ROUND AFTER =====")
    print(after)

    assert "hero" not in (
        after.get("pending_to_act") or []
    ), after

    assert "hero" not in (
        after.get("needs_response_from") or []
    ), after

    assert "hero" in (
        after.get("acted") or []
    ), after

    assert (
        after.get("players_owing_action")
        or []
    ) == [], after

    assert after["complete"] is True, after

    print(
        "PASS: one gateway consumes traversal, "
        "response, and acted-state obligations"
    )


def test_unopened_round_consumes_traversal_obligation():
    tracker = StreetCommitmentTracker()

    street = "FLOP"

    tracker.initialize_street_order(
        street,
        ["hero", "villain"],
    )

    tracker.sync_queue(
        street,
        ["hero", "villain"],
    )

    before = tracker.round_status(street)

    print()
    print("===== UNOPENED ROUND BEFORE =====")
    print(before)

    tracker.consume_observed_action(
        street,
        "hero",
    )

    after = tracker.round_status(street)

    print()
    print("===== UNOPENED ROUND AFTER =====")
    print(after)

    assert (
        after.get("players_owing_action")
        or []
    ) == ["villain"], after

    assert "hero" not in (
        after.get("pending_to_act") or []
    ), after

    assert "hero" in (
        after.get("acted") or []
    ), after

    print(
        "PASS: one gateway consumes unopened "
        "street traversal obligation"
    )


def test_gateway_is_idempotent():
    tracker = StreetCommitmentTracker()

    street = "TURN"

    tracker.initialize_street_order(
        street,
        ["hero", "villain"],
    )

    tracker.sync_queue(
        street,
        ["hero", "villain"],
    )

    tracker.consume_observed_action(
        street,
        "hero",
    )

    once = tracker.round_status(street)

    tracker.consume_observed_action(
        street,
        "hero",
    )

    twice = tracker.round_status(street)

    print()
    print("===== IDEMPOTENCE =====")
    print("once :", once)
    print("twice:", twice)

    assert (
        once.get("players_owing_action")
        == twice.get("players_owing_action")
    )

    assert (
        once.get("pending_to_act")
        == twice.get("pending_to_act")
    )

    assert (
        once.get("needs_response_from")
        == twice.get("needs_response_from")
    )

    assert (
        once.get("acted")
        == twice.get("acted")
    )

    print(
        "PASS: repeated projection of the same "
        "durable owner is idempotent"
    )


def main():
    tests = [
        test_open_round_consumes_every_obligation,
        test_unopened_round_consumes_traversal_obligation,
        test_gateway_is_idempotent,
    ]

    for test in tests:
        test()

    print()
    print(
        "PASS StreetCommitmentTracker single "
        "action-consumption gateway contract"
    )


if __name__ == "__main__":
    main()
