import re
from collections import Counter
from typing import Any, Dict, Optional

import cv2
import pytesseract


LOWER_GREEN = (35, 30, 60)
UPPER_GREEN = (95, 255, 255)

OCR_CONFIG = "--psm 7"


def _parse_value(raw: str) -> Optional[float]:
    text = str(raw or "").strip()

    # Best case: OCR included the BB suffix.
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*BB\b",
        text,
        re.IGNORECASE,
    )

    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        text,
    )

    if not numbers:
        return None

    # Prefer decimal values (typical BB format).
    decimals = [
        n for n in numbers
        if "." in n
    ]

    if decimals:
        token = decimals[0]
    else:
        token = numbers[0]

    try:
        return float(token)
    except ValueError:
        return None


def _prepare_images(crop):
    if crop is None or crop.size == 0:
        raise ValueError(
            "crop must be a non-empty image"
        )

    enlarged = cv2.resize(
        crop,
        None,
        fx=6,
        fy=6,
        interpolation=cv2.INTER_CUBIC,
    )

    hsv = cv2.cvtColor(
        enlarged,
        cv2.COLOR_BGR2HSV,
    )

    gray = cv2.cvtColor(
        enlarged,
        cv2.COLOR_BGR2GRAY,
    )

    green = cv2.inRange(
        hsv,
        LOWER_GREEN,
        UPPER_GREEN,
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (2, 2),
    )

    green = cv2.morphologyEx(
        green,
        cv2.MORPH_OPEN,
        kernel,
    )

    green = cv2.morphologyEx(
        green,
        cv2.MORPH_CLOSE,
        kernel,
    )

    return enlarged, gray, green


def _ocr(image):
    raw = pytesseract.image_to_string(
        image,
        config=OCR_CONFIG,
    ).strip()

    return {
        "raw": raw,
        "stack_bb": _parse_value(raw),
    }


def _green_is_trustworthy(reading):
    raw = reading["raw"]
    value = reading["stack_bb"]

    if value is None:
        return False

    if not (0 <= value <= 1000):
        return False

    if not re.search(
        r"\bBB\b",
        raw,
        re.IGNORECASE,
    ):
        return False

    token_match = re.search(
        r"(\d+(?:\.\d+)?)\s*BB\b",
        raw,
        re.IGNORECASE,
    )

    if not token_match:
        return False

    token = token_match.group(1)

    # Decimal stack displays are the normal ACR format.
    # Reject suspicious merged-digit values such as 4784.
    if "." not in token:
        return False

    integer_part, decimal_part = token.split(
        ".",
        1,
    )

    if not integer_part or len(decimal_part) != 2:
        return False

    return True


def _fallback_read(gray):
    otsu = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )[1]

    plain = _ocr(gray)
    otsu_result = _ocr(otsu)

    return [
        {
            "variant": "plain",
            **plain,
        },
        {
            "variant": "otsu",
            **otsu_result,
        },
    ]


def _resolve(readings):
    """
    Resolve disagreement between green, plain, and Otsu OCR variants.

    Green-mask OCR is the primary ACR stack reader. Plain and Otsu are
    correlated fallback variants and can make the same leading-digit error,
    so their 2-to-1 vote is not trusted when the disagreement is large.
    """
    by_variant = {
        reading.get("variant"): reading.get("stack_bb")
        for reading in readings
    }

    green = by_variant.get("green")
    plain = by_variant.get("plain")
    otsu = by_variant.get("otsu")

    numeric = [
        value
        for value in (green, plain, otsu)
        if value is not None
    ]

    if not numeric:
        return None, 0

    # Exact agreement remains the strongest result.
    counts = Counter(numeric)
    majority_value, majority_votes = counts.most_common(1)[0]

    # Plain and Otsu are derived from the same grayscale source and can make
    # the same truncation/substitution error. In observed failures they agreed
    # on values such as 32.29 or 24.97 while green correctly read 82.29 or
    # 94.97. Prefer green when that correlated majority differs by >20 BB.
    if (
        green is not None
        and plain is not None
        and otsu is not None
        and plain == otsu
        and green != plain
    ):
        green_digits = str(int(round(green)))
        plain_digits = str(int(round(plain)))

        # Reject obvious digit-merging OCR failures such as:
        # 64.1  -> 641
        # 82.3  -> 823
        # 111.0 -> 11101
        if (
            len(green_digits) >= len(plain_digits) + 1
            and green_digits.startswith(plain_digits)
        ):
            return plain, 2

        if abs(green - plain) > 20.0:
            return green, 1

    return majority_value, majority_votes


def read_stack(crop) -> Dict[str, Any]:
    _, gray, green = _prepare_images(crop)

    green_result = {
        "variant": "green",
        **_ocr(green),
    }

    plain_result = {
        "variant": "plain",
        **_ocr(gray),
    }

    green_value = green_result["stack_bb"]
    plain_value = plain_result["stack_bb"]

    # Both methods agree.
    if (
        green_value is not None
        and green_value == plain_value
    ):
        value = green_value

        return {
            "raw": [
                green_result,
                plain_result,
            ],
            "stack_bb": value,
            "stack_text": f"{value:g} BB",
            "confidence": 0.98,
            "votes": 2,
            "mode": "agreement",
        }

    # Only one method produced a value.
    if green_value is None and plain_value is None:
        return {
            "raw": [
                green_result,
                plain_result,
            ],
            "stack_bb": None,
            "stack_text": "",
            "confidence": 0.0,
            "votes": 0,
            "mode": "empty",
        }

    if green_value is not None and plain_value is None:
        return {
            "raw": [
                green_result,
                plain_result,
            ],
            "stack_bb": green_value,
            "stack_text": f"{green_value:g} BB",
            "confidence": 0.80,
            "votes": 1,
            "mode": "green_only",
        }

    if plain_value is not None and green_value is None:
        return {
            "raw": [
                green_result,
                plain_result,
            ],
            "stack_bb": plain_value,
            "stack_text": f"{plain_value:g} BB",
            "confidence": 0.75,
            "votes": 1,
            "mode": "plain_only",
        }

    # Disagreement: use Otsu as the tiebreaker.
    otsu = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )[1]

    otsu_result = {
        "variant": "otsu",
        **_ocr(otsu),
    }

    readings = [
        green_result,
        plain_result,
        otsu_result,
    ]

    value, votes = _resolve(readings)

    # Debug suspicious OCR disagreements.
    numeric = [
        r.get("stack_bb")
        for r in readings
        if r.get("stack_bb") is not None
    ]

    if numeric:
        spread = max(numeric) - min(numeric)

        if spread > 20:
            print("\n[STACK OCR DISAGREEMENT]")
            for r in readings:
                print(
                    f"  {r['variant']:<6} "
                    f"raw={repr(r.get('raw')):<12} "
                    f"parsed={r.get('stack_bb')}"
                )
            print(f"  resolved={value} votes={votes}\n", flush=True)

    confidence = (
        0.95
        if votes >= 2
        else 0.50
    )

    return {
        "raw": readings,
        "stack_bb": value,
        "stack_text": (
            f"{value:g} BB"
            if value is not None
            else ""
        ),
        "confidence": confidence,
        "votes": votes,
        "mode": "tiebreak",
    }

