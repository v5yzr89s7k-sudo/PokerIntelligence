"""
V0.17 Pixel Lab real-ACR-hand pixel renderer.

PRIVATE GENERATOR SIDE ONLY.

ACR semantic truth is allowed here.  The renderer converts deterministic
TruthFrame state into physical ACR-like pixels.  Generated truth must never
be supplied to FrameHandObserver.

Only rendered PNG bytes may later cross the Pixel Lab isolation wall.
"""

from pathlib import Path
import json
import math

import cv2

from src.v017.pixel_lab.acr_seat_mapper import (
    map_acr_seats,
    mapped_dealer_seat,
)
from src.v017.pixel_lab.test_novel_stack_pixels import (
    build_atlas,
    render_stack_value,
)


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY_PATH = (
    ROOT / "config/v017/geometry_maximized.json"
)

DEFAULT_SUBSTRATE = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_8p.png"
)

SUBSTRATE_6P = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_6p.png"
)

SUBSTRATE_7P = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_7p.png"
)

MAXIMIZED_ABSENT = (
    ROOT
    / "runtime/debug/v017_resolution_ab/"
      "maximized.png"
)

EMPTY_STACK_DONORS = {
    "seat_lower_left": SUBSTRATE_6P,
    "seat_mid_left": MAXIMIZED_ABSENT,
}

OVERLAY_ABSENT = (
    ROOT
    / "runtime/debug/v017_max_geometry/"
      "geometry_maximized_final_overlay_v2.png"
)

PRESENT_DONORS = {
    "seat_upper_left": (
        ROOT
        / "runtime/debug/action_sequence/"
          "20260714_184648/0001_full.png"
    ),
    "seat_top": DEFAULT_SUBSTRATE,
    "seat_upper_right": (
        ROOT
        / "runtime/debug/action_sequence/"
          "20260714_183507/0001_full.png"
    ),
    "seat_mid_right": (
        ROOT
        / "runtime/debug/action_sequence/"
          "20260714_183507/0001_full.png"
    ),
    "seat_lower_right": (
        ROOT
        / "runtime/debug/action_sequence/"
          "20260714_183507/0001_full.png"
    ),
}

ABSENT_DONORS = {
    "seat_upper_left": SUBSTRATE_7P,
    "seat_top": OVERLAY_ABSENT,
    "seat_upper_right": MAXIMIZED_ABSENT,
    "seat_mid_right": MAXIMIZED_ABSENT,
    "seat_lower_right": MAXIMIZED_ABSENT,
}

JULY22_SESSION = (
    ROOT
    / "runtime/debug/action_sequence/"
      "20260722_152155"
)

OLD_GEOMETRY_PATH = (
    ROOT / "config/geometry.json"
)

BOARD_DONORS = {
    0: JULY22_SESSION / "0001_full.png",
    3: JULY22_SESSION / "0052_full.png",
    4: JULY22_SESSION / "0103_full.png",
    5: JULY22_SESSION / "0115_full.png",
}

BOARD_ORDER = (
    "flop_1",
    "flop_2",
    "flop_3",
    "turn",
    "river",
)

DEALER_DONORS = {
    "seat_upper_left": (
        ROOT
        / "runtime/debug/action_sequence/"
          "20260726_105421/0001_full.png"
    ),
}


def load_geometry():
    return json.loads(
        GEOMETRY_PATH.read_text()
    )


def _load_native(path):
    path = Path(path)
    image = cv2.imread(str(path))
    assert image is not None, path
    assert image.shape[:2] == (2168, 3456), (
        path,
        image.shape,
    )
    return image


def _inverse_sensor_rect(
    rect,
    *,
    sensor_size=(934, 696),
    native_size=(3456, 2168),
):
    """
    Return the native pixel footprint covering one canonical sensor ROI.

    canonical_sensor_frame() is a full-frame INTER_AREA resize with no
    crop or translation, so Pixel Lab must place canonical donor pixels
    into this inverse footprint rather than independently calibrated
    maximized card coordinates.
    """
    sensor_w, sensor_h = sensor_size
    native_w, native_h = native_size

    x1 = math.floor(
        float(rect["x"])
        * native_w
        / sensor_w
    )
    y1 = math.floor(
        float(rect["y"])
        * native_h
        / sensor_h
    )

    x2 = math.ceil(
        float(
            rect["x"]
            + rect["width"]
        )
        * native_w
        / sensor_w
    )
    y2 = math.ceil(
        float(
            rect["y"]
            + rect["height"]
        )
        * native_h
        / sensor_h
    )

    return {
        "x": int(x1),
        "y": int(y1),
        "width": int(x2 - x1),
        "height": int(y2 - y1),
    }


