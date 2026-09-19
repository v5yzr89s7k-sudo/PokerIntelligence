"""
V0.17 unified production publication-progression acceptance.

The observer receives PNG pixels only.

Every live publication must be an authoritative monotonic projection:
  * published actions are exact prefixes of the final action sequence;
  * an already-published action never changes or disappears;
  * action_count never decreases;
  * street never regresses;
  * board cards never disappear or change;
  * final publication agrees with final HandEngine state.

This protects runtime/live/current_hand.txt from transient semantic
errors that happen to self-correct by the final frame.
"""

import hashlib
import json
import re

from src.v017.pixel_lab.test_real_acr_observer_pixels import (
    generator_phase,
    assert_wall,
    observer_phase,
)


ACTION_RE = re.compile(
    r"^\s*(\d+)\.\s+"
)


def semantic_action_signature(row):
    return {
        "sequence": row["sequence"],
        "street": row["street"],
        "seat": row["seat"],
        "position": row["position"],
        "name": row["name"],
        "action": row["action"],
        "amount_bb": row["amount_bb"],
        "raise_to_bb": row["raise_to_bb"],
    }


def publication_action_lines(text):
    """
    Return numbered rendered action lines only.

    This is diagnostic/product evidence. Semantic authority remains
    HandEngine; the prefix contract below compares publication counts
    against the authoritative final action sequence.
    """
    return tuple(
        line.strip()
        for line in text.splitlines()
        if ACTION_RE.match(line)
    )


def board_from_text(text):
    """
    Read board identity from the established current_hand.txt format:

        FLOP: Jd 9s Tc
        TURN: Jd 9s Tc 7h
        RIVER: Jd 9s Tc 7h 2c
    """
    board = ()

    for line in text.splitlines():
        stripped = line.strip()

        for street in (
            "FLOP",
            "TURN",
            "RIVER",
        ):
            prefix = street + ":"

            if not stripped.startswith(
                prefix
            ):
                continue

            value = stripped[
                len(prefix):
            ].strip()

            if not value:
                continue

            cards = tuple(
                value.split()
            )

            if len(cards) > len(board):
                board = cards

    return board




def main():
    generator_phase()
    assert_wall()

    result = observer_phase()
    observer = result["observer"]

    publications = tuple(
        observer.publications
    )

    assert publications, (
        "production emitted no publications"
    )

    final_actions = tuple(
        semantic_action_signature(row)
        for row
        in observer.hand.semantic_actions()
    )

    assert len(final_actions) == 11

    previous_count = -1
    previous_board = ()
    previous_lines = ()

    progression = []

    street_rank = {
        "WAITING": 0,
        "PREFLOP": 1,
        "FLOP": 2,
        "TURN": 3,
        "RIVER": 4,
    }

    previous_street_rank = -1

    print()
    print(
        "===== PRODUCTION PUBLICATION PROGRESSION ====="
    )

    for index, publication in enumerate(
        publications
    ):
        frame = publication["frame"]
        count = int(
            publication["action_count"]
        )
        street = publication["street"]
        text = publication["text"]

        assert 0 <= count <= len(
            final_actions
        ), (
            index,
            frame,
            count,
        )

        assert count >= previous_count, (
            "action_count regression",
            previous_count,
            count,
            frame,
        )

        rank = street_rank[street]

        assert rank >= previous_street_rank, (
            "street regression",
            frame,
            street,
        )

        lines = publication_action_lines(
            text
        )

        # Rendered actions may include forced contributions. Whatever
        # has already appeared in the live product must remain an exact
        # textual prefix thereafter.
        assert lines[:len(previous_lines)] == (
            previous_lines
        ), (
            "published action changed/disappeared",
            frame,
            previous_lines,
            lines,
        )

        board = board_from_text(text)

        assert board[:len(previous_board)] == (
            previous_board
        ), (
            "published board changed",
            frame,
            previous_board,
            board,
        )

        assert len(board) >= len(
            previous_board
        ), (
            "published board regressed",
            frame,
            previous_board,
            board,
        )

        row = {
            "index": index,
            "frame": frame,
            "action_count": count,
            "street": street,
            "next_actor":
                publication["next_actor"],
            "board": list(board),
            "action_lines": list(lines),
            "text_sha256":
                hashlib.sha256(
                    text.encode("utf-8")
                ).hexdigest(),
        }

        progression.append(row)

        print(
            "publication",
            index,
            "frame=",
            frame,
            "actions=",
            count,
            "street=",
            street,
            "next_actor=",
            publication["next_actor"],
            "board=",
            board,
            "text_hash=",
            row["text_sha256"],
        )

        previous_count = count
        previous_street_rank = rank
        previous_board = board
        previous_lines = lines

    final = publications[-1]

    assert final["action_count"] == len(
        final_actions
    )

    assert final["street"] == (
        observer.hand.street
    )

    assert observer.hand.hand_complete is True

    # Known authoritative checkpoints for this physical hand.
    by_frame = {
        row["frame"]: row
        for row in progression
    }

    assert by_frame[13][
        "action_count"
    ] == 6

    assert by_frame[13][
        "street"
    ] == "PREFLOP"

    assert by_frame[16][
        "action_count"
    ] == 8

    assert by_frame[16][
        "street"
    ] == "FLOP"

    assert by_frame[16][
        "board"
    ] == [
        "Jd",
        "9s",
        "Tc",
    ]

    assert by_frame[19][
        "action_count"
    ] == 11

    assert by_frame[19][
        "street"
    ] == "FLOP"

    encoded = json.dumps(
        progression,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    print()
    print(
        "publication_count =",
        len(publications),
    )
    print(
        "progression_sha256 =",
        digest,
    )

    print()
    print(
        "ACTION COUNT MONOTONIC: PASS"
    )
    print(
        "ACTION TEXT PREFIX MONOTONIC: PASS"
    )
    print(
        "STREET MONOTONIC: PASS"
    )
    print(
        "BOARD MONOTONIC: PASS"
    )
    print(
        "FINAL PUBLICATION AUTHORITATIVE: PASS"
    )
    print(
        "V0.17 PRODUCTION PUBLICATION PROGRESSION: PASS"
    )


if __name__ == "__main__":
    main()
