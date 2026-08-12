from unittest.mock import patch

import numpy as np

from src.api.api_event_coordinator import (
    enrich_stack_change_measurements,
)
from src.events.local_event_detector import ChangeSet
from src.state.recent_stack_observations import (
    RecentStackObservations,
)


def make_state():
    return {
        "phase": "PREFLOP",
        "pending_stack_reads": {
            "hero": {
                "first_change_ts": 1.0,
                "last_change_ts": 1.0,
                "max_mean_diff": 5.0,
                "origin_street": "PREFLOP",
                "trigger_sources": ["bet_region_appeared"],
            }
        },
    }


def run_case(reading):
    state = make_state()
    changes = ChangeSet()
    store = RecentStackObservations()
    image = np.zeros((696, 934, 3), dtype=np.uint8)

    with (
        patch(
            "src.api.api_event_coordinator.time.time",
            return_value=10.0,
        ),
        patch(
            "src.api.api_event_coordinator._canonical_stack_values",
            return_value={"hero": 25.42},
        ),
        patch(
            "src.api.api_event_coordinator.read_stack",
            return_value=reading,
        ),
    ):
        enrich_stack_change_measurements(
            changes,
            image,
            state,
            recent_stack_observations=store,
            frame_path="/tmp/source_frame.png",
            frame_ts=9.75,
        )

    return changes, state, store


def test_trusted_unchanged_read_is_retained_without_stack_update():
    changes, state, store = run_case({
        "stack_bb": 25.42,
        "stack_text": "25.42 BB",
        "confidence": 0.98,
        "votes": 2,
        "mode": "agreement_verified",
        "raw": [],
    })

    item = store.latest("hero")

    assert item is not None
    assert item.stack_bb == 25.42
    assert item.confidence == 0.98
    assert item.votes == 2
    assert item.mode == "agreement_verified"
    assert item.frame_path == "/tmp/source_frame.png"
    assert item.ts == 9.75

    # Historical perception evidence must not manufacture a canonical
    # quantitative transition.
    assert changes.stack_changed_seats == []
    assert changes.stack_change_details == {}


def test_untrusted_read_is_not_retained():
    changes, state, store = run_case({
        "stack_bb": 25.42,
        "stack_text": "25.42 BB",
        "confidence": 0.75,
        "votes": 1,
        "mode": "plain_only",
        "raw": [],
    })

    assert store.latest("hero") is None
    assert changes.stack_changed_seats == []
    assert changes.stack_change_details == {}


def test_store_clear_is_hand_local():
    store = RecentStackObservations()

    assert store.add(
        seat="hero",
        stack_bb=25.42,
        confidence=0.98,
        votes=2,
        mode="agreement_verified",
        frame_path="/tmp/a.png",
        ts=1.0,
    )

    assert store.latest("hero") is not None

    store.clear()

    assert store.latest("hero") is None


if __name__ == "__main__":
    test_trusted_unchanged_read_is_retained_without_stack_update()
    test_untrusted_read_is_not_retained()
    test_store_clear_is_hand_local()

    print(
        "PASS recent stack wiring: existing trusted settlement OCR "
        "is retained with provenance; unchanged evidence emits no "
        "stack_update; untrusted reads are excluded; hand-local clear works"
    )
