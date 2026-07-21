import cv2


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


def crop(img, rect):
    x, y, w, h = map(
        int,
        [
            rect["x"],
            rect["y"],
            rect["width"],
            rect["height"],
        ],
    )

    return img[y:y + h, x:x + w]


def card_presence_score(card_crop):
    """
    Return the bright-pixel ratio used by the existing deterministic
    card-presence detector.

    A value greater than 0.08 currently means that a card is present.
    """
    if card_crop is None or card_crop.size == 0:
        return 0.0

    gray = cv2.cvtColor(
        card_crop,
        cv2.COLOR_BGR2GRAY,
    )

    return float(
        (gray > 145).mean()
    )


def card_present(card_crop):
    return card_presence_score(card_crop) > 0.08


def cards_visible(frame, card_regions):
    """
    Determine whether both cards are visible in a two-card geometry region.
    """
    if not card_regions:
        return False

    seen = 0

    for rect in card_regions.values():
        if card_present(crop(frame, rect)):
            seen += 1

    return seen >= 2


def seat_card_presence(frame, geometry):
    """
    Evaluate hole-card visibility for every immutable physical seat.

    This is a live visual observation, not the permanent hand roster.
    The result must be frozen at hand initialization before folded cards
    disappear.
    """
    hole_cards = geometry.get("hole_cards") or {}
    results = {}

    for seat in SEAT_ORDER:
        regions = hole_cards.get(seat) or {}

        card_scores = {}

        for card_name, rect in regions.items():
            card_scores[card_name] = round(
                card_presence_score(
                    crop(frame, rect)
                ),
                6,
            )

        visible_count = sum(
            score > 0.08
            for score in card_scores.values()
        )

        results[seat] = {
            "seat": seat,
            "dealt_in": (
                len(card_scores) >= 2
                and visible_count >= 2
            ),
            "visible_card_count": int(
                visible_count
            ),
            "card_scores": card_scores,
            "threshold": 0.08,
        }

    return results


def dealt_in_seats(frame, geometry):
    """
    Return physical seats whose two hole-card regions are visible.
    """
    results = seat_card_presence(
        frame,
        geometry,
    )

    return [
        seat
        for seat in SEAT_ORDER
        if results[seat]["dealt_in"]
    ]


def count_board_cards(frame, geometry):
    count = 0

    for rect in geometry.get(
        "board",
        {},
    ).values():
        if card_present(crop(frame, rect)):
            count += 1

    return count


def hero_cards_visible(frame, geometry):
    hero = (
        geometry.get("hero_cards")
        or geometry.get(
            "hole_cards",
            {},
        ).get("hero", {})
    )

    return cards_visible(
        frame,
        hero,
    )


def opponent_card_back_score(card_crop):
    """
    Detect the red ACR opponent card back.

    This is intentionally separate from the bright face-up Hero-card
    detector because the two visual classes have different properties.
    """
    if card_crop is None or card_crop.size == 0:
        return {
            "present": False,
            "red_ratio": 0.0,
            "strong_red_ratio": 0.0,
            "saturated_ratio": 0.0,
        }

    hsv = cv2.cvtColor(
        card_crop,
        cv2.COLOR_BGR2HSV,
    )

    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    red_hue = (
        (hue <= 12)
        | (hue >= 168)
    )

    red_pixels = (
        red_hue
        & (saturation >= 70)
        & (value >= 35)
    )

    strong_red_pixels = (
        red_hue
        & (saturation >= 120)
        & (value >= 45)
    )

    red_ratio = float(
        red_pixels.mean()
    )

    strong_red_ratio = float(
        strong_red_pixels.mean()
    )

    saturated_ratio = float(
        (saturation >= 70).mean()
    )

    present = bool(
        red_ratio >= 0.25
        and strong_red_ratio >= 0.12
        and saturated_ratio >= 0.45
    )

    return {
        "present": present,
        "red_ratio": red_ratio,
        "strong_red_ratio": strong_red_ratio,
        "saturated_ratio": saturated_ratio,
    }


def opponent_cards_visible(
    frame,
    card_regions,
):
    """
    Return True only when both calibrated opponent card regions contain
    the red ACR card back.
    """
    if not card_regions:
        return False

    results = []

    for card_name in (
        "card_1",
        "card_2",
    ):
        rect = card_regions.get(
            card_name
        )

        if not rect:
            return False

        results.append(
            opponent_card_back_score(
                crop(frame, rect)
            )
        )

    return all(
        result["present"]
        for result in results
    )


def hand_participant_presence(
    frame,
    geometry,
    hero_is_dealt=True,
):
    """
    Observe the currently visible dealt-card state for all physical seats.

    This is not itself the permanent roster. The caller must freeze the
    starting participant set before folds remove opponent card backs.
    """
    hole_cards = (
        geometry.get("hole_cards")
        or {}
    )

    results = {}

    for seat in SEAT_ORDER:
        regions = (
            hole_cards.get(seat)
            or {}
        )

        if seat == "hero":
            dealt_in = bool(
                hero_is_dealt
                and cards_visible(
                    frame,
                    (
                        geometry.get(
                            "hero_cards"
                        )
                        or regions
                    ),
                )
            )

            results[seat] = {
                "seat": seat,
                "dealt_in": dealt_in,
                "source": "hero_face_up",
            }

            continue

        card_results = {}

        for card_name in (
            "card_1",
            "card_2",
        ):
            rect = regions.get(
                card_name
            )

            if not rect:
                continue

            score = opponent_card_back_score(
                crop(frame, rect)
            )

            card_results[card_name] = score

        dealt_in = bool(
            card_results.get(
                "card_1",
                {},
            ).get("present")
            and card_results.get(
                "card_2",
                {},
            ).get("present")
        )

        results[seat] = {
            "seat": seat,
            "dealt_in": dealt_in,
            "source": "opponent_card_back",
            "cards": card_results,
        }

    return results
