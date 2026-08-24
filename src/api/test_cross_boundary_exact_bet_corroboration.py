import json
import tempfile
from pathlib import Path

from src.api import api_event_coordinator as coord
from src.events.local_event_detector import ChangeSet


HAND = "cross-boundary-hand"
SEAT = "seat_lower_left"
REQUEST = "flop-bet-request"


def read_events(path):
    if not path.exists():
        return []

    result = []

    for raw in path.read_text().splitlines():
        if not raw.strip():
            continue

        result.append(
            json.loads(raw)
        )

    return result


def make_deferred(
    *,
    bet_bb,
    street="FLOP",
):
    return {
        REQUEST: {
            "request": {
                "hand_token": HAND,
                "seat": SEAT,
                "street": street,
                "frame": "frame.png",
                "source": "transition",
                "queued_ts": 10.0,
            },
            "result": {
                "type": "bet_amount_result",
                "request_id": REQUEST,
                "hand_token": HAND,
                "seat": SEAT,
                "street": street,
                "frame": "frame.png",
                "ok": True,
                "bet_bb": bet_bb,
                "elapsed_ms": 100.0,
                "ts": 11.0,
            },
            "bet_bb": bet_bb,
            "seat": SEAT,
            "street": street,
        }
    }


def make_changes(
    *,
    delta_bb,
    origin_street="PREFLOP",
    confidence=0.98,
    mode="independent_confirmed",
):
    changes = ChangeSet()

    changes.stack_changed_seats = [
        SEAT
    ]

    changes.stack_change_details = {
        SEAT: {
            "changed": True,
            "previous_stack_bb": 47.57,
            "current_stack_bb": round(
                47.57 - delta_bb,
                2,
            ),
            "delta_bb": delta_bb,
            "origin_street": origin_street,
            "stack_read_confidence": confidence,
            "stack_read_mode": mode,
        }
    }

    return changes


def event_types(events):
    return [
        item.get("type")
        for item in events
    ]


def main():
    old_event_log = coord.EVENT_LOG

    try:
        with tempfile.TemporaryDirectory() as tmp:
            event_log = (
                Path(tmp)
                / "api_events.jsonl"
            )

            coord.EVENT_LOG = event_log
            event_log.write_text("")

            # ====================================================
            # CONTRACT 1
            #
            # Candidate history remains PREFLOP.
            #
            # Independent FLOP absolute-bet evidence says 3.37.
            # Independently confirmed stack transition says 3.37.
            #
            # Exact quantitative agreement must be sufficient to
            # corroborate the deferred FLOP evidence without
            # rewriting the historical stack candidate street.
            # ====================================================

            state = coord.fresh_state()
            state["hand_token"] = HAND
            state["phase"] = "FLOP"

            state[
                "deferred_bet_amount_results"
            ] = make_deferred(
                bet_bb=3.37,
            )

            changes = make_changes(
                delta_bb=3.37,
                origin_street="PREFLOP",
            )

            state = (
                coord
                .release_corroborated_bet_amount_results(
                    state,
                    changes,
                )
            )

            events = read_events(
                event_log
            )

            print(
                "exact-match events:",
                json.dumps(
                    events,
                    indent=2,
                ),
            )

            print(
                "exact-match deferred:",
                json.dumps(
                    state.get(
                        "deferred_bet_amount_results"
                    ),
                    indent=2,
                ),
            )

            types = event_types(
                events
            )

            assert (
                "bet_amount_observation"
                in types
            ), (
                "REGRESSION REPRODUCED: independently "
                "confirmed stack delta exactly matches "
                "same-seat deferred FLOP bet amount, but "
                "corroboration is rejected solely because "
                "the older physical stack candidate retained "
                "PREFLOP origin_street"
            )

            assert (
                "provisional_bet_closed"
                in types
            )

            bet_event = next(
                item
                for item in events
                if (
                    item.get("type")
                    == "bet_amount_observation"
                )
            )

            close_event = next(
                item
                for item in events
                if (
                    item.get("type")
                    == "provisional_bet_closed"
                )
            )

            assert bet_event["street"] == "FLOP"
            assert bet_event["bet_bb"] == 3.37
            assert (
                close_event["street"]
                == "FLOP"
            )
            assert (
                close_event["reason"]
                == "corroborated"
            )

            assert (
                state[
                    "deferred_bet_amount_results"
                ]
                == {}
            )

            # ====================================================
            # CONTRACT 2 — NEGATIVE CONTROL
            #
            # Cross-street attribution alone is NOT enough.
            # A materially different stack delta must NOT release
            # the FLOP provisional evidence.
            # ====================================================

            event_log.write_text("")

            state = coord.fresh_state()
            state["hand_token"] = HAND
            state["phase"] = "FLOP"

            state[
                "deferred_bet_amount_results"
            ] = make_deferred(
                bet_bb=3.37,
            )

            changes = make_changes(
                delta_bb=1.00,
                origin_street="PREFLOP",
            )

            state = (
                coord
                .release_corroborated_bet_amount_results(
                    state,
                    changes,
                )
            )

            mismatch_events = read_events(
                event_log
            )

            print(
                "mismatch events:",
                json.dumps(
                    mismatch_events,
                    indent=2,
                ),
            )

            assert not any(
                item.get("type")
                == "bet_amount_observation"
                for item in mismatch_events
            )

            assert (
                REQUEST
                in state[
                    "deferred_bet_amount_results"
                ]
            )

            # ====================================================
            # CONTRACT 3 — WEAK CROSS-STREET NEGATIVE CONTROL
            #
            # Exact rounded equality is not sufficient by itself.
            # Weak continuity evidence must remain blocked across
            # a street mismatch.
            # ====================================================

            event_log.write_text("")

            state = coord.fresh_state()
            state["hand_token"] = HAND
            state["phase"] = "FLOP"

            state[
                "deferred_bet_amount_results"
            ] = make_deferred(
                bet_bb=3.37,
            )

            changes = make_changes(
                delta_bb=3.37,
                origin_street="PREFLOP",
                confidence=0.80,
                mode="continuity",
            )

            state = (
                coord
                .release_corroborated_bet_amount_results(
                    state,
                    changes,
                )
            )

            weak_events = read_events(
                event_log
            )

            print(
                "weak exact-match events:",
                json.dumps(
                    weak_events,
                    indent=2,
                ),
            )

            assert not any(
                item.get("type")
                == "bet_amount_observation"
                for item in weak_events
            )

            assert (
                REQUEST
                in state[
                    "deferred_bet_amount_results"
                ]
            )

            # ====================================================
            # CONTRACT 4 — SAME-STREET EXISTING BEHAVIOR
            #
            # Existing same-street positive corroboration must
            # remain valid regardless of this new boundary rule.
            # ====================================================

            event_log.write_text("")

            state = coord.fresh_state()
            state["hand_token"] = HAND
            state["phase"] = "FLOP"

            state[
                "deferred_bet_amount_results"
            ] = make_deferred(
                bet_bb=2.50,
            )

            changes = make_changes(
                delta_bb=2.50,
                origin_street="FLOP",
            )

            state = (
                coord
                .release_corroborated_bet_amount_results(
                    state,
                    changes,
                )
            )

            same_events = read_events(
                event_log
            )

            assert [
                item.get("type")
                for item in same_events
            ] == [
                "bet_amount_observation",
                "provisional_bet_closed",
            ]

            print(
                "PASS cross-boundary quantitative "
                "corroboration contract"
            )

    finally:
        coord.EVENT_LOG = old_event_log


if __name__ == "__main__":
    main()
