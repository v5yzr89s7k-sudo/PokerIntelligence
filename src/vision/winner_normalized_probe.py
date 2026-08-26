from pathlib import Path
import json
import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]

GEOMETRY = json.loads(
    (ROOT / "config/geometry.json").read_text()
)

STACK_REGIONS = GEOMETRY["stack_regions"]
CANONICAL_SIZE = (934, 696)

NORMALIZED_SIZE = (180, 48)


def canonical_image(path):
    image = cv2.imread(str(path))

    if image is None:
        raise RuntimeError(path)

    return cv2.resize(
        image,
        CANONICAL_SIZE,
    )


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


def crop(image, region):
    x = region["x"]
    y = region["y"]
    w = region["width"]
    h = region["height"]

    return image[y:y+h, x:x+w]


def extract_bright_word(image):
    """
    Locate the large bright horizontal WINNER word independent of its
    exact size and position inside a seat-relative terminal region.

    This is deliberately a visual glyph extractor, not OCR.
    """
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
        return None, None

    candidates.sort(reverse=True)

    _, x, y, w, h = candidates[0]

    pad_x = max(2, int(w * 0.04))
    pad_y = max(2, int(h * 0.10))

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

    return normalized, {
        "x": x0,
        "y": y0,
        "width": x1 - x0,
        "height": y1 - y0,
        "aspect": w / float(h),
    }


def similarity(a, b):
    if a is None or b is None:
        return None

    ae = cv2.Canny(
        a,
        50,
        150,
    )

    be = cv2.Canny(
        b,
        50,
        150,
    )

    result = cv2.matchTemplate(
        be,
        ae,
        cv2.TM_CCOEFF_NORMED,
    )

    return float(result[0, 0])


def template():
    path = (
        ROOT
        / "runtime/debug/action_sequence"
        / "20260809_124419"
        / "0105_full.png"
    )

    image = canonical_image(path)

    region = winner_roi_for_seat(
        "hero"
    )

    word, meta = extract_bright_word(
        crop(
            image,
            region,
        )
    )

    if word is None:
        raise RuntimeError(
            "could not extract template WINNER word"
        )

    out = (
        ROOT
        / "runtime/debug/"
        "winner_normalized_template.png"
    )

    cv2.imwrite(
        str(out),
        word,
    )

    print(
        "template:",
        out,
        meta,
    )

    return word


def analyze(session_name, indices, tmpl):
    session = (
        ROOT
        / "runtime/debug/action_sequence"
        / session_name
    )

    print()
    print("=" * 78)
    print(session_name)
    print("=" * 78)

    for idx in indices:
        path = session / f"{idx:04d}_full.png"

        if not path.exists():
            continue

        image = canonical_image(path)

        results = []

        for seat in STACK_REGIONS:
            region = winner_roi_for_seat(
                seat
            )

            word, meta = extract_bright_word(
                crop(
                    image,
                    region,
                )
            )

            score = similarity(
                tmpl,
                word,
            )

            if score is None:
                score = -1.0

            results.append(
                (
                    score,
                    seat,
                    meta,
                )
            )

        results.sort(
            reverse=True,
            key=lambda item: item[0],
        )

        best = results[0]
        second = results[1]

        print()
        print(
            f"{idx:04d} "
            f"best={best[1]:18s} "
            f"score={best[0]:.4f} "
            f"second={second[0]:.4f} "
            f"margin={best[0]-second[0]:.4f}"
        )

        for score, seat, meta in results:
            if score < 0:
                continue

            print(
                f"  {seat:18s} "
                f"{score:.4f} "
                f"box={meta}"
            )


def main():
    tmpl = template()

    analyze(
        "20260809_124419",
        range(100, 111),
        tmpl,
    )

    analyze(
        "20260718_172832",
        range(130, 138),
        tmpl,
    )


if __name__ == "__main__":
    main()
