from unittest.mock import patch

from src.v017.run_live_observer import (
    read_hero_identity,
)


def main():
    with patch(
        "src.v017.run_live_observer.read_hero_cards",
        return_value=(
            {
                "hero_cards": [
                    "",
                    "",
                ],
                "confidence": 0.0,
            },
            {
                "total_ms": 10.0,
            },
        ),
    ):
        result = read_hero_identity(
            "unused.png"
        )

    assert result is None

    print(
        "V0.17 UNRESOLVED HERO "
        "IDENTITY RETRY: PASS"
    )


if __name__ == "__main__":
    main()