def _transplant_hole_cards(
    destination,
    donor,
    *,
    geometry,
    seat,
    donor_geometry=None,
    canonical_donor=False,
):
    """
    Generator-side authentic hole-card ROI transplant.

    Native/maximized donors use maximized calibrated coordinates.

    Historical canonical 934x696 donors use canonical calibrated
    coordinates. Only each authentic card ROI is resized into the
    corresponding maximized target ROI.
    """
    result = destination.copy()

    target_regions = (
        geometry["hole_cards"][seat]
    )

    source_geometry = (
        geometry
        if donor_geometry is None
        else donor_geometry
    )

    source_regions = (
        source_geometry[
            "hole_cards"
        ][seat]
    )

    for card_name in (
        "card_1",
        "card_2",
    ):
        source_rect = (
            source_regions[card_name]
        )

        if canonical_donor:
            target_rect = _inverse_sensor_rect(
                source_rect
            )
        else:
            target_rect = (
                target_regions[card_name]
            )

        sx = int(source_rect["x"])
        sy = int(source_rect["y"])
        sw = int(source_rect["width"])
        sh = int(source_rect["height"])

        source = donor[
            sy:sy + sh,
            sx:sx + sw,
        ]

        assert source.size > 0, (
            seat,
            card_name,
            source_rect,
            donor.shape,
        )

        tw = int(target_rect["width"])
        th = int(target_rect["height"])

        if source.shape[:2] != (
            th,
            tw,
        ):
            source = cv2.resize(
                source,
                (tw, th),
                interpolation=cv2.INTER_CUBIC,
            )

        tx = int(target_rect["x"])
        ty = int(target_rect["y"])

        result[
            ty:ty + th,
            tx:tx + tw,
        ] = source

    return result

def _transplant_stack_region(
    destination,
    donor,
    *,
    geometry,
    seat,
):
    """
    Generator-side authentic stack-region transplant.

    Used for physically empty seats so production occupancy sees the
    same absence evidence it sees on real ACR material.
    """
    result = destination.copy()

    rect = geometry["stack_regions"][seat]

    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    result[
        y:y + h,
        x:x + w,
    ] = donor[
        y:y + h,
        x:x + w,
    ]

    return result


def _load_empty_stack_donors():
    return {
        seat: _load_native(path)
        for seat, path
        in EMPTY_STACK_DONORS.items()
    }


def _load_fold_donors():
    paths = set(
        PRESENT_DONORS.values()
    )
    paths.update(
        ABSENT_DONORS.values()
    )

    donors = {}

    for path in paths:
        image = cv2.imread(
            str(path)
        )

        assert image is not None, path

        assert image.shape[:2] in {
            (2168, 3456),
            (696, 934),
        }, (
            path,
            image.shape,
        )

        donors[path] = image

    return donors

def _old_geometry():
    return json.loads(
        OLD_GEOMETRY_PATH.read_text()
    )


