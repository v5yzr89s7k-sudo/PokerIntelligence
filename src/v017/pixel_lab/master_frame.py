"""
V0.17 immutable authentic ACR master-frame ownership layer.

GENERATOR SIDE ONLY.

Every generated observer frame begins as a copy of the authentic,
byte-identical ACR master. The master itself is never modified.

Before a frame may cross into observer input, every production-sensitive
visual lane must be explicitly owned by the controlled renderer.

Ownership is structural protection against stale master-hand pixels.
It does NOT supply semantic truth to the observer.
"""

from pathlib import Path
import hashlib
import json

import cv2


ROOT = Path(__file__).resolve().parents[3]

MASTER = (
    ROOT
    / "runtime/pixel_lab/master/"
      "acr_master_8p.png"
)

MASTER_MANIFEST = (
    ROOT
    / "runtime/pixel_lab/master/"
      "master_manifest.json"
)

GEOMETRY_PATH = (
    ROOT
    / "config/v017/"
      "geometry_maximized.json"
)


SEATS = (
    "seat_upper_left",
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
)

BOARD_SLOTS = (
    "flop_1",
    "flop_2",
    "flop_3",
    "turn",
    "river",
)


def _sha256(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def _geometry():
    return json.loads(
        GEOMETRY_PATH.read_text()
    )


def _master_manifest():
    return json.loads(
        MASTER_MANIFEST.read_text()
    )


def load_master_copy():
    """
    Load a fresh copy of the immutable authentic ACR master.

    Refuse to proceed if the file has changed since the manifest was
    created.
    """
    manifest = _master_manifest()

    expected = (
        manifest.get("master_sha256")
        or manifest.get("sha256")
    )

    actual = _sha256(MASTER)

    if expected and actual != expected:
        raise RuntimeError(
            "ACR master hash mismatch: "
            f"expected={expected} "
            f"actual={actual}"
        )

    image = cv2.imread(
        str(MASTER)
    )

    if image is None:
        raise RuntimeError(
            f"cannot read ACR master: {MASTER}"
        )

    if image.shape[:2] != (
        2168,
        3456,
    ):
        raise RuntimeError(
            "unexpected ACR master shape: "
            f"{image.shape}"
        )

    return image.copy()


def required_ownership():
    """
    Return every production-sensitive visual lane that must be
    explicitly controlled before a generated frame may be emitted.
    """
    required = set()

    # Snapshot identity + local stack OCR.
    for seat in SEATS:
        required.add(
            f"seat_identity:{seat}"
        )

        required.add(
            f"stack:{seat}"
        )

    # Opponent/Hero physical card state.
    for seat in SEATS:
        required.add(
            f"hole_cards:{seat}"
        )

    # Dealer search zones must all be controlled so the master's
    # original dealer button cannot survive.
    for seat in SEATS:
        required.add(
            f"dealer:{seat}"
        )

    # Physical commitment evidence.
    for seat in SEATS:
        required.add(
            f"bet:{seat}"
        )

    # Board presence + identity.
    for slot in BOARD_SLOTS:
        required.add(
            f"board:{slot}"
        )

    required.add("pot")

    return frozenset(required)


class MasterFrame:
    """
    Mutable per-frame copy of the immutable authentic master.

    The controlled renderer must explicitly claim every required lane.
    """

    def __init__(self):
        self.image = load_master_copy()
        self.geometry = _geometry()
        self.owned = set()

    def claim(self, lane):
        if lane not in required_ownership():
            raise KeyError(
                f"unknown ownership lane: {lane}"
            )

        self.owned.add(lane)

    def claim_seat_identity(self, seat):
        self.claim(
            f"seat_identity:{seat}"
        )

    def claim_stack(self, seat):
        self.claim(
            f"stack:{seat}"
        )

    def claim_hole_cards(self, seat):
        self.claim(
            f"hole_cards:{seat}"
        )

    def claim_dealer(self, seat):
        self.claim(
            f"dealer:{seat}"
        )

    def claim_bet(self, seat):
        self.claim(
            f"bet:{seat}"
        )

    def claim_board(self, slot):
        self.claim(
            f"board:{slot}"
        )

    def claim_pot(self):
        self.claim("pot")

    def missing(self):
        return sorted(
            required_ownership()
            - self.owned
        )

    def assert_complete(self):
        missing = self.missing()

        if missing:
            raise RuntimeError(
                "master frame ownership incomplete: "
                + ", ".join(missing)
            )

    def emit(self):
        self.assert_complete()
        return self.image.copy()
