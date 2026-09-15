from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import src.vision.action_sequence_recorder as recorder_module
from src.vision.action_sequence_recorder import ActionSequenceRecorder


class EmptyChanges:
    def to_dict(self):
        return {}


def main():
    original_out_dir = recorder_module.OUT_DIR

    try:
        with TemporaryDirectory() as tmp:
            recorder_module.OUT_DIR = Path(tmp)

            recorder = ActionSequenceRecorder(
                max_frames=None
            )

            frame = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            state = {
                "phase": "PREFLOP",
                "hero_decision_active": False,
                "confirmed_board_len": 0,
            }

            # Historical recorder capacity was 240.
            # Unlimited diagnostic recording must cross that
            # boundary without silently stopping.
            for index in range(1, 242):
                recorded = recorder.record(
                    frame=frame,
                    changes=EmptyChanges(),
                    state=state,
                )

                assert recorded is True, (
                    "unlimited recorder stopped at "
                    f"frame {index}"
                )

            assert recorder.frame_index == 241

            full_frames = list(
                recorder.session_dir.glob("*_full.png")
            )

            metadata = list(
                recorder.session_dir.glob(
                    "*_metadata.json"
                )
            )

            assert len(full_frames) == 241
            assert len(metadata) == 241

            # Preserve bounded mode as a supported contract.
            bounded = ActionSequenceRecorder(
                max_frames=2
            )
            bounded.start_session()

            assert bounded.record(
                frame,
                EmptyChanges(),
                state,
            ) is True

            assert bounded.record(
                frame,
                EmptyChanges(),
                state,
            ) is True

            assert bounded.record(
                frame,
                EmptyChanges(),
                state,
            ) is False

            print(
                "PASS: action-sequence recorder supports "
                "unlimited diagnostic recording while "
                "preserving bounded mode"
            )

    finally:
        recorder_module.OUT_DIR = original_out_dir


if __name__ == "__main__":
    main()
