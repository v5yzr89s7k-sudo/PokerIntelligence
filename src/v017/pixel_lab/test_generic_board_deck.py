"""
Acceptance for the V0.17 generic physical board deck.

The current accepted boundary is intentionally 51/52:
all legal identities except Ad must have an authentic donor that satisfies
unchanged production board presence in all five canonical board slots.

Ad must fail closed until equivalent authentic physical source material exists.
"""

from pathlib import Path
import json

from src.v017.pixel_lab.generic_board_deck import (
    LEGAL_CARDS,
    select_card_donor,
)


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY = json.loads(
    (
        ROOT / "config/geometry.json"
    ).read_text()
)


def main():
    accepted = {}
    rejected = {}

    for card in sorted(LEGAL_CARDS):
        try:
            selected = select_card_donor(
                card,
                geometry=GEOMETRY,
            )
        except RuntimeError as exc:
            rejected[card] = str(exc)
            continue

        accepted[card] = selected

    assert len(accepted) == 51, (
        len(accepted),
        sorted(rejected),
    )

    assert set(rejected) == {"Ad"}, (
        sorted(rejected),
    )

    assert (
        accepted["9c"]["source_kind"]
        == "authentic_board"
    )

    assert (
        accepted["Qh"]["source_kind"]
        == "authentic_board"
    )

    assert accepted["9c"]["worst_score"] > 0.45
    assert accepted["Qh"]["worst_score"] > 0.45

    print("===== GENERIC PHYSICAL BOARD DECK =====")
    print("legal identities =", len(LEGAL_CARDS))
    print("accepted =", len(accepted))
    print("rejected =", sorted(rejected))
    print()

    for card in ("9c", "Qh"):
        row = accepted[card]

        print(
            card,
            f"source={row['source_kind']}",
            f"path={row['path']}",
            f"worst={row['worst_score']:.6f}",
        )

    print()
    print("Ad =", rejected["Ad"])
    print()
    print("GENERIC PHYSICAL DECK 51/52: PASS")
    print("Ad FAIL-CLOSED CONTRACT: PASS")


if __name__ == "__main__":
    main()
