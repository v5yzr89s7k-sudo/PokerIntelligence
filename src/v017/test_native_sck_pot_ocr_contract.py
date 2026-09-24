from pathlib import Path

from src.api.pot_api_reader import read_pot


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/debug/v017_sck_visual_truth_20260924_140419"
    / "first_authoritative_sck_frame.png"
)


def main():
    assert FRAME.exists(), FRAME

    result = read_pot(FRAME)

    print("result =", result)

    assert result.get("ok") is True, (
        "visually authoritative native SCK frame "
        "contains 'Total: 2.25 BB' but pot reader failed"
    )

    assert result.get("pot_bb") == 2.25, (
        "native SCK pot OCR must recover exactly 2.25 BB; "
        f"observed={result.get('pot_bb')!r}"
    )

    assert int(result.get("support") or 0) >= 2, (
        "bootstrap requires independently supported "
        "starting-pot authority"
    )

    print(
        "NATIVE SCK POT PIXEL TRUTH: PASS"
    )


if __name__ == "__main__":
    main()
