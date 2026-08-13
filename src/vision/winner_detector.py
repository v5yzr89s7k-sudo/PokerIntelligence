from pathlib import Path
import json

import cv2


ROOT = Path(__file__).resolve().parents[2]

CANONICAL_SIZE = (934, 696)
NORMALIZED_SIZE = (180, 48)

GEOMETRY = json.loads(
    (ROOT / "config/geometry.json").read_text()
)

STACK_REGIONS = GEOMETRY["stack_regions"]

TEMPLATE_PATH = (
    ROOT
    / "config/templates/winner_template.png"
)

# Human-verified calibration:
#
# verified ordinary-river negatives <= ~0.087
# verified clean WINNER positives   >= ~0.309
#
# 0.20 maintains a substantial measured gap.
WINNER_SCORE_THRESHOLD = 0.20


_TEMPLATE = None


def winner_roi_for_seat(seat):
    r = STACK_REGIONS[seat]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    left = max(0, x - 40)
    top = max(0, y - 85)
    right = min(
        CANONICAL_SIZE[0],
        x + w + 40,
    )
    bottom = min(
        CANONICAL_SIZE[1],
        y + h + 10,
    )

    return {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


def _crop(image, region):
    x = region["x"]
    y = region["y"]
    w = region["width"]
    h = region["height"]

    return image[
        y:y + h,
        x:x + w,
    ]


def _extract_bright_word(image):
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    _, mask = cv2.threshold(
        gray,
        190,
        255,
        cv2.THRESH_BINARY,
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (7, 3),
    )

    joined = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2,
    )

    contours, _ = cv2.findContours(
        joined,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    candidates = []

    H, W = gray.shape

    for contour in contours:
        x, y, w, h = cv2.boundingRect(
            contour
        )

        if h <= 0:
            continue

        aspect = w / float(h)
        area = w * h

        if (
            w >= 45
            and h >= 12
            and aspect >= 2.2
            and area >= 800
        ):
            score = (
                w
                + 0.4 * area
                + 20.0 * aspect
            )

            candidates.append(
                (
                    score,
                    x,
                    y,
                    w,
                    h,
                )
            )

    if not candidates:
        return None

    candidates.sort(reverse=True)

    _, x, y, w, h = candidates[0]

    pad_x = max(
        2,
        int(w * 0.04),
    )
    pad_y = max(
        2,
        int(h * 0.10),
    )

    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(W, x + w + pad_x)
    y1 = min(H, y + h + pad_y)

    word = gray[
        y0:y1,
        x0:x1,
    ]

    word = cv2.resize(
        word,
        NORMALIZED_SIZE,
    )

    _, normalized = cv2.threshold(
        word,
        175,
        255,
        cv2.THRESH_BINARY,
    )

    return normalized


def _template():
    global _TEMPLATE

    if _TEMPLATE is not None:
        return _TEMPLATE

    tmpl = cv2.imread(
        str(TEMPLATE_PATH),
        cv2.IMREAD_GRAYSCALE,
    )

    if tmpl is None:
        raise RuntimeError(
            f"WINNER template missing: {TEMPLATE_PATH}"
        )

    if (
        tmpl.shape[1],
        tmpl.shape[0],
    ) != NORMALIZED_SIZE:
        tmpl = cv2.resize(
            tmpl,
            NORMALIZED_SIZE,
        )

    _TEMPLATE = tmpl
    return _TEMPLATE


def _similarity(template, candidate):
    if candidate is None:
        return None

    if candidate.shape != template.shape:
        candidate = cv2.resize(
            candidate,
            (
                template.shape[1],
                template.shape[0],
            ),
        )

    template_edges = cv2.Canny(
        template,
        50,
        150,
    )

    candidate_edges = cv2.Canny(
        candidate,
        50,
        150,
    )

    result = cv2.matchTemplate(
        candidate_edges,
        template_edges,
        cv2.TM_CCOEFF_NORMED,
    )

    return float(
        result[0, 0]
    )


def detect_winner(image):
    """
    Detect ACR's WINNER treatment and localize it to a canonical seat.

    This detector is fully local and production-contained. It performs no
    OCR and has no dependency on replay/debug sessions.
    """
    if image is None:
        return {
            "visible": False,
            "seat": None,
            "confidence": 0.0,
            "score": -1.0,
            "second_score": -1.0,
            "margin": 0.0,
        }

    if (
        image.shape[1],
        image.shape[0],
    ) != CANONICAL_SIZE:
        image = cv2.resize(
            image,
            CANONICAL_SIZE,
        )

    tmpl = _template()

    results = []

    for seat in STACK_REGIONS:
        roi = _crop(
            image,
            winner_roi_for_seat(
                seat
            ),
        )

        word = _extract_bright_word(
            roi
        )

        score = _similarity(
            tmpl,
            word,
        )

        if score is None:
            score = -1.0

        results.append(
            (
                float(score),
                seat,
            )
        )

    results.sort(reverse=True)

    best_score, best_seat = results[0]
    second_score = results[1][0]

    margin = (
        best_score
        - second_score
    )

    visible = bool(
        best_score
        >= WINNER_SCORE_THRESHOLD
    )

    return {
        "visible": visible,
        "seat": (
            best_seat
            if visible
            else None
        ),
        "confidence": (
            min(
                1.0,
                max(
                    0.0,
                    (
                        best_score
                        - WINNER_SCORE_THRESHOLD
                    )
                    / (
                        1.0
                        - WINNER_SCORE_THRESHOLD
                    ),
                ),
            )
            if visible
            else 0.0
        ),
        "score": best_score,
        "second_score": second_score,
        "margin": margin,
    }
