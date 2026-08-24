import json
import tempfile
from pathlib import Path

from src.api import api_event_coordinator as coord
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_left"
HAND = "hand-current"
STREET = "FLOP"


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


def transition_request(request_id, hand_token=HAND):
    return {
        "seat": SEAT,
        "street": STREET,
        "frame": "0091_full.png",
        "source": "transition",
        "queued_ts": 1.0,
        "hand_token": hand_token,
        "request_id": request_id,
    }


def transition_result(request_id, hand_token=HAND):
    return {
        "type": "bet_amount_result",
        "request_id": request_id,
        "hand_token": hand_token,
        "seat": SEAT,
        "street": STREET,
        "frame": "0091_full.png",
        "ok": True,
        "bet_bb": 3.25,
        "elapsed_ms": 100.0,
        "ts": 2.0,
    }


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
            # A valid transition result that becomes deferred must
            # explicitly open independent provisional ownership.
            # ====================================================

            state = coord.fresh_state()
            state["hand_token"] = HAND
            state["phase"] = STREET

            request_id = "transition-open"

            state[
                "pending_bet_amount_requests"
            ] = {
                request_id: transition_request(
                    request_id
                )
            }

            state, applied = (
                coord.apply_bet_amount_result(
                    state,
                    transition_result(
                        request_id
                    ),
                )
            )

            assert applied

            assert (
                request_id
                in state[
                    "deferred_bet_amount_results"
                ]
            )

            events = read_events(
                event_log
            )

            print(
                "after defer:",
                json.dumps(
                    events,
                    indent=2,
                ),
            )

            opened = [
                item
                for item in events
                if (
                    item.get("type")
                    == "provisional_bet_opened"
                )
            ]

            assert len(opened) == 1, (
                "REGRESSION REPRODUCED: transition bet "
                "evidence entered deferred ownership but "
                "no provisional_bet_opened event was emitted"
            )

            assert opened[0]["seat"] == SEAT
            assert opened[0]["street"] == STREET
            assert opened[0]["hand_token"] == HAND
            assert (
                opened[0]["source_request_id"]
                == request_id
            )

            # ====================================================
            # CONTRACT 2
            # Positive same-street stack corroboration publishes
            # the bet observation AND explicitly closes provisional
            # ownership.
            # ====================================================

            event_log.write_text("")

            changes = ChangeSet()
            changes.stack_changed_seats = [
                SEAT
            ]
            changes.stack_change_details = {
                SEAT: {
                    "delta_bb": 3.25,
                    "origin_street": STREET,
                }
            }

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
                "after corroboration:",
                json.dumps(
                    events,
                    indent=2,
                ),
            )

            types = event_types(
                events
            )

            assert (
                "bet_amount_observation"
                in types
            )

            assert (
                "provisional_bet_closed"
                in types
            ), (
                "REGRESSION REPRODUCED: corroborated "
                "provisional evidence was removed from "
                "coordinator state without explicitly "
                "releasing state-machine ownership"
            )

            close_index = types.index(
                "provisional_bet_closed"
            )

            observation_index = types.index(
                "bet_amount_observation"
            )

            assert (
                observation_index
                < close_index
            ), (
                "quantitative bet evidence must reach "
                "downstream state before its chronology "
                "blocker is released"
            )

            closed = events[
                close_index
            ]

            assert closed["seat"] == SEAT
            assert closed["street"] == STREET
            assert closed["hand_token"] == HAND
            assert (
                closed["source_request_id"]
                == request_id
            )
            assert (
                closed["reason"]
                == "corroborated"
            )

            assert (
                request_id
                not in state[
                    "deferred_bet_amount_results"
                ]
            )

            # ====================================================
            # CONTRACT 3
            # Stale-hand deferred evidence must be retired even if
            # there is NO current confirmed stack transition.
            #
            # Existing production currently returns early when
            # confirmed_seats is empty, so this should also be RED.
            # ====================================================

            event_log.write_text("")

            stale_request = "stale-request"

            state[
                "deferred_bet_amount_results"
            ] = {
                stale_request: {
                    "request": transition_request(
                        stale_request,
                        hand_token="old-hand",
                    ),
                    "result": transition_result(
                        stale_request,
                        hand_token="old-hand",
                    ),
                    "bet_bb": 3.25,
                    "seat": SEAT,
                    "street": STREET,
                }
            }

            empty_changes = ChangeSet()

            state = (
                coord
                .release_corroborated_bet_amount_results(
                    state,
                    empty_changes,
                )
            )

            print(
                "stale deferred after cleanup:",
                state.get(
                    "deferred_bet_amount_results"
                ),
            )

            stale_events = read_events(
                event_log
            )

            print(
                "stale cleanup events:",
                json.dumps(
                    stale_events,
                    indent=2,
                ),
            )

            assert (
                stale_request
                not in state[
                    "deferred_bet_amount_results"
                ]
            ), (
                "REGRESSION REPRODUCED: stale-hand "
                "deferred bet evidence survives forever "
                "when no confirmed stack transition occurs"
            )

            stale_closed = [
                item
                for item in stale_events
                if (
                    item.get("type")
                    == "provisional_bet_closed"
                )
            ]

            assert len(stale_closed) == 1

            assert (
                stale_closed[0]["reason"]
                == "hand_changed"
            )

            # ====================================================
            # CONTRACT 4
            # No negative retirement policy is introduced here.
            # Same-hand unresolved evidence remains provisional
            # when there is no positive stack corroboration.
            # ====================================================

            event_log.write_text("")

            unresolved_request = (
                "same-hand-unresolved"
            )

            state[
                "deferred_bet_amount_results"
            ] = {
                unresolved_request: {
                    "request": transition_request(
                        unresolved_request
                    ),
                    "result": transition_result(
                        unresolved_request
                    ),
                    "bet_bb": 3.25,
                    "seat": SEAT,
                    "street": STREET,
                }
            }

            state = (
                coord
                .release_corroborated_bet_amount_results(
                    state,
                    ChangeSet(),
                )
            )

            assert (
                unresolved_request
                in state[
                    "deferred_bet_amount_results"
                ]
            )

            assert not [
                item
                for item in read_events(
                    event_log
                )
                if (
                    item.get("type")
                    == "provisional_bet_closed"
                )
            ]

            print(
                "PASS coordinator provisional lifecycle: "
                "open on defer, close after publication on "
                "positive corroboration, retire stale hand, "
                "preserve same-hand unresolved evidence"
            )

    finally:
        coord.EVENT_LOG = old_event_log


if __name__ == "__main__":
    main()
