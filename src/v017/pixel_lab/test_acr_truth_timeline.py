from pathlib import Path

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)
from src.v017.pixel_lab.acr_truth_timeline import (
    compile_truth_timeline,
)


ROOT = Path(__file__).resolve().parents[3]

CORPUS = (
    ROOT
    / "runtime/pixel_lab/acr_hand_histories"
)

ACCEPTANCE_IDS = (
    "2826874674",
    "2826896860",
    "2826877384",
    "2826936315",
    "2826934143",
    "2826934900",
)


def player(frame, name):
    for row in frame.players:
        if row.name == name:
            return row

    raise AssertionError(name)


def main():
    corpus = {
        hand.hand_id: hand
        for _, hand in parse_corpus(
            CORPUS
        )
    }

    assert set(
        ACCEPTANCE_IDS
    ).issubset(corpus)

    digests = []

    for hand_id in ACCEPTANCE_IDS:
        hand = corpus[hand_id]

        first = compile_truth_timeline(
            hand
        )
        second = compile_truth_timeline(
            hand
        )
        third = compile_truth_timeline(
            hand
        )

        assert first == second == third, (
            "timeline nondeterministic",
            hand_id,
        )

        assert first[0].cause_action == (
            "HAND_START"
        )

        assert tuple(
            row.stack
            for row in first[0].players
        ) == tuple(
            player.starting_stack
            for player in hand.players
        )

        # Pot can temporarily include uncalled money, but after
        # UNCALLED_RETURN it must return to the contestable pot.
        assert all(
            frame.pot >= -0.011
            for frame in first
        )

        # Fold state is monotonic.
        folded = set()

        for frame in first:
            current = {
                row.name
                for row in frame.players
                if row.folded
            }

            assert folded.issubset(
                current
            )

            folded = current

        print()
        print(
            "HAND",
            hand_id,
        )
        print(
            " players =",
            len(hand.players),
        )
        print(
            " frames =",
            len(first),
        )
        print(
            " final street =",
            first[-1].street,
        )
        print(
            " final board =",
            first[-1].board,
        )
        print(
            " final pot =",
            first[-1].pot,
        )

        for frame in first:
            if frame.cause_action in {
                "RAISE",
                "CALL",
                "BET",
                "FOLD",
                "FLOP_BOUNDARY",
                "TURN_BOUNDARY",
                "RIVER_BOUNDARY",
            }:
                print(
                    " ",
                    frame.sequence,
                    frame.street,
                    frame.cause_actor,
                    frame.cause_action,
                    "pot=",
                    frame.pot,
                )

        digests.append(
            (
                hand_id,
                repr(first),
            )
        )

    # Specific real-history accounting controls.

    # 2826934900:
    # Hero BB starts 31680, ante 70, BB 700,
    # raises another 1400 -> 29510.
    frames = compile_truth_timeline(
        corpus["2826934900"]
    )

    hero_raise = next(
        frame
        for frame in frames
        if (
            frame.cause_actor
            == "poker5068"
            and frame.cause_action
            == "RAISE"
        )
    )

    assert (
        player(
            hero_raise,
            "poker5068",
        ).stack
        == 29510.0
    ), player(
        hero_raise,
        "poker5068",
    )

    # 2826936315:
    # chancylucky33 starts 35090,
    # ante 70, SB 350, later raises 4900.
    frames = compile_truth_timeline(
        corpus["2826936315"]
    )

    re_raise = next(
        frame
        for frame in frames
        if (
            frame.cause_actor
            == "chancylucky33"
            and frame.cause_action
            == "RAISE"
        )
    )

    assert (
        player(
            re_raise,
            "chancylucky33",
        ).stack
        == 29770.0
    ), player(
        re_raise,
        "chancylucky33",
    )

    print()
    print(
        "REAL ACR STACK ACCOUNTING "
        "CONTROLS: PASS"
    )

    print(
        "V0.17 PIXEL LAB ACR TRUTH "
        "TIMELINE 3/3: PASS"
    )


if __name__ == "__main__":
    main()
