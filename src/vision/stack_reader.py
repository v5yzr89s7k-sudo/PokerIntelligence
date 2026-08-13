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

    def normalize_stack_token(token):
        """
        Normalize OCR numeric text to ACR stack-display precision.

        ACR stack values display at most two decimal digits. OCR may merge
        adjacent BB glyphs into trailing digits, e.g.:
            28.36BB -> 28.3688

        Excess decimal digits therefore cannot represent additional stack
        precision. Truncate them before numeric conversion; never round them.
        """
        token = str(token)

        if "." not in token:
            return token

        integer_part, decimal_part = token.split(
            ".",
            1,
        )

        if len(decimal_part) > 2:
            decimal_part = decimal_part[:2]

        return (
            integer_part
            + "."
            + decimal_part
        )

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
            return float(
                normalize_stack_token(
                    match.group(1)
                )
            )
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
        return float(
            normalize_stack_token(token)
        )
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


def _independent_segmentation_consensus(gray):
    """
    Independently verify a stack value across several fixed-threshold
    segmentations.

    Green-mask, grayscale PSM7, and Otsu are correlated views and may share
    the same glyph error. This verifier uses thresholded PSM13 reads and
    returns a candidate only when that independent family is internally
    consistent.

    No digit substitutions or poker-state assumptions are applied here.
    """
    thresholds = (90, 100, 110, 120, 130)

    readings = []

    for threshold in thresholds:
        image = cv2.threshold(
            gray,
            threshold,
            255,
            cv2.THRESH_BINARY,
        )[1]

        result = {
            "variant": f"psm13_t{threshold}",
            **_ocr(
                image,
                config="--psm 13",
            ),
        }

        readings.append(result)

    numeric = [
        item.get("stack_bb")
        for item in readings
        if item.get("stack_bb") is not None
    ]

    if not numeric:
        return None, 0, readings

    counts = Counter(numeric)
    value, votes = counts.most_common(1)[0]

    # Require agreement across at least three independent threshold
    # segmentations. One or two lucky OCR reads are insufficient.
    if votes < 3:
        return None, votes, readings

    return value, votes, readings


def read_stack_independent_consensus(crop) -> Dict[str, Any]:
    """
    Independently read one stack crop across the fixed-threshold PSM13
    segmentation family.

    This is a perception-only interface. It applies no continuity,
    digit substitution, poker semantics, or canonical-state assumptions.
    """
    _, gray, _ = _prepare_images(crop)

    value, votes, readings = (
        _independent_segmentation_consensus(gray)
    )

    return {
        "stack_bb": (
            float(value)
            if value is not None
            else None
        ),
        "stack_text": (
            f"{float(value):g} BB"
            if value is not None
            else ""
        ),
        "confidence": (
            0.98
            if value is not None and int(votes) >= 3
            else 0.0
        ),
        "votes": int(votes),
        "mode": (
            "independent_segmentation"
            if value is not None and int(votes) >= 3
            else "independent_unresolved"
        ),
        "raw": list(readings or []),
    }


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

    # Disagreement: use Otsu as the correlated-family tiebreaker, but also
    # expose the independent thresholded PSM13 family as candidate evidence.
    #
    # The stack reader does NOT decide which OCR family is authoritative.
    # Canonical continuity belongs to the coordinator.
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

    independent_value, independent_votes, independent_readings = (
        _independent_segmentation_consensus(gray)
    )

    readings = [
        green_result,
        plain_result,
        otsu_result,
        *independent_readings,
    ]

    # Preserve the existing correlated-family resolver behavior for the
    # reader's provisional value. Independent candidates are evidence only.
    value, votes = _resolve([
        green_result,
        plain_result,
        otsu_result,
    ])

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

