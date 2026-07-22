from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from src.api.participant_validation_recorder import (
    record_participant_comparison,
)


class ParticipantValidationRecorderTests(unittest.TestCase):
    def paths(self, directory):
        root = Path(directory)
        return (
            root / "records.jsonl",
            root / "summary.json",
        )

    def test_exact_match(self):
        with TemporaryDirectory() as directory:
            records, summary = self.paths(directory)

            result = record_participant_comparison(
                hand_token="hand-1",
                local_dealt_in=["seat_top", "hero"],
                snapshot_dealt_in=["seat_top", "hero"],
                local_frame_count=8,
                records_path=records,
                summary_path=summary,
            )

            self.assertTrue(result["recorded"])
            self.assertTrue(result["record"]["exact_match"])
            self.assertEqual(
                result["summary"]["accuracy_percent"],
                100.0,
            )

    def test_mismatch(self):
        with TemporaryDirectory() as directory:
            records, summary = self.paths(directory)

            result = record_participant_comparison(
                hand_token="hand-2",
                local_dealt_in=["seat_top", "hero"],
                snapshot_dealt_in=[
                    "seat_top",
                    "seat_upper_right",
                    "hero",
                ],
                records_path=records,
                summary_path=summary,
            )

            self.assertFalse(
                result["record"]["exact_match"]
            )
            self.assertEqual(
                result["record"]["missing_locally"],
                ["seat_upper_right"],
            )

    def test_duplicate_is_skipped(self):
        with TemporaryDirectory() as directory:
            records, summary = self.paths(directory)

            kwargs = {
                "hand_token": "hand-3",
                "local_dealt_in": ["hero"],
                "snapshot_dealt_in": ["hero"],
                "records_path": records,
                "summary_path": summary,
            }

            first = record_participant_comparison(**kwargs)
            second = record_participant_comparison(**kwargs)

            self.assertTrue(first["recorded"])
            self.assertFalse(second["recorded"])
            self.assertEqual(
                second["reason"],
                "duplicate_hand_token",
            )

    def test_summary_accumulates(self):
        with TemporaryDirectory() as directory:
            records, summary = self.paths(directory)

            record_participant_comparison(
                hand_token="hand-4",
                local_dealt_in=["hero"],
                snapshot_dealt_in=["hero"],
                records_path=records,
                summary_path=summary,
            )

            record_participant_comparison(
                hand_token="hand-5",
                local_dealt_in=["hero"],
                snapshot_dealt_in=["seat_top", "hero"],
                records_path=records,
                summary_path=summary,
            )

            data = json.loads(summary.read_text())

            self.assertEqual(data["hands_compared"], 2)
            self.assertEqual(data["exact_matches"], 1)
            self.assertEqual(data["mismatches"], 1)
            self.assertEqual(data["accuracy_percent"], 50.0)
            self.assertEqual(
                data["missing_locally_by_seat"],
                {"seat_top": 1},
            )

    def test_missing_roster_is_skipped(self):
        with TemporaryDirectory() as directory:
            records, summary = self.paths(directory)

            result = record_participant_comparison(
                hand_token="hand-6",
                local_dealt_in=[],
                snapshot_dealt_in=["hero"],
                records_path=records,
                summary_path=summary,
            )

            self.assertFalse(result["recorded"])
            self.assertEqual(
                result["reason"],
                "missing_local_roster",
            )


if __name__ == "__main__":
    unittest.main()
