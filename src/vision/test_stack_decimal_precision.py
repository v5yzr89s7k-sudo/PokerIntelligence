from src.vision.stack_reader import _parse_value


def main():
    cases = [
        # Normal values remain unchanged.
        ("28.36 BB", 28.36),
        ("53.41 BB", 53.41),
        ("65.6 BB", 65.6),
        ("7 BB", 7.0),

        # OCR contamination after valid ACR decimal precision.
        ("28.3688", 28.36),
        ("28.368", 28.36),
        ("28.3688 BB", 28.36),

        # Must truncate, never round.
        ("12.9999", 12.99),
        ("12.345", 12.34),

        # Existing malformed-BB protection remains intact.
        ("95./2 BB", None),
        ("99./2 BB", None),
    ]

    for raw, expected in cases:
        actual = _parse_value(raw)

        print(
            repr(raw),
            "->",
            actual,
        )

        assert actual == expected, (
            raw,
            actual,
            expected,
        )

    print()
    print(
        "PASS stack decimal precision: "
        "ACR stack OCR accepts at most two decimal digits; "
        "excess OCR digits are truncated rather than rounded"
    )


if __name__ == "__main__":
    main()
