from collections import defaultdict

from src.v017.synthetic_lab.stack_assets import (
    mine_stack_assets,
    unique_resolved_values,
)


SEATS = (
    "seat_lower_right",
    "hero",
    "seat_lower_left",
)


def main():
    assets = mine_stack_assets(
        SEATS,
    )

    print(
        "asset observations =",
        len(assets),
    )

    assert len(assets) == 135 * len(SEATS)

    by_seat = defaultdict(list)

    for asset in assets:
        by_seat[asset.seat].append(
            asset
        )

    for seat in SEATS:
        rows = by_seat[seat]

        resolved = [
            row
            for row in rows
            if row.value is not None
        ]

        values = unique_resolved_values(
            rows
        )

        print()
        print("seat =", seat)
        print("observations =", len(rows))
        print("resolved =", len(resolved))
        print("unique values =", values)

        assert len(rows) == 135
        assert resolved
        assert values

    print()
    print(
        "SYNTHETIC LAB AUTHENTIC STACK "
        "ASSET BANK: PASS"
    )


if __name__ == "__main__":
    main()
