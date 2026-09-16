from pathlib import Path
import tempfile

from src.v017.july22_frame_preflop_replay import (
    replay,
)


EXPECTED = [
    ("POST_SMALL_BLIND", "hero", 0.5, None),
    ("POST_BIG_BLIND", "seat_lower_left", 1.0, None),
    ("FOLD", "seat_upper_left", None, None),
    ("FOLD", "seat_upper_right", None, None),
    ("FOLD", "seat_mid_right", None, None),
    ("RAISE", "seat_lower_right", None, 2.0),
    ("CALL", "hero", 1.5, None),
    ("CALL", "seat_lower_left", 1.0, None),
    ("CHECK", "hero", None, None),
    ("BET", "seat_lower_left", 3.37, None),
    ("FOLD", "seat_lower_right", None, None),
    ("CALL", "hero", 3.37, None),
    ("CHECK", "hero", None, None),
    ("CHECK", "seat_lower_left", None, None),
    ("CHECK", "hero", None, None),
    ("BET", "seat_lower_left", 6.75, None),
    ("FOLD", "hero", None, None),
]


def semantic_tuple(row):
    return (
        row["action"],
        row["seat"],
        row["amount_bb"],
        row["raise_to_bb"],
    )


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        result = replay(
            progression_dir=root
        )

        hand = result["hand"]
        events = result["events"]

        observed = [
            semantic_tuple(row)
            for row
            in hand.semantic_actions()
        ]

        assert observed == EXPECTED, observed

        assert hand.street == "RIVER"
        assert hand.next_actor is None
        assert hand.players["hero"].folded is True

        # ----------------------------------------------------
        # Independent RIVER identity / lifecycle.
        # ----------------------------------------------------

        starts = [
            row
            for row in events
            if (
                row.get("type")
                == "STREET_STARTED"
                and row.get("street")
                == "RIVER"
            )
        ]

        assert len(starts) == 1
        assert starts[0]["frame"] == 115
        assert starts[0]["next_actor"] == "hero"

        board = [
            row
            for row in events
            if (
                row.get("type")
                == "BOARD_IDENTITY_OBSERVED"
                and row.get("street")
                == "RIVER"
            )
        ]

        assert len(board) == 1
        assert board[0]["frame"] == 115
        assert board[0]["source_frames"] == [
            114,
            115,
        ]

        assert board[0]["board"] == [
            "Jd",
            "9s",
            "Tc",
            "9h",
            "7h",
        ]

        # ----------------------------------------------------
        # False wakes cannot own semantics.
        # ----------------------------------------------------

        for frame in (
            117,
            119,
        ):
            rows = [
                row
                for row in events
                if (
                    row.get("frame") == frame
                    and row.get("type")
                    == "STACK_MOTION_WAKE"
                )
            ]

            assert rows

            for row in rows:
                assert (
                    row.get(
                        "physical_delta_bb"
                    )
                    in (
                        None,
                        0.0,
                    )
                ), row

                assert (
                    "semantic_action"
                    not in row
                ), row

        # ----------------------------------------------------
        # BB's later quantitative action proves Hero completed
        # first. Generic chronology authority determines CHECK.
        # ----------------------------------------------------

        hero_check = [
            row
            for row in events
            if (
                row.get("frame") == 127
                and row.get("type")
                == "CHRONOLOGY_COMPLETION"
                and row.get("seat")
                == "hero"
            )
        ]

        assert len(hero_check) == 1

        assert (
            hero_check[0][
                "proved_by"
            ]
            == "seat_lower_left"
        )

        assert (
            hero_check[0][
                "semantic_action"
            ]
            == "CHECK"
        )

        # ----------------------------------------------------
        # BB physical stack delta owns quantitative BET.
        # ----------------------------------------------------

        bb = [
            row
            for row in events
            if (
                row.get("frame") == 127
                and row.get("type")
                == "STACK_MOTION_WAKE"
                and row.get("seat")
                == "seat_lower_left"
            )
        ]

        assert len(bb) == 1

        assert bb[0]["prior"] == 44.2
        assert bb[0]["resolved_value"] == 37.45

        assert (
            bb[0][
                "physical_delta_bb"
            ]
            == 6.75
        )

        assert (
            bb[0][
                "normalized_delta_bb"
            ]
            == 6.75
        )

        assert (
            bb[0][
                "semantic_action"
            ]
            == "BET"
        )

        # ----------------------------------------------------
        # Direct Hero-card disappearance owns final FOLD.
        # ----------------------------------------------------

        folds = [
            row
            for row in events
            if row.get("type")
            == "HERO_CARDS_DISAPPEARED"
        ]

        assert len(folds) == 1
        assert folds[0]["frame"] == 135
        assert folds[0]["seat"] == "hero"

        assert (
            folds[0][
                "semantic_action"
            ]
            == "FOLD"
        )

        # ----------------------------------------------------
        # Product progression must expose state/actions only
        # when independently established.
        # ----------------------------------------------------

        f115 = (
            root
            / "frame_0115_current_hand.txt"
        ).read_text()

        f127 = (
            root
            / "frame_0127_current_hand.txt"
        ).read_text()

        f135 = (
            root
            / "frame_0135_current_hand.txt"
        ).read_text()

        assert "RIVER: 7h" in f115

        river115 = f115.split(
            "RIVER: 7h",
            1,
        )[1]

        assert (
            "SB (poker5068) checks"
            not in river115
        )

        assert (
            "BB (Birkam) bets 6.75 BB"
            not in river115
        )

        assert (
            "Next Actor: SB (poker5068)"
            in f115
        )

        river127 = f127.split(
            "RIVER: 7h",
            1,
        )[1]

        assert (
            "SB (poker5068) checks"
            in river127
        )

        assert (
            "BB (Birkam) bets 6.75 BB"
            in river127
        )

        assert (
            "SB (poker5068) folds"
            not in river127
        )

        assert (
            "Next Actor: SB (poker5068)"
            in f127
        )

        river135 = f135.split(
            "RIVER: 7h",
            1,
        )[1]

        assert (
            "SB (poker5068) checks"
            in river135
        )

        assert (
            "BB (Birkam) bets 6.75 BB"
            in river135
        )

        assert (
            "SB (poker5068) folds"
            in river135
        )

        assert (
            "Betting round complete"
            in f135
        )

        print(
            "V0.17 JULY22 FRAME RIVER REPLAY: PASS"
        )


if __name__ == "__main__":
    main()
