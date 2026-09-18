from pathlib import Path

import cv2


JULY22_ROOT = Path(
    "runtime/debug/action_sequence/20260722_152155"
)


class RecordedFrameSource:
    """
    Deterministic authentic-ACR frame source.

    This is the laboratory's initial visual backend. It deliberately
    exposes pixels only; semantic ground truth lives elsewhere.
    """

    def __init__(self, root=JULY22_ROOT):
        self.root = Path(root)

    def path(self, number):
        return self.root / f"{number:04d}_full.png"

    def load(self, number):
        path = self.path(number)

        if not path.exists():
            raise FileNotFoundError(path)

        image = cv2.imread(str(path))

        if image is None:
            raise RuntimeError(
                f"unable to decode frame: {path}"
            )

        if image.shape[:2] != (696, 934):
            raise ValueError(
                "laboratory sensor frame must be 934x696: "
                f"{path} -> "
                f"{image.shape[1]}x{image.shape[0]}"
            )

        return image
