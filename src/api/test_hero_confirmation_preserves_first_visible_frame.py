from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.api import api_event_coordinator as c


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        first_visible = root / "0063_full.png"
        confirming = root / "0078_full.png"

        first_visible.write_bytes(b"first-visible")
        confirming.write_bytes(b"confirming")

        state = c.fresh_state()

        queued = []

        def fake_queue(state_arg, frame):
            queued.append(str(frame))
            return state_arg

        # First qualifying Hero-visible frame.
        #
        # Two-frame confirmation should NOT queue yet, but it must retain
        # ownership of this frame for the hand acquisition being confirmed.
        with patch.object(
            c,
            "queue_hero_request",
            side_effect=fake_queue,
        ):
            state = c.maybe_read_hero(
                state,
                hero_visible=True,
                board_count=0,
                frame=first_visible,
                img=None,
            )

        assert queued == [], (
            "first visible frame queued Hero before confirmation"
        )

        owner = state.get(
            "hero_acquisition_first_visible_frame"
        )

        print(
            "after_first_visible_owner:",
            owner,
        )

        assert owner == str(first_visible), (
            "RED: first qualifying Hero-visible frame "
            "was not retained as acquisition owner"
        )

        # Second qualifying frame confirms visibility.
        #
        # The worker request must use the FIRST frame, not this later
        # confirming frame.
        with patch.object(
            c,
            "queue_hero_request",
            side_effect=fake_queue,
        ):
            state = c.maybe_read_hero(
                state,
                hero_visible=True,
                board_count=0,
                frame=confirming,
                img=None,
            )

        print(
            "queued:",
            queued,
        )

        assert queued == [
            str(first_visible)
        ], (
            "RED: Hero confirmation queued the confirming frame "
            "instead of the first qualifying visible frame"
        )

        print()
        print(
            "PASS: two-frame Hero confirmation preserves "
            "first-visible acquisition frame ownership"
        )


if __name__ == "__main__":
    main()
