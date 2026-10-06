"""
Production publish_new() sink/recorder contract.

The authoritative current_hand sink owns the product.
The forensic progression recorder mirrors only a product that has
already crossed that sink.

Recorder failure must never prevent authoritative publication.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.v017 import run_live_observer as live


class Observer:
    def __init__(self):
        self.publications = [{
            "frame": 42,
            "street": "FLOP",
            "action_count": 7,
            "next_actor": "bb",
            "text": "AUTHORITATIVE LIVE PRODUCT\n",
        }]


def main():
    observer = Observer()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        product = root / "current_hand.txt"
        progression = root / "progression.jsonl"

        with (
            patch.object(
                live,
                "CURRENT_HAND",
                product,
            ),
            patch.object(
                live,
                "record_publication",
            ) as record,
        ):
            completed = live.publish_new(
                observer,
                0,
            )

        assert len(completed) == 1, completed

        publication = observer.publications[0]

        assert product.read_text(
            encoding="utf-8"
        ) == publication["text"]

        record.assert_called_once()

        args = record.call_args.args

        assert args[0] is publication
        assert isinstance(args[1], int)
        assert args[1] > 0

        # Now exercise the actual recorder against a temporary path
        # using the exact production publication and sink timestamp.
        from src.v017.live_publication_recorder import (
            record_publication,
        )

        row = record_publication(
            publication,
            args[1],
            progression,
        )

        disk_row = json.loads(
            progression.read_text(
                encoding="utf-8"
            ).strip()
        )

        assert disk_row == row
        assert disk_row["text"] == (
            product.read_text(
                encoding="utf-8"
            )
        )

        print("CURRENT_HAND EXACT PRODUCT: PASS")
        print("RECORDER EXACT PRODUCT MIRROR: PASS")

        # Failure isolation: product must still be written even if
        # forensic telemetry fails.
        second_product = (
            root / "current_hand_failure_case.txt"
        )

        with (
            patch.object(
                live,
                "CURRENT_HAND",
                second_product,
            ),
            patch.object(
                live,
                "record_publication",
                side_effect=RuntimeError(
                    "synthetic recorder failure"
                ),
            ),
        ):
            completed_failure = live.publish_new(
                observer,
                0,
            )

        assert len(completed_failure) == 1

        assert second_product.read_text(
            encoding="utf-8"
        ) == publication["text"]

        print("RECORDER FAILURE PRODUCT LOSS: NO")
        print("AUTHORITATIVE SINK REMAINS OWNER: PASS")
        print(
            "V0.17 PRODUCTION PUBLICATION "
            "RECORDER WIRING: PASS"
        )


if __name__ == "__main__":
    main()
