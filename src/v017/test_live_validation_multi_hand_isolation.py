from pathlib import Path
from tempfile import TemporaryDirectory

from src.v017.live_publication_recorder import (
    record_publication,
    reset_publication_progression,
)
from src.v017.run_live_observer import (
    archive_live_validation_hand,
)


def publication(text, frame):
    return {
        "frame": frame,
        "street": "PREFLOP",
        "action_count": 1,
        "next_actor": None,
        "text": text,
    }


def main():
    with TemporaryDirectory() as td:
        root = Path(td)
        live = root / "live"
        hands = root / "hands"

        current = live / "current_hand.txt"
        progression = live / "progression.jsonl"

        # HAND 1 — K3
        reset_publication_progression(progression)

        current.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        current.write_text(
            "HAND ONE\nHero Cards: Kh 3s\n"
            "Hero raises to 2 BB\n",
            encoding="utf-8",
        )

        record_publication(
            publication(
                "HAND ONE\nHero Cards: Kh 3s\n"
                "Hero raises to 2 BB\n",
                127,
            ),
            1000,
            progression,
        )

        archive_live_validation_hand(
            hand_id="live-v017-1",
            hand_number=1,
            current_hand_path=current,
            progression_path=progression,
            root=hands,
        )

        # HAND 2 — completely different evidence.
        reset_publication_progression(progression)

        current.write_text(
            "HAND TWO\nHero Cards: 5d Jh\n",
            encoding="utf-8",
        )

        record_publication(
            publication(
                "HAND TWO\nHero Cards: 5d Jh\n",
                20,
            ),
            2000,
            progression,
        )

        archive_live_validation_hand(
            hand_id="live-v017-2",
            hand_number=2,
            current_hand_path=current,
            progression_path=progression,
            root=hands,
        )

        h1_final = (
            hands / "live-v017-1"
            / "final_current_hand.txt"
        ).read_text()

        h1_progression = (
            hands / "live-v017-1"
            / "publication_progression.jsonl"
        ).read_text()

        h2_final = (
            hands / "live-v017-2"
            / "final_current_hand.txt"
        ).read_text()

        h2_progression = (
            hands / "live-v017-2"
            / "publication_progression.jsonl"
        ).read_text()

        assert "Kh 3s" in h1_final
        assert "raises to 2 BB" in h1_final
        assert "Kh 3s" in h1_progression

        assert "5d Jh" not in h1_final
        assert "5d Jh" not in h1_progression

        assert "5d Jh" in h2_final
        assert "5d Jh" in h2_progression

        assert "Kh 3s" not in h2_final
        assert "Kh 3s" not in h2_progression
        assert "raises to 2 BB" not in h2_progression

        print(
            "HAND 1 IMMUTABLE AFTER HAND 2: PASS"
        )
        print(
            "HAND 2 CONTAINS NO HAND 1 EVIDENCE: PASS"
        )
        print(
            "MULTI-HAND LIVE VALIDATION ISOLATION: PASS"
        )


if __name__ == "__main__":
    main()
