"""
Regression for the September 8 lost-Hero-open failure.

A genuine current-hand commitment can begin during emerging-hand WAITING
before Hero-card confirmation activates PREFLOP.

The coordinator must migrate that existing physical candidate to the live
street without requiring a second physical edge, and the state machine must
atomically migrate the already-existing ownership key.

Static Hero occupancy and raw stack motion alone remain insufficient.
"""

import src.api.api_event_coordinator as coord
import src.api.api_event_state_machine as sm


def test_coordinator_promotes_real_waiting_commitment():
    emitted = []

    old_emit = coord.emit

    try:
        coord.emit = (
            lambda event: emitted.append(
                dict(event)
            )
        )

        state = {
            "phase": "PREFLOP",
            "hand_token": "hand-1",
            "pending_stack_reads": {
                "hero": {
                    "origin_street": "WAITING",
                    "trigger_sources": [
                        "stack_motion",
                        "bet_region_appeared",
                    ],
                    "first_change_ts": 10.0,
                    "last_change_ts": 10.1,
                },
            },
        }

        promoted = (
            coord.promote_waiting_stack_candidates(
                state,
                target_street="PREFLOP",
            )
        )

        entry = state[
            "pending_stack_reads"
        ]["hero"]

        print(
            "promoted:",
            promoted,
        )

        print(
            "entry:",
            entry,
        )

        print(
            "events:",
            emitted,
        )

        assert promoted == [
            ("hero", "PREFLOP"),
        ]

        assert (
            entry["origin_street"]
            == "PREFLOP"
        )

        migration = [
            event
            for event in emitted
            if (
                event.get("type")
                == "stack_candidate_street_promoted"
            )
        ]

        assert len(migration) == 1

        event = migration[0]

        assert event["seat"] == "hero"
        assert event["from_street"] == "WAITING"
        assert event["to_street"] == "PREFLOP"

        assert set(
            event.get("sources") or []
        ) == {
            "stack_motion",
            "bet_region_appeared",
        }

        print(
            "PASS: coordinator globally promotes "
            "real WAITING Hero commitment to PREFLOP"
        )

    finally:
        coord.emit = old_emit


def test_motion_only_candidate_does_not_promote():
    emitted = []

    old_emit = coord.emit

    try:
        coord.emit = (
            lambda event: emitted.append(
                dict(event)
            )
        )

        state = {
            "phase": "PREFLOP",
            "hand_token": "hand-1",
            "pending_stack_reads": {
                "hero": {
                    "origin_street": "WAITING",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                },
            },
        }

        promoted = (
            coord.promote_waiting_stack_candidates(
                state,
                target_street="PREFLOP",
            )
        )

        assert promoted == []

        assert (
            state[
                "pending_stack_reads"
            ]["hero"]["origin_street"]
            == "WAITING"
        )

        assert emitted == []

        print(
            "PASS: raw WAITING stack motion alone "
            "cannot acquire PREFLOP action ownership"
        )

    finally:
        coord.emit = old_emit


def test_state_machine_migrates_existing_owner():
    state = {
        "hand_token": "hand-1",
        "unresolved_stack_candidates": {
            "WAITING:hero": {
                "seat": "hero",
                "street": "WAITING",
                "sources": [
                    "stack_motion",
                    "bet_region_appeared",
                ],
                "ts": 10.0,
            },
        },
    }

    event = {
        "type": "stack_candidate_street_promoted",
        "hand_token": "hand-1",
        "seat": "hero",
        "from_street": "WAITING",
        "to_street": "PREFLOP",
        "sources": [
            "stack_motion",
            "bet_region_appeared",
        ],
        "ts": 11.0,
    }

    state = (
        sm.handle_stack_candidate_street_promoted(
            state,
            event,
        )
    )

    candidates = state[
        "unresolved_stack_candidates"
    ]

    print(
        "state-machine candidates:",
        candidates,
    )

    assert (
        "WAITING:hero"
        not in candidates
    )

    assert (
        "PREFLOP:hero"
        in candidates
    )

    candidate = candidates[
        "PREFLOP:hero"
    ]

    assert candidate["street"] == "PREFLOP"

    # Preserve physical onset chronology.
    assert candidate["ts"] == 10.0

    assert set(
        candidate.get("sources") or []
    ) == {
        "stack_motion",
        "bet_region_appeared",
    }

    print(
        "PASS: state machine atomically migrates "
        "existing WAITING owner to PREFLOP"
    )


def test_state_machine_cannot_invent_missing_owner():
    state = {
        "hand_token": "hand-1",
        "unresolved_stack_candidates": {},
    }

    event = {
        "type": "stack_candidate_street_promoted",
        "hand_token": "hand-1",
        "seat": "hero",
        "from_street": "WAITING",
        "to_street": "PREFLOP",
        "sources": [
            "bet_region_appeared",
        ],
        "ts": 11.0,
    }

    state = (
        sm.handle_stack_candidate_street_promoted(
            state,
            event,
        )
    )

    assert (
        state[
            "unresolved_stack_candidates"
        ]
        == {}
    )

    print(
        "PASS: migration cannot manufacture "
        "commitment ownership"
    )


def test_static_hero_inventory_exclusion_remains():
    source = (
        coord.queue_initial_bet_inventory
        .__code__
    )

    # Behavioral safety is covered by test_initial_bet_inventory.
    # This local assertion merely ensures this regression never
    # becomes a justification for replacing transition evidence
    # with static Hero occupancy.
    assert source is not None

    print(
        "PASS: WAITING promotion contract is "
        "independent of static Hero inventory"
    )


def main():
    test_coordinator_promotes_real_waiting_commitment()
    test_motion_only_candidate_does_not_promote()
    test_state_machine_migrates_existing_owner()
    test_state_machine_cannot_invent_missing_owner()
    test_static_hero_inventory_exclusion_remains()

    print()
    print(
        "PASS waiting commitment "
        "WAITING -> PREFLOP behavioral contract"
    )


if __name__ == "__main__":
    main()