def _load_old_board_donor(path):
    image = cv2.imread(str(path))
    assert image is not None, path

    if image.shape[:2] != (696, 934):
        image = cv2.resize(
            image,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    return image


def _board_count_for_truth(truth_frame):
    count = len(truth_frame.board)
    assert count in (0, 3, 4, 5), (
        truth_frame.sequence,
        truth_frame.street,
        truth_frame.board,
    )
    return count


def _transplant_board(
    destination,
    donor,
    *,
    old_geometry,
    new_geometry,
):
    """
    Generator-side authentic board-presence transplant.

    Board donors are historical canonical 934x696 pixels.

    canonical_sensor_frame() is a pure full-frame resize, so each
    canonical board ROI must be rendered into its exact inverse native
    footprint. Independently calibrated maximized board coordinates
    are not the inverse sensor transform and must not own placement.
    """
    result = destination.copy()

    for card_name in BOARD_ORDER:
        source_rect = old_geometry[
            "board"
        ][card_name]

        target_rect = _inverse_sensor_rect(
            source_rect
        )

        sx = int(source_rect["x"])
        sy = int(source_rect["y"])
        sw = int(source_rect["width"])
        sh = int(source_rect["height"])

        source = donor[
            sy:sy + sh,
            sx:sx + sw,
        ]

        assert source.size > 0, (
            card_name,
            source_rect,
            donor.shape,
        )

        tw = int(target_rect["width"])
        th = int(target_rect["height"])

        source = cv2.resize(
            source,
            (tw, th),
            interpolation=cv2.INTER_CUBIC,
        )

        tx = int(target_rect["x"])
        ty = int(target_rect["y"])

        assert (
            tx >= 0
            and ty >= 0
            and tx + tw <= result.shape[1]
            and ty + th <= result.shape[0]
        ), (
            card_name,
            target_rect,
            result.shape,
        )

        result[
            ty:ty + th,
            tx:tx + tw,
        ] = source

    return result

def _transplant_dealer_button(
    destination,
    donor,
    *,
    seat,
    old_geometry,
):
    """
    Generator-side authentic dealer-button transplant.

    Dealer detection operates in canonical 934x696 coordinates.
    The donor is canonical. Only the selected dealer search zone is
    transformed into the native 3456x2168 rendered frame.
    """
    result = destination.copy()

    zone = old_geometry[
        "dealer_button_zones"
    ][seat]

    if isinstance(zone, list):
        zone = zone[0]

    cx = int(zone["x"])
    cy = int(zone["y"])
    cw = int(zone["width"])
    ch = int(zone["height"])

    patch = donor[
        cy:cy + ch,
        cx:cx + cw,
    ]

    assert patch.size > 0

    native_h, native_w = result.shape[:2]

    sx = native_w / 934.0
    sy = native_h / 696.0

    x1 = round(cx * sx)
    y1 = round(cy * sy)
    x2 = round((cx + cw) * sx)
    y2 = round((cy + ch) * sy)

    patch = cv2.resize(
        patch,
        (x2 - x1, y2 - y1),
        interpolation=cv2.INTER_CUBIC,
    )

    result[
        y1:y2,
        x1:x2,
    ] = patch

    return result

def _load_dealer_donors():
    donors = {}

    for seat, path in DEALER_DONORS.items():
        image = cv2.imread(str(path))
        assert image is not None, path
        assert image.shape[:2] == (696, 934), (
            path,
            image.shape,
        )
        donors[seat] = image

    return donors


def _load_board_donors():
    return {
        count: _load_old_board_donor(path)
        for count, path in BOARD_DONORS.items()
    }


def _truth_by_name(frame):
    return {
        row.name: row
        for row in frame.players
        if not row.sitting_out
    }


def _player_by_name(hand):
    return {
        row.name: row
        for row in hand.players
        if not row.sitting_out
    }


def _stack_bb(stack, big_blind):
    return float(stack) / float(big_blind)


def render_truth_frame(
    *,
    hand,
    truth_frame,
    substrate,
    geometry,
    atlas,
    fold_donors,
    empty_stack_donors,
    dealer_donors,
    board_donors,
    old_geometry,
):
    """
    Render one deterministic truth snapshot into physical pixels.

    Initial scope is intentionally narrow:
      * authentic native 3456x2168 substrate;
      * real ACR -> physical seat mapping;
      * deterministic per-seat stack state.

    Card/fold/board primitives are added through their already-proven
    physical primitives after this first real-hand stack progression
    boundary is locked.
    """
    image = substrate.copy()

    dealer_seat = mapped_dealer_seat(
        hand
    )

    dealer_donor = dealer_donors.get(
        dealer_seat
    )

    if dealer_donor is None:
        raise RuntimeError(
            "no physical dealer donor for "
            f"{dealer_seat}"
        )

    image = _transplant_dealer_button(
        image,
        dealer_donor,
        seat=dealer_seat,
        old_geometry=old_geometry,
    )

    board_count = _board_count_for_truth(
        truth_frame
    )

    image = _transplant_board(
        image,
        board_donors[board_count],
        old_geometry=old_geometry,
        new_geometry=geometry,
    )

    seat_map = map_acr_seats(hand)
    players = _player_by_name(hand)
    occupied_seats = set(
        seat_map.values()
    )

    for seat, donor in empty_stack_donors.items():
        if seat not in occupied_seats:
            image = _transplant_stack_region(
                image,
                donor,
                geometry=geometry,
                seat=seat,
            )

    truth = _truth_by_name(truth_frame)

    rendered = []

    for name, state in truth.items():
        source_player = players[name]
        acr_seat = int(source_player.seat_number)
        seat = seat_map[acr_seat]

        stack_bb = _stack_bb(
            state.stack,
            hand.big_blind,
        )

        render_stack_value(
            image,
            geometry=geometry,
            seat=seat,
            value=stack_bb,
            atlas=atlas,
        )

        # Opponent hole cards are a physical signal.
        #
        # Every target opponent begins from an authentic detector-positive
        # ACR card-back donor. Once private truth marks that player folded,
        # only the two calibrated hole-card ROIs are replaced by an
        # authentic detector-negative donor.
        #
        # Hero is intentionally excluded here. Hero face-up cards have a
        # separate physical class and lifecycle.
        if seat != "hero":
            donor_path = (
                ABSENT_DONORS[seat]
                if state.folded
                else PRESENT_DONORS[seat]
            )

            donor = fold_donors[
                donor_path
            ]

            canonical_donor = (
                donor.shape[:2]
                == (696, 934)
            )

            donor_geometry = (
                old_geometry
                if canonical_donor
                else geometry
            )

            image = _transplant_hole_cards(
                image,
                donor,
                geometry=geometry,
                seat=seat,
                donor_geometry=donor_geometry,
                canonical_donor=canonical_donor,
            )

        rendered.append(
            {
                "name": name,
                "acr_seat": acr_seat,
                "seat": seat,
                "stack_bb": round(stack_bb, 6),
                "folded": bool(state.folded),
            }
        )

    return image, tuple(rendered)


def render_hand_progression(
    *,
    hand,
    truth_frames,
    output_dir,
    substrate_path=DEFAULT_SUBSTRATE,
):
    """
    Render an entire deterministic ACR truth timeline.

    This function is generator-side.  Its returned metadata is private
    generator truth and must not cross into observer input.
    """
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    substrate = _load_native(
        substrate_path
    )

    geometry = load_geometry()

    # Reuse the already-proven authentic stack glyph extraction.
    atlas = build_atlas(substrate)
    fold_donors = _load_fold_donors()
    empty_stack_donors = (
        _load_empty_stack_donors()
    )
    dealer_donors = _load_dealer_donors()
    board_donors = _load_board_donors()
    old_geometry = _old_geometry()

    manifest_frames = []

    for truth_frame in truth_frames:
        image, rendered_players = (
            render_truth_frame(
                hand=hand,
                truth_frame=truth_frame,
                substrate=substrate,
                geometry=geometry,
                atlas=atlas,
                fold_donors=fold_donors,
                empty_stack_donors=
                    empty_stack_donors,
                dealer_donors=dealer_donors,
                board_donors=board_donors,
                old_geometry=old_geometry,
            )
        )

        filename = (
            f"frame_{truth_frame.sequence:04d}.png"
        )
        path = output_dir / filename

        assert cv2.imwrite(
            str(path),
            image,
        ), path

        manifest_frames.append(
            {
                "sequence": truth_frame.sequence,
                "filename": filename,
                "street": truth_frame.street,
                "cause_actor": truth_frame.cause_actor,
                "cause_action": truth_frame.cause_action,
                "board": list(truth_frame.board),
                "pot": truth_frame.pot,
                "players": list(rendered_players),
            }
        )

    private_manifest = {
        "hand_id": hand.hand_id,
        "frame_count": len(manifest_frames),
        "width": 3456,
        "height": 2168,
        "frames": manifest_frames,
    }

    manifest_path = (
        output_dir / "private_truth_manifest.json"
    )
    manifest_path.write_text(
        json.dumps(
            private_manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    return {
        "output_dir": output_dir,
        "manifest_path": manifest_path,
        "frames": tuple(
            output_dir / row["filename"]
            for row in manifest_frames
        ),
        "private_manifest": private_manifest,
    }
