from pathlib import Path
from tempfile import TemporaryDirectory

from src.v017.run_live_observer import (
    archive_live_validation_hand,
)


def main():
    with TemporaryDirectory() as td:
        root = Path(td)

        current = root / "current_hand.txt"
        progression = root / "progression.jsonl"
        destination = root / "hands"

        current.write_text(
            "CURRENT HAND\nHero Cards: Kh 3s\n",
            encoding="utf-8",
        )

        progression.write_text(
            '{"frame":"bootstrap","action_count":2}\n'
            '{"frame":127,"action_count":7}\n',
            encoding="utf-8",
        )

        hand_dir = archive_live_validation_hand(
            hand_id="live-v017-1",
            hand_number=1,
            current_hand_path=current,
            progression_path=progression,
            root=destination,
        )

        assert hand_dir == (
            destination / "live-v017-1"
        )

        final = (
            hand_dir / "final_current_hand.txt"
        ).read_text()

        archived_progression = (
            hand_dir
            / "publication_progression.jsonl"
        ).read_text()

        metadata = (
            hand_dir / "metadata.json"
        ).read_text()

        assert "Kh 3s" in final
        assert '"frame":127' in archived_progression
        assert '"hand_id": "live-v017-1"' in metadata
        assert '"hand_number": 1' in metadata

        print(
            "PER-HAND LIVE VALIDATION ARCHIVE: PASS"
        )


if __name__ == "__main__":
    main()
