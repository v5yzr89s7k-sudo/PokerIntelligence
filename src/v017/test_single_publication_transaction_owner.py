"""
V0.17 architectural publication ownership contract.

Publication creation must have one transaction owner.

FrameHandObserver admission primitives may mutate authoritative
HandEngine state, but they must not independently create nested
publication transactions.

The production physical-frame transaction owns the commit boundary.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

OBSERVER = (
    ROOT / "src/v017/frame_hand_observer.py"
)

RUNNER = (
    ROOT / "src/v017/run_live_observer.py"
)


def method_block(text, name):
    marker = f"    def {name}("
    start = text.find(marker)

    assert start >= 0, name

    next_method = text.find(
        "\n    def ",
        start + len(marker),
    )

    if next_method < 0:
        next_method = len(text)

    return text[start:next_method]


def main():
    observer = OBSERVER.read_text()
    runner = RUNNER.read_text()

    card = method_block(
        observer,
        "admit_card_disappearance",
    )

    quantitative = method_block(
        observer,
        "admit_quantitative_observation",
    )

    offenders = []

    for name, block in (
        (
            "admit_card_disappearance",
            card,
        ),
        (
            "admit_quantitative_observation",
            quantitative,
        ),
    ):
        if (
            "_begin_publication_transaction("
            in block
            or "_end_publication_transaction("
            in block
        ):
            offenders.append(name)

    print(
        "nested_publication_owners =",
        offenders,
    )

    assert not offenders, (
        "semantic admission primitives still own "
        "nested publication transactions"
    )

    assert (
        "def process_frame_transaction("
        in runner
    )

    assert (
        "publish_authoritative_state("
        in runner
    )

    print(
        "ADMISSION PRIMITIVE PUBLICATION OWNERS: ZERO"
    )
    print(
        "PHYSICAL TRANSACTION COMMIT OWNER: PRESENT"
    )
    print(
        "V0.17 SINGLE PUBLICATION TRANSACTION OWNER: PASS"
    )


if __name__ == "__main__":
    main()
