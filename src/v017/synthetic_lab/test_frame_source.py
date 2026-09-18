from src.v017.synthetic_lab.frame_source import (
    RecordedFrameSource,
)
from src.v017.synthetic_lab.scenario import (
    JULY22_BASELINE,
)


def main():
    source = RecordedFrameSource()

    dimensions = []

    for step in JULY22_BASELINE.steps:
        image = source.load(step.frame)

        dimensions.append(
            (
                step.frame,
                image.shape[1],
                image.shape[0],
            )
        )

        print(
            f"frame={step.frame:03d}",
            f"size={image.shape[1]}x{image.shape[0]}",
            f"label={step.label}",
        )

    assert dimensions
    assert all(
        width == 934 and height == 696
        for _, width, height in dimensions
    )

    print()
    print(
        "SYNTHETIC LAB AUTHENTIC FRAME SOURCE: PASS"
    )


if __name__ == "__main__":
    main()
