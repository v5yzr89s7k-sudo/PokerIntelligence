"""
Build the immutable generator-side ACR master table.

The master contains authentic ACR pixels at native 3456x2168 resolution.
It is NOT observer input and contains no simulator truth.

V1 neutralizes only observer-sensitive regions for which authentic,
aligned neutral source pixels are already available/provable.

The controlled-hand renderer is NOT modified by this module.
"""

from pathlib import Path
import hashlib
import json

import cv2


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY_PATH = (
    ROOT / "config/v017/geometry_maximized.json"
)

BASE = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_8p.png"
)

# Authentic native/canonical sources already used by the proven
# Pixel Lab renderer. These sources provide only visual material.
EMPTY_BOARD_SOURCE = (
    ROOT
    / "runtime/debug/action_sequence/"
      "20260722_152155/0001_full.png"
)

HERO_ABSENT_SOURCE = (
    ROOT
    / "runtime/debug/v017_max_geometry/"
      "geometry_maximized_corrected_overlay.png"
)

OUT_DIR = (
    ROOT
    / "runtime/pixel_lab/master"
)

MASTER = (
    OUT_DIR / "acr_master_8p.png"
)

MANIFEST = (
    OUT_DIR / "master_manifest.json"
)


def _load(path):
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(
            f"could not load {path}"
        )
    return image


def _geometry():
    return json.loads(
        GEOMETRY_PATH.read_text()
    )


def _copy_rect(
    destination,
    source,
    rect,
):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    if source.shape[:2] != destination.shape[:2]:
        raise ValueError(
            "direct native transplant requires "
            "identical dimensions: "
            f"{source.shape} vs "
            f"{destination.shape}"
        )

    destination[
        y:y+h,
        x:x+w,
    ] = source[
        y:y+h,
        x:x+w,
    ]


def _native_from_canonical(
    canonical,
    *,
    native_shape,
):
    native_h, native_w = native_shape[:2]

    return cv2.resize(
        canonical,
        (native_w, native_h),
        interpolation=cv2.INTER_CUBIC,
    )


def _sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def build():
    g = _geometry()

    base = _load(BASE)

    if base.shape[:2] != (
        2168,
        3456,
    ):
        raise RuntimeError(
            f"unexpected base shape "
            f"{base.shape}"
        )

    master = base.copy()

    neutralized = []

    # ---------------------------------------------------------
    # BOARD + POT
    #
    # The known empty-board ACR frame is canonical 934x696.
    # Scale the complete authentic frame into native coordinates
    # once, then transplant ONLY the relevant production ROIs.
    # ---------------------------------------------------------

    empty_board = _load(
        EMPTY_BOARD_SOURCE
    )

    if empty_board.shape[:2] == (
        696,
        934,
    ):
        empty_board = (
            _native_from_canonical(
                empty_board,
                native_shape=master.shape,
            )
        )

    if empty_board.shape[:2] != (
        2168,
        3456,
    ):
        raise RuntimeError(
            "unexpected empty-board source "
            f"shape {empty_board.shape}"
        )

    for name, rect in g[
        "board"
    ].items():
        _copy_rect(
            master,
            empty_board,
            rect,
        )

        neutralized.append(
            f"board:{name}"
        )

    pot = g["pot_region"]

    if (
        isinstance(pot, dict)
        and "x" not in pot
    ):
        pot_items = pot.items()
    else:
        pot_items = (
            ("main_pot", pot),
        )

    for name, rect in pot_items:
        _copy_rect(
            master,
            empty_board,
            rect,
        )

        neutralized.append(
            f"pot:{name}"
        )

    # ---------------------------------------------------------
    # BET REGIONS
    #
    # Use the same known no-voluntary-action frame. We will
    # subsequently validate every bet ROI with the unchanged
    # production detector. A detector-positive master is rejected.
    # ---------------------------------------------------------

    for seat, rect in g[
        "bet_regions"
    ].items():
        _copy_rect(
            master,
            empty_board,
            rect,
        )

        neutralized.append(
            f"bet:{seat}"
        )

    # ---------------------------------------------------------
    # HERO CARDS
    #
    # Authentic maximized detector-negative Hero-card pixels.
    # ---------------------------------------------------------

    hero_absent = _load(
        HERO_ABSENT_SOURCE
    )

    if hero_absent.shape[:2] != (
        2168,
        3456,
    ):
        raise RuntimeError(
            "unexpected hero-absent source "
            f"shape {hero_absent.shape}"
        )

    for name, rect in g[
        "hero_cards"
    ].items():
        _copy_rect(
            master,
            hero_absent,
            rect,
        )

        neutralized.append(
            f"hero_cards:{name}"
        )

    # ---------------------------------------------------------
    # DEALER
    #
    # We cannot safely claim arbitrary donor pixels are neutral
    # merely because they look like felt. V1 therefore clears each
    # dealer search zone from the empty-board source and REQUIRES
    # the unchanged production dealer detector to reject the result.
    # ---------------------------------------------------------

    for seat, zones in g[
        "dealer_button_zones"
    ].items():
        if not isinstance(
            zones,
            list,
        ):
            zones = [zones]

        for index, rect in enumerate(
            zones
        ):
            _copy_rect(
                master,
                empty_board,
                rect,
            )

            neutralized.append(
                f"dealer:{seat}:{index}"
            )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not cv2.imwrite(
        str(MASTER),
        master,
    ):
        raise RuntimeError(
            f"could not write {MASTER}"
        )

    manifest = {
        "purpose": (
            "Immutable authentic ACR "
            "generator-side master table."
        ),
        "observer_input": False,
        "immutable": True,
        "version": 1,
        "width": 3456,
        "height": 2168,
        "base": str(
            BASE.relative_to(ROOT)
        ),
        "neutral_sources": {
            "board_pot_bet_dealer": str(
                EMPTY_BOARD_SOURCE
                .relative_to(ROOT)
            ),
            "hero_cards": str(
                HERO_ABSENT_SOURCE
                .relative_to(ROOT)
            ),
        },
        "neutralized": neutralized,
        "intentionally_not_yet_neutralized": [
            "seat/nameplate visual state",
            "stack_regions",
            "opponent_hole_cards",
        ],
        "sha256": _sha256(MASTER),
    }

    MANIFEST.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    return manifest


def main():
    manifest = build()

    print(
        "===== ACR MASTER TABLE V1 ====="
    )

    print(
        "master =",
        MASTER,
    )

    print(
        "manifest =",
        MANIFEST,
    )

    print(
        "sha256 =",
        manifest["sha256"],
    )

    print(
        "neutralized =",
        len(
            manifest["neutralized"]
        ),
    )

    print()
    print(
        "NOT CONNECTED TO SIMULATOR"
    )


if __name__ == "__main__":
    main()
