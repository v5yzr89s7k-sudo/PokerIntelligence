"""
V0.17 Pixel Lab generic physical board deck.

PRIVATE GENERATOR SIDE ONLY.

Maps semantic card identities to authentic physical ACR card-face pixels.

Selection is generic and deterministic:

* evaluate every authentic Hero-library sample for an identity;
* resize it into every canonical board slot;
* require unchanged production board_card_present() in all five slots;
* choose the candidate with the strongest worst-slot physical margin;
* break ties by filename.

Authentic board-derived overrides are allowed only as library data, never as
renderer branches. 9c and Qh currently require such authentic board sources.

Ad intentionally remains unavailable until an authentic donor passes the same
unchanged five-slot production-presence contract.
"""

from pathlib import Path

import cv2

from src.events.detectors.card_presence import (
    board_card_present,
    card_presence_score,
)


ROOT = Path(__file__).resolve().parents[3]

CARD_LIBRARY = (
    ROOT / "runtime/hero_card_library"
)

BOARD_SOURCE_LIBRARY = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "missing_card_board_donor_probe"
)

BOARD_SOURCE_OVERRIDES = {
    "9c": BOARD_SOURCE_LIBRARY / "9c_source.png",
    "Qh": BOARD_SOURCE_LIBRARY / "Qh_source.png",
}

BOARD_ORDER = (
    "flop_1",
    "flop_2",
    "flop_3",
    "turn",
    "river",
)

RANKS = "23456789TJQKA"
SUITS = "cdhs"

LEGAL_CARDS = frozenset(
    rank + suit
    for rank in RANKS
    for suit in SUITS
)


def _normalize_card(card):
    value = str(card).strip()

    if len(value) < 2:
        raise ValueError(
            f"invalid card identity: {card!r}"
        )

    rank = value[:-1].upper()
    suit = value[-1].lower()

    if rank == "10":
        rank = "T"

    normalized = rank + suit

    if normalized not in LEGAL_CARDS:
        raise ValueError(
            f"invalid card identity: {card!r}"
        )

    return normalized


def _load(path):
    path = Path(path)

    image = cv2.imread(str(path))

    if image is None:
        raise RuntimeError(
            f"could not load physical card donor: {path}"
        )

    return image


def _slot_face(
    source,
    rect,
):
    return cv2.resize(
        source,
        (
            int(rect["width"]),
            int(rect["height"]),
        ),
        interpolation=cv2.INTER_CUBIC,
    )


def _candidate_result(
    source,
    *,
    geometry,
):
    slot_results = []

    for slot in BOARD_ORDER:
        rect = geometry["board"][slot]

        face = _slot_face(
            source,
            rect,
        )

        score = float(
            card_presence_score(face)
        )

        present = bool(
            board_card_present(face)
        )

        slot_results.append(
            {
                "slot": slot,
                "present": present,
                "score": score,
            }
        )

    return {
        "all_pass": all(
            row["present"]
            for row in slot_results
        ),
        "worst_score": min(
            row["score"]
            for row in slot_results
        ),
        "slots": tuple(slot_results),
    }


def select_card_donor(
    card,
    *,
    geometry,
):
    """
    Return deterministic authentic donor metadata for one card identity.

    Raises RuntimeError if no available authentic donor satisfies unchanged
    production board presence in all five canonical board slots.
    """

    card = _normalize_card(card)

    override = BOARD_SOURCE_OVERRIDES.get(card)

    if override is not None:
        source = _load(override)

        result = _candidate_result(
            source,
            geometry=geometry,
        )

        if not result["all_pass"]:
            raise RuntimeError(
                "authentic board-source override failed "
                f"five-slot presence contract: card={card} "
                f"path={override} "
                f"worst={result['worst_score']:.6f}"
            )

        return {
            "card": card,
            "path": override,
            "source_kind": "authentic_board",
            **result,
        }

    directory = CARD_LIBRARY / card

    candidates = []

    for path in sorted(directory.glob("*.png")):
        source = _load(path)

        result = _candidate_result(
            source,
            geometry=geometry,
        )

        candidates.append(
            {
                "card": card,
                "path": path,
                "source_kind": "authentic_hero",
                **result,
            }
        )

    passing = [
        row
        for row in candidates
        if row["all_pass"]
    ]

    if not passing:
        best = (
            max(
                candidates,
                key=lambda row: (
                    row["worst_score"],
                    str(row["path"]),
                ),
            )
            if candidates
            else None
        )

        detail = (
            "none"
            if best is None
            else (
                f"{best['path']} "
                f"worst={best['worst_score']:.6f}"
            )
        )

        raise RuntimeError(
            "no authentic five-slot board donor: "
            f"card={card} best={detail}"
        )

    passing.sort(
        key=lambda row: (
            -row["worst_score"],
            str(row["path"]),
        )
    )

    return passing[0]


def load_card_face(
    card,
    *,
    geometry,
):
    """
    Load the deterministic authentic physical donor for one card identity.
    """

    selected = select_card_donor(
        card,
        geometry=geometry,
    )

    return _load(
        selected["path"]
    )


def render_card(
    image,
    card,
    slot,
    *,
    geometry,
):
    """
    Render one authentic card identity into one canonical board-slot image.

    This primitive operates in canonical 934x696 geometry. Native placement
    into the inverse production-sensor footprint remains the responsibility
    of acr_pixel_renderer.
    """

    if slot not in BOARD_ORDER:
        raise ValueError(
            f"invalid board slot: {slot!r}"
        )

    source = load_card_face(
        card,
        geometry=geometry,
    )

    rect = geometry["board"][slot]

    face = _slot_face(
        source,
        rect,
    )

    if not board_card_present(face):
        raise RuntimeError(
            "selected physical donor failed target slot: "
            f"card={card} slot={slot}"
        )

    result = image.copy()

    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    result[
        y:y + h,
        x:x + w,
    ] = face

    return result
