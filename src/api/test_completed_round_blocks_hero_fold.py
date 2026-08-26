from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_coordinator as coord


def run_case(*, complete, owing):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        old_status = coord.BETTING_ROUND_STATUS
        old_event_log = coord.EVENT_LOG

        try:
            coord.BETTING_ROUND_STATUS = (
                root / "betting_round_status.json"
            )
            coord.EVENT_LOG = root / "api_events.jsonl"

            coord.BETTING_ROUND_STATUS.write_text(
                __import__("json").dumps({
                    "street": "FLOP",
                    "complete": complete,
                    "players_owing_action": owing,
                })
            )

            state = coord.fresh_state()
            state["phase"] = "FLOP"
            state["hand_token"] = "synthetic-hand"
            state["hero_clear_seen"] = 3
            state[
                "last_hero_action_complete_phase"
            ] = "FLOP"

            result = coord.maybe_complete_early(
                state,
                3,
                False,
            )

            events = []

            if coord.EVENT_LOG.exists():
                import json

                events = [
                    json.loads(line)
                    for line in (
                        coord.EVENT_LOG
                        .read_text()
                        .splitlines()
                    )
                    if line.strip()
                ]

            return result, events

        finally:
            coord.BETTING_ROUND_STATUS = old_status
            coord.EVENT_LOG = old_event_log


def main():
    # Completed betting round: card disappearance cannot
    # create another same-street Hero action.
    state, events = run_case(
        complete=True,
        owing=[],
    )

    assert not any(
        event.get("type") == "hero_fold"
        for event in events
    ), events

    assert not any(
        event.get("type") == "hand_complete"
        for event in events
    ), events

    assert state["phase"] == "FLOP"

    # Unfinished betting round: existing fold behavior remains.
    state, events = run_case(
        complete=False,
        owing=["hero"],
    )

    folds = [
        event
        for event in events
        if event.get("type") == "hero_fold"
    ]

    assert len(folds) == 1, events
    assert folds[0]["street"] == "FLOP"

    assert any(
        event.get("type") == "hand_complete"
        for event in events
    ), events

    print(
        "PASS: completed betting round suppresses "
        "same-street Hero fold while unfinished round "
        "preserves real fold classification"
    )


if __name__ == "__main__":
    main()
