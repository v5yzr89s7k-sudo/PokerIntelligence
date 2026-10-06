from unittest.mock import patch

from src.v017 import run_live_observer as live


def main():
    captures = iter([
        ("MID_HAND", "/tmp/mid.png"),
        ("CLEAR", "/tmp/clear.png"),
        ("NEW_HAND", "/tmp/new.png"),
    ])

    def capture(_window):
        return next(captures)

    def cards_visible(image, _geometry):
        return image in ("MID_HAND", "NEW_HAND")

    def board_count(image, _geometry):
        return {
            "MID_HAND": 3,
            "CLEAR": 0,
            "NEW_HAND": 0,
        }[image]

    with patch.object(
        live,
        "capture_image",
        side_effect=capture,
    ), patch.object(
        live,
        "native_occupied_seats",
        return_value=("hero", "villain"),
    ), patch.object(
        live,
        "hero_cards_visible",
        side_effect=cards_visible,
    ), patch.object(
        live,
        "bootstrap_local_stacks",
        return_value=[],
    ), patch.object(
        live,
        "count_board_cards",
        side_effect=board_count,
        create=True,
    ), patch.object(
        live,
        "hand_participant_presence",
        return_value={
            "hero": {
                "seat": "hero",
                "dealt_in": True,
                "source": "hero_face_up",
            },
            "villain": {
                "seat": "villain",
                "dealt_in": True,
                "source": "opponent_card_back",
            },
        },
    ):
        image, *_ = live.wait_for_hand(
            object(),
            clear_confirmed=False,
        )

    assert image == "NEW_HAND", (
        "initial startup accepted Hero-visible "
        "mid-hand frame before clean-hand synchronization"
    )

    print("MID-HAND STARTUP ACCEPTED: NO")
    print("CLEAN INTERVAL REQUIRED: PASS")
    print("NEW PREFLOP HAND ACQUIRED: PASS")
    print("V0.17 INITIAL CLEAN-HAND STARTUP: PASS")


if __name__ == "__main__":
    main()
