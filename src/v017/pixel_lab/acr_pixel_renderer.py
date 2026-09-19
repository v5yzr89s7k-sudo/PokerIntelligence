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

import cv2

from src.v017.pixel_lab.acr_seat_mapper import (
    map_acr_seats,
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

OVERLAY_ABSENT = (
    ROOT
    / "runtime/debug/v017_max_geometry/"
      "geometry_maximized_final_overlay_v2.png"
)

PRESENT_DONORS = {
    "seat_upper_left": SUBSTRATE_6P,
    "seat_top": DEFAULT_SUBSTRATE,
    "seat_upper_right": DEFAULT_SUBSTRATE,
    "seat_mid_right": DEFAULT_SUBSTRATE,
    "seat_lower_right": DEFAULT_SUBSTRATE,
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


def _transplant_hole_cards(
    destination,
    donor,
    *,
    geometry,
    seat,
):
    """
    Generator-side authentic hole-card ROI transplant.

    Only the two production-calibrated hole-card regions are copied.
    """
    result = destination.copy()

    regions = geometry["hole_cards"][seat]

    for card_name in ("card_1", "card_2"):
        rect = regions[card_name]

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


def _load_fold_donors():
    paths = set(PRESENT_DONORS.values())
    paths.update(ABSENT_DONORS.values())

    return {
        path: _load_native(path)
        for path in paths
    }


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

    Each historical calibrated board ROI is independently transformed
    into the corresponding maximized calibrated ROI. No full-frame
    scaling and no production geometry changes.
    """
    result = destination.copy()

    for card_name in BOARD_ORDER:
        old_rect = old_geometry[
            "board"
        ][card_name]

        new_rect = new_geometry[
            "board"
        ][card_name]

        ox = int(old_rect["x"])
        oy = int(old_rect["y"])
        ow = int(old_rect["width"])
        oh = int(old_rect["height"])

        source = donor[
            oy:oy + oh,
            ox:ox + ow,
        ]

        assert source.size > 0

        nw = int(new_rect["width"])
        nh = int(new_rect["height"])

        resized = cv2.resize(
            source,
            (nw, nh),
            interpolation=cv2.INTER_CUBIC,
        )

        nx = int(new_rect["x"])
        ny = int(new_rect["y"])

        result[
            ny:ny + nh,
            nx:nx + nw,
        ] = resized

    return result


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

            image = _transplant_hole_cards(
                image,
                fold_donors[donor_path],
                geometry=geometry,
                seat=seat,
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
