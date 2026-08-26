from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import src.api.api_event_state_machine as sm


class FakeCommitmentTracker:
    def round_status(self, street):
        return {
            "street": street,
            "complete": False,
            "players_owing_action": ["hero"],
            "pending_to_act": ["hero"],
            "needs_response_from": [],
            "betting_open": False,
        }


class FakeTracker:
    def __init__(self):
        self.commitment_tracker = FakeCommitmentTracker()
        self.processed_episode_ids = set()


class FakeCanonical:
    hand_id = "synthetic-hand"
    current_street = "FLOP"
    players_to_act = ["hero"]


def main():
    tracker = FakeTracker()
    canonical = FakeCanonical()
    state = {
        "hand_token": "synthetic-token",
    }

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "betting_round_status.json"

        with patch.object(
            sm,
            "BETTING_ROUND_STATUS_PATH",
            path,
        ):
            # First transaction acknowledgement.
            sm.write_betting_round_status(
                tracker,
                canonical,
                state,
                processed_event_cursor=7,
            )

            first = json.loads(path.read_text())

            assert first["processed_event_cursor"] == 7

            # A handler-internal status write must never erase or
            # optimistically advance the last proven acknowledgement.
            sm.write_betting_round_status(
                tracker,
                canonical,
                state,
            )

            middle = json.loads(path.read_text())

            assert middle["processed_event_cursor"] == 7

            # The next completed main-loop transaction advances it.
            sm.write_betting_round_status(
                tracker,
                canonical,
                state,
                processed_event_cursor=8,
            )

            final = json.loads(path.read_text())

            assert final["processed_event_cursor"] == 8

    print(
        "PASS betting status event cursor: "
        "handler writes preserve acknowledgement and "
        "completed transactions advance it monotonically"
    )


if __name__ == "__main__":
    main()
