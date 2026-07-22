from datetime import datetime
from pathlib import Path
import json
import shutil
import subprocess
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = ROOT / "config/geometry.json"
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
DEBUG_DIR = ROOT / "runtime/debug"

FRAME_WIDTH = 934
FRAME_HEIGHT = 696
SIDEBAR_WIDTH = 390
CANVAS_WIDTH = FRAME_WIDTH + SIDEBAR_WIDTH
CANVAS_HEIGHT = FRAME_HEIGHT

WINDOW_NAME = "Hole-card geometry calibration"

SEAT_ORDER = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]

CARD_NAMES = [
    "card_1",
    "card_2",
]


def capture_frame():
    subprocess.run(
        [
            sys.executable,
            str(CAPTURE_SCRIPT),
        ],
        cwd=str(ROOT),
        check=True,
    )

    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    )

    if not captures:
        raise RuntimeError(
            "window_capture.py produced no capture"
        )

    return captures[-1]


def to_canonical(image):
    return cv2.resize(
        image,
        (FRAME_WIDTH, FRAME_HEIGHT),
        interpolation=cv2.INTER_AREA,
    )


def normalized_rect(start, end):
    x1 = min(start[0], end[0])
    y1 = min(start[1], end[1])
    x2 = max(start[0], end[0])
    y2 = max(start[1], end[1])

    return {
        "x": int(x1),
        "y": int(y1),
        "width": int(x2 - x1),
        "height": int(y2 - y1),
    }


