from pathlib import Path
import json
import os
import tempfile

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_renderer import render_canonical_hand


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON = ROOT / "runtime/live/canonical_hand.json"
DEFAULT_TEXT = ROOT / "runtime/live/current_hand_canonical.txt"


class CanonicalHandStore:
    def __init__(
        self,
        json_path: Path = DEFAULT_JSON,
        text_path: Path = DEFAULT_TEXT,
    ):
        self.json_path = Path(json_path)
        self.text_path = Path(text_path)

    @staticmethod
    def _atomic_write(path: Path, text: str):
        path.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=str(path.parent),
            text=True,
        )

        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_name, path)
        finally:
            temp_path = Path(temp_name)
            if temp_path.exists():
                temp_path.unlink()

    def exists(self) -> bool:
        return self.json_path.exists()

    def load(self) -> CanonicalHand:
        if not self.json_path.exists():
            return CanonicalHand()

        data = json.loads(self.json_path.read_text())
        return CanonicalHand.from_dict(data)

    def save(self, hand: CanonicalHand):
        json_text = json.dumps(
            hand.to_dict(),
            indent=2,
            sort_keys=False,
        ) + "\n"

        rendered = render_canonical_hand(hand)

        self._atomic_write(self.json_path, json_text)
        self._atomic_write(self.text_path, rendered)

    def reset(self):
        for path in (self.json_path, self.text_path):
            if path.exists():
                path.unlink()
