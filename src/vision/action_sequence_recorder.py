from pathlib import Path
import json
import time

import cv2


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = ROOT / "config/geometry.json"
OUT_DIR = ROOT / "runtime/debug/action_sequence"


def _crop(frame, rect):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])
    return frame[y:y + h, x:x + w]


class ActionSequenceRecorder:
    """
    Temporary diagnostic recorder.

    Saves the exact visual inputs and detector outputs for consecutive
    coordinator frames so action evidence can be audited frame by frame.
    """

    def __init__(self, max_frames=240):
        self.geometry = json.loads(
            GEOMETRY_PATH.read_text()
        )
        self.max_frames = int(max_frames)
        self.session_dir = None
        self.frame_index = 0

    def start_session(self):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = OUT_DIR / stamp
        self.session_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.frame_index = 0
        return self.session_dir

    def record(self, frame, changes, state, source_frame=None):
        if self.session_dir is None:
            self.start_session()

        if self.frame_index >= self.max_frames:
            return False

        self.frame_index += 1
        index = self.frame_index
        prefix = f"{index:04d}"

        full_path = self.session_dir / f"{prefix}_full.png"
        cv2.imwrite(str(full_path), frame)

        crops = {
            "hero_bet": (
                self.geometry
                .get("bet_regions", {})
                .get("hero")
            ),
            "hero_stack": (
                self.geometry
                .get("stack_regions", {})
                .get("hero")
            ),
            "action_buttons": (
                self.geometry
                .get("action_buttons", {})
                .get("primary")
            ),
            "pot": (
                self.geometry
                .get("pot_regions", {})
                .get("main_pot")
                or self.geometry.get("main_pot")
            ),
        }

        crop_files = {}

        for name, rect in crops.items():
            if not rect:
                continue

            crop = _crop(frame, rect)

            if crop.size == 0:
                continue

            crop_path = (
                self.session_dir
                / f"{prefix}_{name}.png"
            )

            cv2.imwrite(str(crop_path), crop)
            crop_files[name] = crop_path.name

        changes_dict = (
            changes.to_dict()
            if hasattr(changes, "to_dict")
            else dict(changes or {})
        )

        record = {
            "index": index,
            "ts": time.time(),
            "source_frame": (
                str(source_frame)
                if source_frame
                else None
            ),
            "phase": state.get("phase"),
            "hero_decision_active": state.get(
                "hero_decision_active"
            ),
            "confirmed_board_len": state.get(
                "confirmed_board_len"
            ),
            "files": {
                "full": full_path.name,
                **crop_files,
            },
            "changes": changes_dict,
        }

        metadata_path = (
            self.session_dir
            / f"{prefix}_metadata.json"
        )

        metadata_path.write_text(
            json.dumps(record, indent=2)
        )

        timeline_path = (
            self.session_dir
            / "timeline.jsonl"
        )

        with timeline_path.open("a") as handle:
            handle.write(
                json.dumps(record) + "\n"
            )

        return True