def draw_saved_rectangles(image, completed):
    output = image.copy()

    for seat, cards in completed.items():
        for card_name, rect in cards.items():
            x = int(rect["x"])
            y = int(rect["y"])
            width = int(rect["width"])
            height = int(rect["height"])

            cv2.rectangle(
                output,
                (x, y),
                (x + width, y + height),
                (0, 255, 0),
                2,
            )

            label_y = (
                y - 5
                if y >= 18
                else y + height + 15
            )

            cv2.putText(
                output,
                f"{seat}:{card_name}",
                (x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.34,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

    return output


def draw_drag_preview(image, start, current):
    if start is None or current is None:
        return image

    output = image.copy()

    x1 = min(start[0], current[0])
    y1 = min(start[1], current[1])
    x2 = max(start[0], current[0])
    y2 = max(start[1], current[1])

    cv2.rectangle(
        output,
        (x1, y1),
        (x2, y2),
        (0, 255, 255),
        2,
    )

    cv2.putText(
        output,
        f"{x2 - x1} x {y2 - y1}",
        (x1, max(15, y1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (0, 255, 255),
        1,
        cv2.LINE_AA,
    )

    return output


def draw_sidebar(
    canvas,
    seat,
    card_name,
    step_number,
    total_steps,
    last_rect,
):
    x0 = FRAME_WIDTH

    canvas[
        0:CANVAS_HEIGHT,
        x0:CANVAS_WIDTH,
    ] = (25, 25, 25)

    text_x = x0 + 22
    y = 40

    cv2.putText(
        canvas,
        "HOLE-CARD CALIBRATION",
        (text_x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    y += 46

    cv2.putText(
        canvas,
        f"Step {step_number} of {total_steps}",
        (text_x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (210, 210, 210),
        1,
        cv2.LINE_AA,
    )

    y += 44

    cv2.putText(
        canvas,
        seat,
        (text_x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.70,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    y += 38

    cv2.putText(
        canvas,
        card_name,
        (text_x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    y += 62

    instructions = [
        "1. Move to exact card corner.",
        "2. Hold LEFT mouse button.",
        "3. Drag around the full card.",
        "4. Release to accept.",
        "",
        "Include:",
        "  - full visible card body",
        "",
        "Exclude:",
        "  - avatar",
        "  - player name",
        "  - stack text",
        "  - surrounding felt",
        "",
        "Keys:",
        "  U = undo previous card",
        "  R = redraw current card",
        "  Q = abort without saving",
        "  Esc = abort without saving",
    ]

    for line in instructions:
        cv2.putText(
            canvas,
            line,
            (text_x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )

        y += 25

    if last_rect:
        y = CANVAS_HEIGHT - 72

        cv2.putText(
            canvas,
            (
                f"Last: x={last_rect['x']} "
                f"y={last_rect['y']}"
            ),
            (text_x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (150, 255, 150),
            1,
            cv2.LINE_AA,
        )

        y += 24

        cv2.putText(
            canvas,
            (
                f"Size: {last_rect['width']} x "
                f"{last_rect['height']}"
            ),
            (text_x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (150, 255, 150),
            1,
            cv2.LINE_AA,
        )


def main():
    if not GEOMETRY_PATH.exists():
        raise SystemExit(
            f"geometry not found: {GEOMETRY_PATH}"
        )

    print()
    print(
        "Pause the replay immediately after every player "
        "has received cards and before the first fold."
    )
    print()

    frame_path = capture_frame()

    raw = cv2.imread(
        str(frame_path)
    )

    if raw is None or raw.size == 0:
        raise SystemExit(
            f"could not read captured frame: {frame_path}"
        )

    frame = to_canonical(raw)

    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    tasks = [
        (seat, card_name)
        for seat in SEAT_ORDER
        for card_name in CARD_NAMES
    ]

    completed = {}
    history = []

    task_index = 0
    dragging = False
    drag_start = None
    drag_current = None
    accepted_rect = None
    last_rect = None
    aborted = False

    def mouse_callback(
        event,
        x,
        y,
        flags,
        userdata,
    ):
        nonlocal dragging
        nonlocal drag_start
        nonlocal drag_current
        nonlocal accepted_rect

        # Sidebar clicks are ignored.
        if x >= FRAME_WIDTH:
            return

        x = max(
            0,
            min(FRAME_WIDTH - 1, int(x)),
        )

        y = max(
            0,
            min(FRAME_HEIGHT - 1, int(y)),
        )

        if event == cv2.EVENT_LBUTTONDOWN:
            dragging = True
            drag_start = (x, y)
            drag_current = (x, y)
            accepted_rect = None

        elif (
            event == cv2.EVENT_MOUSEMOVE
            and dragging
        ):
            drag_current = (x, y)

        elif (
            event == cv2.EVENT_LBUTTONUP
            and dragging
        ):
            dragging = False
            drag_current = (x, y)

            rect = normalized_rect(
                drag_start,
                drag_current,
            )

            if (
                rect["width"] >= 8
                and rect["height"] >= 8
            ):
                accepted_rect = rect
            else:
                print(
                    "Rejected rectangle: too small. "
                    "Please drag it again."
                )

            drag_start = None
            drag_current = None

    cv2.namedWindow(
        WINDOW_NAME,
        cv2.WINDOW_AUTOSIZE,
    )

    cv2.setMouseCallback(
        WINDOW_NAME,
        mouse_callback,
    )

    while task_index < len(tasks):
        seat, card_name = tasks[task_index]

        table_view = draw_saved_rectangles(
            frame,
            completed,
        )

        table_view = draw_drag_preview(
            table_view,
            drag_start,
            drag_current,
        )

        canvas = np.zeros(
            (
                CANVAS_HEIGHT,
                CANVAS_WIDTH,
                3,
            ),
            dtype=np.uint8,
        )

        canvas[
            0:FRAME_HEIGHT,
            0:FRAME_WIDTH,
        ] = table_view

        draw_sidebar(
            canvas,
            seat,
            card_name,
            task_index + 1,
            len(tasks),
            last_rect,
        )

        cv2.imshow(
            WINDOW_NAME,
            canvas,
        )

        key = cv2.waitKey(20) & 0xFF

        if key in (
            27,
            ord("q"),
            ord("Q"),
        ):
            aborted = True
            break

        if key in (
            ord("r"),
            ord("R"),
        ):
            dragging = False
            drag_start = None
            drag_current = None
            accepted_rect = None

        if key in (
            ord("u"),
            ord("U"),
        ):
            if history:
                previous_seat, previous_card = (
                    history.pop()
                )

                if (
                    previous_seat in completed
                    and previous_card
                    in completed[previous_seat]
                ):
                    del completed[
                        previous_seat
                    ][previous_card]

                    if not completed[
                        previous_seat
                    ]:
                        del completed[
                            previous_seat
                        ]

                task_index = max(
                    0,
                    task_index - 1,
                )

                last_rect = None
                accepted_rect = None
                dragging = False
                drag_start = None
                drag_current = None

        if accepted_rect is not None:
            completed.setdefault(
                seat,
                {},
            )[card_name] = accepted_rect

            history.append(
                (seat, card_name)
            )

            last_rect = dict(
                accepted_rect
            )

            print(
                f"{seat:20s} "
                f"{card_name:6s} "
                f"x={accepted_rect['x']:3d} "
                f"y={accepted_rect['y']:3d} "
                f"w={accepted_rect['width']:3d} "
                f"h={accepted_rect['height']:3d}"
            )

            accepted_rect = None
            task_index += 1

    cv2.destroyAllWindows()

    if aborted:
        print()
        print(
            "Calibration aborted. "
            "config/geometry.json was not changed."
        )
        return

    missing = [
        f"{seat}:{card_name}"
        for seat in SEAT_ORDER
        for card_name in CARD_NAMES
        if card_name not in completed.get(
            seat,
            {},
        )
    ]

    if missing:
        raise SystemExit(
            "Calibration incomplete: "
            + ", ".join(missing)
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = (
        GEOMETRY_PATH.parent
        / (
            "geometry.before_hole_cards_"
            f"{timestamp}.json"
        )
    )

    shutil.copy2(
        GEOMETRY_PATH,
        backup_path,
    )

    geometry["hole_cards"] = completed

    geometry["hero_cards"] = {
        card_name: dict(rect)
        for card_name, rect
        in completed["hero"].items()
    }

    GEOMETRY_PATH.write_text(
        json.dumps(
            geometry,
            indent=2,
        )
        + "\n"
    )

    DEBUG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    overlay = draw_saved_rectangles(
        frame,
        completed,
    )

    overlay_path = (
        DEBUG_DIR
        / "calibrated_hole_card_geometry.png"
    )

    cv2.imwrite(
        str(overlay_path),
        overlay,
    )

    coordinates_path = (
        DEBUG_DIR
        / "calibrated_hole_card_geometry.json"
    )

    coordinates_path.write_text(
        json.dumps(
            completed,
            indent=2,
        )
        + "\n"
    )

    print()
    print("Calibration saved successfully.")
    print("Source frame:", frame_path)
    print("Geometry:", GEOMETRY_PATH)
    print("Backup:", backup_path)
    print("Overlay:", overlay_path)
    print("Coordinates:", coordinates_path)


if __name__ == "__main__":
    main()
