from pathlib import Path
from tempfile import TemporaryDirectory
import time

import cv2

import src.api.api_event_coordinator as coordinator
import src.api.api_event_state_machine as sm

from src.events.local_event_detector import LocalEventDetector
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore
from src.state.recent_stack_observations import (
    RecentStackObservations,
)


ROOT = Path(__file__).resolve().parents[2]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260808_114630"
)

SEAT = "seat_mid_right"


def load_frame(index):
    path = SESSION / f"{index:04d}_full.png"

    assert path.exists(), path

    image = cv2.imread(str(path))
    assert image is not None

    return cv2.resize(
        image,
        (934, 696),
    )


def make_unresolved_hand():
    return CanonicalHand().start_hand(
        hand_id="replay-0002-baseline-e2e",
        players=[
            {
                "seat": SEAT,
                "name": "UTG+1",
                "stack_bb": None,
                "stack_candidates": [
                    99.41,
                    55.41,
                ],
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="HJ",
        positions={
            SEAT: "UTG+1",
        },
        started_ts=1.0,
    )


def canonical_values_from_store(store):
    hand = store.load()

    return {
        seat: player.last_confirmed_stack_bb
        for seat, player in hand.players.items()
    }


def main():
    before = load_frame(12)
    after = load_frame(13)

    detector = LocalEventDetector()
    detector.previous_frame = before.copy()

    preserved_previous = (
        detector.previous_frame.copy()
    )

    changes = detector.detect(after)

    assert SEAT in changes.stack_changed_seats, (
        changes.stack_change_details
    )

    original_store = sm.CANONICAL_STORE
    old_emit = coordinator.emit
    old_canonical_values = (
        coordinator._canonical_stack_values
    )

    emitted = []
    recent = RecentStackObservations()

    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            store = CanonicalHandStore(
                json_path=root / "canonical_hand.json",
                text_path=root / "current_hand.txt",
            )

            sm.CANONICAL_STORE = store

            hand = make_unresolved_hand()
            store.save(hand)

            initial = store.load().players[SEAT]

            print("===== INITIAL CANONICAL =====")
            print(initial)

            assert initial.starting_stack_bb is None
            assert initial.current_stack_bb is None
            assert initial.last_confirmed_stack_bb is None
            assert initial.starting_stack_candidates == [
                99.41,
                55.41,
            ]

            # Coordinator reads the actual canonical store. No injected
            # 55.41 baseline is permitted.
            coordinator._canonical_stack_values = (
                lambda: canonical_values_from_store(
                    store
                )
            )

            def route_event(event):
                event = dict(event)
                event.setdefault("ts", time.time())

                emitted.append(event)

                if (
                    event.get("type")
                    == "stack_baseline_observation"
                ):
                    state = route_event.state

                    route_event.state = (
                        sm.handle_stack_baseline_observation(
                            state,
                            event,
                        )
                    )

            route_event.state = sm.default_state()
            route_event.state["phase"] = "PREFLOP"
            route_event.state[
                "canonical_snapshot_ready"
            ] = True

            coordinator.emit = route_event

            coordinator_state = {
                "phase": "PREFLOP",
                "pending_stack_reads": {},
            }

            # --------------------------------------------------------
            # Stage 1:
            # Real 12 -> 13 motion automatically observes frame 12
            # and emits 55.41 baseline evidence.
            # --------------------------------------------------------
            coordinator.enrich_stack_change_measurements(
                changes,
                after,
                coordinator_state,
                prechange_image=preserved_previous,
                prior_occupied_bet_regions=[],
                prior_commitment_seats=[],
                event_street="PREFLOP",
                recent_stack_observations=recent,
                frame_path=str(
                    SESSION / "0013_full.png"
                ),
                frame_ts=13.0,
            )

            baseline_events = [
                event
                for event in emitted
                if event.get("type")
                == "stack_baseline_observation"
                and event.get("seat") == SEAT
            ]

            assert len(baseline_events) == 1, emitted

            baseline_event = baseline_events[0]

            assert (
                baseline_event["observed_stack_bb"]
                == 55.41
            )

            assert baseline_event["votes"] >= 3
            assert "delta_bb" not in baseline_event
            assert "action" not in baseline_event

            after_baseline = store.load().players[
                SEAT
            ]

            print()
            print("===== AFTER BASELINE EVENT =====")
            print(after_baseline)

            assert (
                after_baseline.starting_stack_bb
                == 55.41
            )
            assert (
                after_baseline.current_stack_bb
                == 55.41
            )
            assert (
                after_baseline.last_confirmed_stack_bb
                == 55.41
            )

            # --------------------------------------------------------
            # Stage 2:
            # Exercise the CURRENT worker-owned stack-settlement
            # contract.
            #
            # The physical candidate already exists from frame 13.
            # CanonicalHand already owns the accepted 55.41 BB
            # baseline. A settled stack worker now returns the
            # objective 53.41 BB observation from the immutable
            # frame-13 evidence.
            # --------------------------------------------------------
            pending = coordinator_state[
                "pending_stack_reads"
            ]

            assert SEAT in pending, pending

            candidate = pending[SEAT]

            # This regression supplies recorded frame_ts=13.5 below.
            # Candidate timing must therefore remain in that same replay
            # clock domain. 12.9 -> 13.5 gives 0.60 seconds of physical
            # quiet, safely beyond STACK_SETTLE_SECONDS=0.45.
            candidate["last_change_ts"] = 12.9

            request_id = (
                "replay-0002-settled-stack"
            )

            request = {
                "request_id": request_id,
                "seat": SEAT,
                "street": "PREFLOP",
                "frame": str(
                    SESSION / "0013_full.png"
                ),
                "purpose": "settled",
                "hand_token": coordinator_state.get(
                    "hand_token"
                ),
                "queued_ts": time.time() - 0.1,
            }

            # Semantic candidate ownership and durable transport
            # ownership must refer to the same worker request.
            candidate[
                "stack_worker_request_id"
            ] = request_id

            coordinator_state.setdefault(
                "pending_stack_worker_requests",
                {},
            )[request_id] = dict(request)

            worker_item = {
                "request_id": request_id,
                "request": dict(request),
                "result": {
                    "type": "stack_result",
                    "request_id": request_id,
                    "hand_token": (
                        coordinator_state.get(
                            "hand_token"
                        )
                    ),
                    "seat": SEAT,
                    "street": "PREFLOP",
                    "frame": str(
                        SESSION / "0013_full.png"
                    ),
                    "purpose": "settled",
                    "ok": True,
                    "reading": {
                        "stack_bb": 53.41,
                        "stack_text": "53.41 BB",
                        "confidence": 0.99,
                        "votes": 3,
                        "mode": "continuity",
                        "raw": [],
                    },
                    "independent": {
                        "stack_bb": 53.41,
                        "stack_text": "53.41 BB",
                        "confidence": 0.99,
                        "votes": 3,
                        "mode": "continuity",
                        "raw": [],
                    },
                    "error": None,
                    "elapsed_ms": 1.0,
                    "ts": time.time(),
                },
            }

            quiet_changes = type(changes)()

            coordinator.process_stack_change_measurements_async(
                quiet_changes,
                after,
                coordinator_state,
                stack_worker_results={
                    SEAT: worker_item,
                },
                prior_occupied_bet_regions=set(),
                prior_commitment_seats=set(),
                response_to_aggression_seats=set(),
                event_street="PREFLOP",
                old_street_owing_seats=set(),
                frame_path=str(
                    SESSION / "0013_full.png"
                ),
                frame_ts=13.5,
                replay_records=[
                    {
                        "index": 12,
                        "ts": 12.5,
                        "frame_path": str(
                            SESSION
                            / "0012_full.png"
                        ),
                    },
                    {
                        "index": 13,
                        "ts": 13.5,
                        "frame_path": str(
                            SESSION
                            / "0013_full.png"
                        ),
                    },
                ],
            )

            stack_updates = [
                event
                for event in emitted
                if event.get("type") == "stack_update"
                and event.get("seat") == SEAT
            ]

            print()
            print("===== STACK UPDATES =====")

            for event in stack_updates:
                print(event)

            assert len(stack_updates) == 1, emitted

            update = stack_updates[0]

            assert update["previous_stack_bb"] == 55.41
            assert update["current_stack_bb"] == 53.41
            assert update["delta_bb"] == 2.0
            assert update["stack_read_mode"] == "continuity"

            # Route the objective stack update through the normal state
            # machine stack handler as well.
            route_event.state = sm.handle_stack_update(
                route_event.state,
                {
                    **update,
                    "ts": time.time(),
                },
            )

            final = store.load().players[SEAT]

            print()
            print("===== FINAL CANONICAL =====")
            print(final)

            assert final.starting_stack_bb == 55.41
            assert final.current_stack_bb == 53.41
            assert (
                final.last_confirmed_stack_bb
                == 53.41
            )

            print()
            print(
                "PASS Replay 0002 stack baseline end-to-end: "
                "unresolved [99.41, 55.41] bootstrap evidence + "
                "real frame 12->13 pixels autonomously establish "
                "55.41 -> 53.41 = 2.00 BB without injected "
                "canonical stack values or poker-semantic feedback"
            )

    finally:
        coordinator.emit = old_emit
        coordinator._canonical_stack_values = (
            old_canonical_values
        )
        sm.CANONICAL_STORE = original_store


if __name__ == "__main__":
    main()
