"""
Regression: chronology-blocked quantitative evidence survives
a later betting-price change and reconciles in action order.

Uses the existing behavioral contract rather than obsolete
source-text markers.
"""

from src.v017.test_blocked_call_survives_later_raise_price_change import (
    main as validate_price_change_reconciliation,
)


def main():
    validate_price_change_reconciliation()

    print(
        "BLOCKED QUANTITATIVE PRICE-CHANGE CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
