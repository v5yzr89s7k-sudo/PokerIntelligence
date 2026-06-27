from pathlib import Path
import json

class LiveStateStore:
    """Temporary current/last hand state store.

    This is intentionally separate from the permanent database.
    Live OCR state can be overwritten/discarded. Completed ACR hand histories
    should be parsed later into a permanent database.
    """

    def __init__(self, project_root: Path):
        self.output_dir = project_root / "output"
        self.current_path = self.output_dir / "current_hand_state.json"
        self.last_path = self.output_dir / "last_hand_state.json"

    def set_current(self, state: dict):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def clear_current_to_last(self):
        if self.current_path.exists():
            self.last_path.write_text(self.current_path.read_text(encoding="utf-8"), encoding="utf-8")
            self.current_path.unlink()
