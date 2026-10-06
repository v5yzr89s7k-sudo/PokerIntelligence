"""
V0.17 authoritative live-publication recorder contract.
"""

import json
import tempfile
from pathlib import Path

from src.v017.live_publication_recorder import (
    record_publication,
    reset_publication_progression,
)


def main():
    with tempfile.TemporaryDirectory() as td:
        path = (
            Path(td)
            / "progression.jsonl"
        )

        reset_publication_progression(path)

        first = {
            "frame": 10,
            "street": "PREFLOP",
            "action_count": 3,
            "next_actor": "hero",
            "text": "FIRST PRODUCT\n",
        }

        second = {
            "frame": 11,
            "street": "PREFLOP",
            "action_count": 4,
            "next_actor": "bb",
            "text": "SECOND PRODUCT\n",
        }

        record_publication(
            first,
            1000,
            path,
        )

        record_publication(
            second,
            2000,
            path,
        )

        rows = [
            json.loads(line)
            for line in path.read_text(
                encoding="utf-8"
            ).splitlines()
        ]

        assert len(rows) == 2, rows

        assert rows[0] == {
            "frame": 10,
            "street": "PREFLOP",
            "action_count": 3,
            "next_actor": "hero",
            "sink_complete_ns": 1000,
            "text": "FIRST PRODUCT\n",
        }

        assert rows[1] == {
            "frame": 11,
            "street": "PREFLOP",
            "action_count": 4,
            "next_actor": "bb",
            "sink_complete_ns": 2000,
            "text": "SECOND PRODUCT\n",
        }

        # Reset belongs to lifecycle setup, never individual
        # publication recording.
        reset_publication_progression(path)

        assert path.read_text(
            encoding="utf-8"
        ) == ""

        print("AUTHORITATIVE PUBLICATIONS RECORDED: PASS")
        print("PUBLICATION ORDER PRESERVED: PASS")
        print("EXACT PRODUCT TEXT PRESERVED: PASS")
        print("RECORDER RESET: PASS")
        print(
            "V0.17 LIVE PUBLICATION RECORDER: PASS"
        )


if __name__ == "__main__":
    main()
