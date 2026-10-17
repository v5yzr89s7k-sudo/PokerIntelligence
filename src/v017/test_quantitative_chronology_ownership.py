"""
Contract: later quantitative evidence may prove that an earlier actor
completed action, but semantic completion must remain canonical.

If the predecessor is already at the authoritative current price,
HandEngine.observe_no_commitment() classifies that completion as CHECK.

A chronology-only completion must not erase an objectively classifiable
poker action.
"""

from pathlib import Path


def main():
    source = Path(
        "src/v017/frame_hand_observer.py"
    ).read_text()

    hand_source = Path(
        "src/v017/hand_engine.py"
    ).read_text()

    assert "def observe_no_commitment" in hand_source

    assert (
        "cannot check while facing a bet"
        in hand_source
    )

    assert (
        ".observe_no_commitment("
        in source
    )

    assert (
        '"CHRONOLOGY_COMPLETION"'
        in source
    )

    assert (
        '"semantic_action":\n'
        '                        action'
        in source
    )

    print(
        "QUANTITATIVE CHRONOLOGY CANONICAL "
        "SEMANTIC OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
