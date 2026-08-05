from pathlib import Path

from src.api.pot_api_reader import read_pot


ROOT = Path(__file__).resolve().parents[2]

cases = [
    (
        "acr_table_20260803_193131_476109.png",
        2.5,
    ),
    (
        "acr_table_20260803_193146_997151.png",
        5.0,
    ),
    (
        "acr_table_20260803_193151_628637.png",
        5.0,
    ),
]

for filename, expected in cases:
    frame = ROOT / "runtime" / "window_captures" / filename

    result = read_pot(frame)

    assert result["ok"] is True, (filename, result)
    assert result["pot_bb"] == expected, (filename, result)

    print(
        filename,
        "PASS",
        result["pot_bb"],
        result.get("read_mode"),
        "support=",
        result.get("support"),
    )

print("Saved-frame pot reader regression passed.")
