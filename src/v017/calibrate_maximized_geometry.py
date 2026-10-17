from pathlib import Path
import json
import cv2


ROOT = Path(__file__).resolve().parents[2]

IMAGE_PATH = (
    ROOT
    / "runtime/debug/v017_max_geometry"
    / "pair_maximized.png"
)

BASE_PATH = (
    ROOT
    / "runtime/debug/v017_max_geometry"
    / "geometry_maximized.json"
)

OUTPUT_PATH = (
    ROOT
    / "runtime/debug/v017_max_geometry"
    / "geometry_maximized_manual.json"
)

OVERLAY_PATH = (
    ROOT
    / "runtime/debug/v017_max_geometry"
    / "geometry_maximized_manual_overlay.png"
)

SEATS = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]

BOARD = [
    "flop_1",
    "flop_2",
    "flop_3",
    "turn",
    "river",
]


def select_rect(image, title):
    print()
    print("SELECT:", title)
    print(
        "Drag tightly around target, "
        "then press ENTER."
    )

    window = title

    cv2.namedWindow(
        window,
        cv2.WINDOW_NORMAL,
    )

    cv2.resizeWindow(
        window,
        1500,
        940,
    )

    roi = cv2.selectROI(
        window,
        image,
        showCrosshair=True,
        fromCenter=False,
    )

    cv2.destroyWindow(window)

    x, y, w, h = map(int, roi)

    if w <= 0 or h <= 0:
        raise SystemExit(
            f"Cancelled at {title}"
        )

    rect = {
        "x": x,
        "y": y,
        "width": w,
        "height": h,
    }

    print("saved:", rect)

    return rect


def draw_rect(
    image,
    rect,
    label,
):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    cv2.rectangle(
        image,
        (x, y),
        (x + w, y + h),
        (255, 255, 255),
        3,
    )

    cv2.putText(
        image,
        label,
        (x, max(25, y - 6)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def main():
    image = cv2.imread(
        str(IMAGE_PATH)
    )

    if image is None:
        raise SystemExit(
            f"Missing image: {IMAGE_PATH}"
        )

    h, w = image.shape[:2]

    if BASE_PATH.exists():
        geometry = json.loads(
            BASE_PATH.read_text()
        )
    else:
        geometry = {}

    geometry["table_size"] = {
        "width": w,
        "height": h,
    }

    geometry["geometry_version"] = (
        "v017-maximized-native-manual"
    )

    print()
    print(
        "MAXIMIZED NATIVE GEOMETRY CALIBRATION"
    )
    print(
        "Reference:",
        IMAGE_PATH,
    )
    print(
        "Resolution:",
        f"{w}x{h}",
    )

    print()
    print("===== STACKS: 8 =====")

    geometry["stack_regions"] = {}

    for seat in SEATS:
        geometry[
            "stack_regions"
        ][seat] = select_rect(
            image,
            f"STACK — {seat}",
        )

    print()
    print("===== HERO CARDS: 2 =====")

    geometry["hero_cards"] = {}

    geometry["hero_cards"][
        "card_1"
    ] = select_rect(
        image,
        "HERO CARD 1",
    )

    geometry["hero_cards"][
        "card_2"
    ] = select_rect(
        image,
        "HERO CARD 2",
    )

    print()
    print("===== BOARD: 5 =====")

    geometry["board"] = {}

    for name in BOARD:
        geometry["board"][
            name
        ] = select_rect(
            image,
            f"BOARD — {name}",
        )

    print()
    print("===== OPPONENT CARDS =====")
    print(
        "Select CARD 1 and CARD 2 separately "
        "for each opponent seat."
    )

    geometry["hole_cards"] = {}

    for seat in SEATS:
        if seat == "hero":
            continue

        geometry[
            "hole_cards"
        ][seat] = {
            "card_1": select_rect(
                image,
                f"OPPONENT CARD 1 — {seat}",
            ),
            "card_2": select_rect(
                image,
                f"OPPONENT CARD 2 — {seat}",
            ),
        }

    geometry[
        "hole_cards"
    ]["hero"] = {
        "card_1":
            dict(
                geometry[
                    "hero_cards"
                ]["card_1"]
            ),
        "card_2":
            dict(
                geometry[
                    "hero_cards"
                ]["card_2"]
            ),
    }

    print()
    print("===== BET REGIONS: 8 =====")

    geometry["bet_regions"] = {}

    for seat in SEATS:
        geometry[
            "bet_regions"
        ][seat] = select_rect(
            image,
            f"BET REGION — {seat}",
        )

    OUTPUT_PATH.write_text(
        json.dumps(
            geometry,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    overlay = image.copy()

    for seat, rect in (
        geometry[
            "stack_regions"
        ].items()
    ):
        draw_rect(
            overlay,
            rect,
            f"STACK:{seat}",
        )

    for name, rect in (
        geometry[
            "hero_cards"
        ].items()
    ):
        draw_rect(
            overlay,
            rect,
            f"HERO:{name}",
        )

    for name, rect in (
        geometry["board"].items()
    ):
        draw_rect(
            overlay,
            rect,
            f"BOARD:{name}",
        )

    for seat, rect in (
        geometry[
            "hole_cards"
        ].items()
    ):
        draw_rect(
            overlay,
            rect,
            f"CARDS:{seat}",
        )

    for seat, rect in (
        geometry[
            "bet_regions"
        ].items()
    ):
        draw_rect(
            overlay,
            rect,
            f"BET:{seat}",
        )

    cv2.imwrite(
        str(OVERLAY_PATH),
        overlay,
    )

    print()
    print(
        "MAXIMIZED MANUAL CALIBRATION: COMPLETE"
    )
    print(
        "geometry:",
        OUTPUT_PATH,
    )
    print(
        "overlay:",
        OVERLAY_PATH,
    )


if __name__ == "__main__":
    main()
