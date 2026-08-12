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

    # When OCR includes the BB suffix, accept only a syntactically valid
    # numeric token immediately before BB. Never salvage a partial number
    # from malformed text such as "95./2 BB" or "99./2 BB".
    match = re.search(
        r"(?<![\d./])"
        r"(\d+(?:\.\d+)?)"
        r"\s*BB\b",
        text,
        re.IGNORECASE,
    )

    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    if re.search(r"\bBB\b", text, re.IGNORECASE):
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


def _ocr(image, config=OCR_CONFIG):
    raw = pytesseract.image_to_string(
        image,
        config=config,
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

    Exact majority agreement is authoritative. A single conflicting OCR
    variant must not override two matching readings.
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

    # Exact majority agreement wins.
    # Do not override two agreeing variants with one conflicting read.

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

    # Green-mask and grayscale PSM7 are correlated views of the same glyph.
    # They can therefore agree on the same systematic OCR error. Replay 0001
    # demonstrated ACR's leading "5" being read as "9" by both views.
    #
    # Verify apparent two-view agreement with an independent single-line/glyph
    # segmentation mode before assigning high confidence.
    if (
        green_value is not None
        and green_value == plain_value
    ):
        # Replay 0001 calibration: ACR's leading "5" is systematically
        # misread as "9" by the normal PSM7 paths. A fixed 130 grayscale
        # threshold with PSM13 preserves the glyph correctly across the
        # captured transition:
        #
        #   65.6 -> 56.6 -> 51.6
        #
        # This is an independent verification path, not a digit substitution.
        psm13_image = cv2.threshold(
            gray,
            130,
            255,
            cv2.THRESH_BINARY,
        )[1]

        psm13_result = {
            "variant": "psm13_t130",
            **_ocr(
                psm13_image,
                config="--psm 13",
            ),
        }

        psm13_value = psm13_result["stack_bb"]

        if (
            psm13_value is not None
            and psm13_value != green_value
        ):
            # PSM13 is independent evidence, not an authoritative override.
            #
            # Green + plain PSM7 are correlated and can agree on the same
            # glyph error (Replay 0001: 56.6 -> 96.6). But PSM13 can also be
            # wrong independently (Replay 0001 Hero: 90.84 vs 80.84).
            #
            # Preserve every candidate and deliberately mark the result
            # ambiguous. The coordinator owns canonical previous-stack
            # continuity and will promote a candidate only when the resulting
            # transition is plausible.
            return {
                "raw": [
                    green_result,
                    plain_result,
                    psm13_result,
                ],
                "stack_bb": green_value,
                "stack_text": f"{green_value:g} BB",
                "confidence": 0.50,
                "votes": 1,
                "mode": "segmentation_disagreement",
            }

        value = green_value

        return {
            "raw": [
                green_result,
                plain_result,
                psm13_result,
            ],
            "stack_bb": value,
            "stack_text": f"{value:g} BB",
            "confidence": 0.98,
            "votes": 2,
            "mode": "agreement_verified",
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

