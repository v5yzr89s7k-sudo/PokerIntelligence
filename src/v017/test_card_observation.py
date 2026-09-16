from src.v017.card_observation import (
    normalize_card,
    normalize_cards,
)


def main():
    assert normalize_card(
        "10c"
    ) == "Tc"

    assert normalize_card(
        "Tc"
    ) == "Tc"

    assert normalize_card(
        "jd"
    ) == "Jd"

    assert normalize_cards(
        [
            "Jd",
            "9s",
            "10c",
            "9h",
            "7h",
        ]
    ) == [
        "Jd",
        "9s",
        "Tc",
        "9h",
        "7h",
    ]

    print(
        "V0.17 CARD OBSERVATION NORMALIZATION: PASS"
    )


if __name__ == "__main__":
    main()
