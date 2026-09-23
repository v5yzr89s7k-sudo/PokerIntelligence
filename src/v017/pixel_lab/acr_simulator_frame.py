"""
Private ACR physical simulator renderer.

GENERATOR SIDE ONLY.

The complete table image is constructed from drawing primitives and
private ACR simulation state.

No full-table PNG, captured ACR frame, donor hand, truth manifest, or
production-observer state is read here.

Only the completed image may cross the simulator/observer isolation wall.
"""

from pathlib import Path
import json
import math

import cv2
import numpy as np

from src.v017.pixel_lab.master_frame import (
    MasterFrame,
)
from src.v017.pixel_lab.master_player_renderer import (
    render_master_player,
)
from src.v017.pixel_lab.test_novel_stack_pixels import (
    build_atlas,
)
from src.v017.pixel_lab.acr_seat_mapper import (
    map_acr_seats,
)


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY_PATH = (
    ROOT / "config/v017/geometry_maximized.json"
)

WIDTH = 3456
HEIGHT = 2168

BACKGROUND = (18, 18, 20)
RAIL = (42, 45, 48)
RAIL_EDGE = (95, 100, 115)
FELT = (36, 108, 55)
FELT_EDGE = (48, 132, 68)
PLATE = (42, 45, 47)
PLATE_EDGE = (78, 82, 84)

NAME_COLOR = (225, 235, 235)

# Must remain inside production's green HSV family.
STACK_COLOR = (90, 235, 105)

CARD_BORDER = (225, 225, 225)
CARD_BACK = (60, 50, 145)
CARD_BACK_INNER = (85, 68, 180)


def load_geometry():
    return json.loads(
        GEOMETRY_PATH.read_text()
    )


def build_blank_table():
    """
    Fresh table pixels. No image input of any kind.
    """

    image = np.zeros(
        (HEIGHT, WIDTH, 3),
        dtype=np.uint8,
    )

    image[:] = BACKGROUND

    center = (
        WIDTH // 2,
        1080,
    )

    # Outer poker-table body.
    cv2.ellipse(
        image,
        center,
        (1500, 735),
        0,
        0,
        360,
        RAIL,
        -1,
        cv2.LINE_AA,
    )

    # Rail edge.
    cv2.ellipse(
        image,
        center,
        (1435, 680),
        0,
        0,
        360,
        RAIL_EDGE,
        18,
        cv2.LINE_AA,
    )

    # Felt.
    cv2.ellipse(
        image,
        center,
        (1365, 625),
        0,
        0,
        360,
        FELT,
        -1,
        cv2.LINE_AA,
    )

    cv2.ellipse(
        image,
        center,
        (1090, 440),
        0,
        0,
        360,
        FELT_EDGE,
        4,
        cv2.LINE_AA,
    )

    return image


def _fit_text(
    text,
    max_width,
    *,
    font,
    base_scale,
    thickness,
):
    scale = float(base_scale)

    while scale >= 0.35:
        (width, _), _ = cv2.getTextSize(
            text,
            font,
            scale,
            thickness,
        )

        if width <= max_width:
            return scale

        scale -= 0.05

    return 0.35


def _center_text(
    image,
    text,
    *,
    center_x,
    baseline_y,
    max_width,
    font,
    base_scale,
    thickness,
    color,
):
    scale = _fit_text(
        text,
        max_width,
        font=font,
        base_scale=base_scale,
        thickness=thickness,
    )

    (width, _), _ = cv2.getTextSize(
        text,
        font,
        scale,
        thickness,
    )

    cv2.putText(
        image,
        text,
        (
            int(center_x - width / 2),
            int(baseline_y),
        ),
        font,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def _draw_card_back(
    image,
    rect,
):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    cv2.rectangle(
        image,
        (x, y),
        (x + w, y + h),
        CARD_BORDER,
        -1,
    )

    margin = max(
        5,
        int(min(w, h) * 0.06),
    )

    cv2.rectangle(
        image,
        (
            x + margin,
            y + margin,
        ),
        (
            x + w - margin,
            y + h - margin,
        ),
        CARD_BACK,
        -1,
    )

    cv2.rectangle(
        image,
        (
            x + margin * 2,
            y + margin * 2,
        ),
        (
            x + w - margin * 2,
            y + h - margin * 2,
        ),
        CARD_BACK_INNER,
        3,
    )


def _draw_player(
    image,
    *,
    seat,
    name,
    stack_bb,
    geometry,
    is_hero,
):
    seat_rect = geometry[
        "seat_regions"
    ][seat]

    stack_rect = geometry[
        "stack_regions"
    ][seat]

    sx = int(seat_rect["x"])
    sy = int(seat_rect["y"])
    sw = int(seat_rect["width"])
    sh = int(seat_rect["height"])

    # Visible nameplate.
    plate_y1 = sy + int(sh * 0.40)
    plate_y2 = sy + int(sh * 0.70)

    cv2.rectangle(
        image,
        (sx, plate_y1),
        (sx + sw, plate_y2),
        PLATE,
        -1,
    )

    cv2.rectangle(
        image,
        (sx, plate_y1),
        (sx + sw, plate_y2),
        PLATE_EDGE,
        2,
    )

    _center_text(
        image,
        name,
        center_x=sx + sw / 2,
        baseline_y=(
            plate_y1
            + int(
                (plate_y2 - plate_y1)
                * 0.70
            )
        ),
        max_width=sw - 24,
        font=cv2.FONT_HERSHEY_SIMPLEX,
        base_scale=1.05,
        thickness=2,
        color=NAME_COLOR,
    )

    # Stack text is drawn inside the exact calibrated production stack
    # region. Keep a dark local background and high-saturation green text.
    x = int(stack_rect["x"])
    y = int(stack_rect["y"])
    w = int(stack_rect["width"])
    h = int(stack_rect["height"])

    text = f"{float(stack_bb):.2f} BB"

    # Native production stack crops are 432x174. Put the baseline in
    # the same lower-middle band the production OCR examines.
    stack_y1 = y + 76
    stack_y2 = y + 158

    cv2.rectangle(
        image,
        (
            x + 20,
            stack_y1,
        ),
        (
            x + w - 20,
            stack_y2,
        ),
        PLATE,
        -1,
    )

    _center_text(
        image,
        text,
        center_x=x + w / 2,
        baseline_y=y + 137,
        max_width=w - 55,
        font=cv2.FONT_HERSHEY_SIMPLEX,
        base_scale=1.28,
        thickness=3,
        color=STACK_COLOR,
    )

    # Opponent card backs are physical presence only. Hero cards are
    # intentionally added in a later simulator milestone.
    if not is_hero:
        cards = geometry[
            "hole_cards"
        ][seat]

        _draw_card_back(
            image,
            cards["card_1"],
        )

        _draw_card_back(
            image,
            cards["card_2"],
        )


def _load_sprite(path):
    """
    Load one isolated visual primitive.

    Permitted:
      card face
      dealer button

    Forbidden:
      table screenshot
      captured frame
      donor hand
    """
    path = Path(path)

    image = cv2.imread(
        str(path),
        cv2.IMREAD_UNCHANGED,
    )

    if image is None:
        raise FileNotFoundError(path)

    return image


def _paste_scaled_sprite(
    image,
    sprite,
    rect,
    *,
    inset_fraction=0.0,
):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    inset_x = int(
        w * inset_fraction
    )
    inset_y = int(
        h * inset_fraction
    )

    x += inset_x
    y += inset_y
    w -= 2 * inset_x
    h -= 2 * inset_y

    if w <= 0 or h <= 0:
        raise ValueError(
            f"invalid sprite target: {rect}"
        )

    source = sprite

    if source.ndim == 2:
        source = cv2.cvtColor(
            source,
            cv2.COLOR_GRAY2BGRA,
        )

    if (
        source.ndim == 3
        and source.shape[2] == 3
    ):
        source = cv2.cvtColor(
            source,
            cv2.COLOR_BGR2BGRA,
        )

    resized = cv2.resize(
        source,
        (w, h),
        interpolation=cv2.INTER_AREA,
    )

    rgb = resized[:, :, :3]
    alpha = resized[:, :, 3]

    # Many isolated crops have no useful alpha channel. Treat a fully
    # opaque crop as a normal rectangular sprite.
    if int(alpha.min()) == 255:
        image[
            y:y+h,
            x:x+w,
        ] = rgb
        return

    a = (
        alpha.astype(np.float32)
        / 255.0
    )[:, :, None]

    target = image[
        y:y+h,
        x:x+w,
    ].astype(np.float32)

    blended = (
        rgb.astype(np.float32) * a
        + target * (1.0 - a)
    )

    image[
        y:y+h,
        x:x+w,
    ] = blended.astype(np.uint8)


def _draw_dealer_button(
    image,
    *,
    seat,
    geometry,
):
    """
    Render dealer evidence as the exact inverse of production.

    Production:
        native 3456x2168
            -> canonical 934x696
            -> search canonical dealer zone
            -> template match calibrated canonical template

    Simulator:
        calibrated canonical template
            -> place at center of selected canonical dealer zone
            -> inverse-scale that exact canonical patch into native pixels

    No simulator-specific dealer coordinates are maintained.
    """
    template_path = (
        ROOT
        / "assets/templates/"
          "dealer_button_calibrated.png"
    )

    template = cv2.imread(
        str(template_path)
    )

    if template is None:
        raise FileNotFoundError(
            template_path
        )

    # Dealer detector itself uses config/geometry.json after converting
    # native input to canonical 934x696. Therefore use that SAME geometry
    # as the dealer authority, not geometry_maximized.json.
    canonical_geometry = json.loads(
        (
            ROOT / "config/geometry.json"
        ).read_text()
    )

    zones = canonical_geometry[
        "dealer_button_zones"
    ][seat]

    if not isinstance(zones, list):
        zones = [zones]

    # Deterministically use the first legitimate production zone.
    zone = zones[0]

    zx = int(zone["x"])
    zy = int(zone["y"])
    zw = int(zone["width"])
    zh = int(zone["height"])

    th, tw = template.shape[:2]

    if tw > zw or th > zh:
        raise ValueError(
            "dealer template larger than production zone: "
            f"template={tw}x{th} zone={zw}x{zh}"
        )

    # Center the exact calibrated template inside the exact production
    # canonical search zone.
    canonical_x = (
        zx
        + (zw - tw) // 2
    )

    canonical_y = (
        zy
        + (zh - th) // 2
    )

    native_h, native_w = (
        image.shape[:2]
    )

    sx = native_w / 934.0
    sy = native_h / 696.0

    # Inverse-map the exact canonical template footprint.
    x1 = round(
        canonical_x * sx
    )
    y1 = round(
        canonical_y * sy
    )
    x2 = round(
        (canonical_x + tw) * sx
    )
    y2 = round(
        (canonical_y + th) * sy
    )

    assert 0 <= x1 < x2 <= native_w
    assert 0 <= y1 < y2 <= native_h

    native_template = cv2.resize(
        template,
        (
            x2 - x1,
            y2 - y1,
        ),
        interpolation=cv2.INTER_CUBIC,
    )

    image[
        y1:y2,
        x1:x2,
    ] = native_template


def _draw_hero_cards(
    image,
    *,
    cards,
    geometry,
):
    if len(cards) != 2:
        raise ValueError(
            f"expected two Hero cards: {cards}"
        )

    regions = geometry[
        "hero_cards"
    ]

    for card, key in zip(
        cards,
        ("card_1", "card_2"),
    ):
        samples = sorted(
            (
                ROOT
                / "runtime/hero_card_library"
                / card
            ).glob("*.png")
        )

        if not samples:
            raise FileNotFoundError(
                f"no isolated card asset: {card}"
            )

        sprite = _load_sprite(
            samples[0]
        )

        _paste_scaled_sprite(
            image,
            sprite,
            regions[key],
        )


def render_starting_table(
    *,
    hand,
    state,
    show_dealer=True,
    show_hero_cards=True,
):
    frame = MasterFrame()
    image = frame.image
    geometry = frame.geometry
    atlas = build_atlas(image)

    seat_map = map_acr_seats(
        hand
    )

    state_players = {
        player.name: player
        for player in state.players
    }

    for player in hand.players:
        seat = seat_map[
            int(player.seat_number)
        ]

        sim_player = state_players[
            player.name
        ]

        render_master_player(
            frame,
            seat=seat,
            name=player.name,
            stack_bb=sim_player.stack_bb,
            atlas=atlas,
        )

    if show_dealer:
        dealer_seat = seat_map[
            int(state.button_seat)
        ]

        _draw_dealer_button(
            image,
            seat=dealer_seat,
            geometry=geometry,
        )

    if show_hero_cards:
        _draw_hero_cards(
            image,
            cards=state.hero_cards,
            geometry=geometry,
        )

    return image


def _draw_simple_card_face(
    image,
    *,
    card,
    rect,
):
    """
    Synthetic card face placed strictly inside production geometry.

    Identity text is generator truth. Production receives pixels only.
    """
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    cv2.rectangle(
        image,
        (x, y),
        (x + w, y + h),
        (245, 245, 245),
        -1,
    )

    cv2.rectangle(
        image,
        (x, y),
        (x + w, y + h),
        (40, 40, 40),
        3,
    )

    rank = card[:-1]
    suit = card[-1].lower()

    suit_symbol = {
        "s": "S",
        "h": "H",
        "d": "D",
        "c": "C",
    }[suit]

    color = (
        (40, 40, 190)
        if suit in {"h", "d"}
        else (20, 20, 20)
    )

    _center_text(
        image,
        rank,
        center_x=x + w * 0.35,
        baseline_y=y + int(h * 0.48),
        max_width=int(w * 0.55),
        font=cv2.FONT_HERSHEY_SIMPLEX,
        base_scale=1.5,
        thickness=3,
        color=color,
    )

    _center_text(
        image,
        suit_symbol,
        center_x=x + w * 0.65,
        baseline_y=y + int(h * 0.80),
        max_width=int(w * 0.45),
        font=cv2.FONT_HERSHEY_SIMPLEX,
        base_scale=1.1,
        thickness=3,
        color=color,
    )


def _draw_board(
    image,
    *,
    board,
    geometry,
):
    """
    Board is rendered only into production board-card geometry.
    """

    # Single coordinate authority: the exact maximized-native board
    # rectangles consumed by production.
    board_regions = geometry["board"]

    required = (
        "flop_1",
        "flop_2",
        "flop_3",
        "turn",
        "river",
    )

    missing = (
        set(required)
        - set(board_regions)
    )

    if missing:
        raise KeyError(
            f"production board geometry missing: {sorted(missing)}"
        )

    keys = (
        "flop_1",
        "flop_2",
        "flop_3",
        "turn",
        "river",
    )

    for card, key in zip(
        board,
        keys,
    ):
        _draw_simple_card_face(
            image,
            card=card,
            rect=board_regions[key],
        )


def _draw_pot(
    image,
    *,
    pot_bb,
    geometry,
):
    """
    Render numeric pot evidence entirely inside the exact native
    production pot ROI.

    Production downsamples native -> 934x696, then OCRs:
        <number> BB

    Use the available native height aggressively so the BB suffix
    survives that downsample and pot-value changes create meaningful
    physical change evidence.
    """
    region = geometry[
        "pot_region"
    ]

    if (
        isinstance(region, dict)
        and "x" not in region
    ):
        region = (
            region.get("main_pot")
            or next(iter(region.values()))
        )

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    # Clear the complete production ROI deterministically.
    cv2.rectangle(
        image,
        (x, y),
        (x + w, y + h),
        (18, 55, 30),
        -1,
    )

    text = (
        f"{float(pot_bb):.2f} BB"
    )

    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 4

    # Fit primarily to ROI height, then constrain width.
    scale = 1.55

    while scale >= 0.50:
        (tw, th), baseline = (
            cv2.getTextSize(
                text,
                font,
                scale,
                thickness,
            )
        )

        if (
            tw <= w - 18
            and th + baseline <= h - 6
        ):
            break

        scale -= 0.05

    (tw, th), baseline = (
        cv2.getTextSize(
            text,
            font,
            scale,
            thickness,
        )
    )

    tx = (
        x
        + max(
            4,
            (w - tw) // 2,
        )
    )

    ty = (
        y
        + max(
            th + 2,
            (h + th - baseline) // 2,
        )
    )

    cv2.putText(
        image,
        text,
        (tx, ty),
        font,
        scale,
        (245, 245, 245),
        thickness,
        cv2.LINE_AA,
    )


def _draw_bet_marker(
    image,
    *,
    seat,
    amount_bb,
    geometry,
):
    """
    Render quantitative commitment evidence inside the exact native
    production bet ROI.

    Use nearly all useful physical area for the amount itself.
    The border/text also provide ample occupancy evidence; no decorative
    center chip is required.
    """
    if amount_bb <= 0:
        return

    region = geometry[
        "bet_regions"
    ][seat]

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    # Large central label while retaining safe margins inside the
    # calibrated production ROI.
    box_w = int(round(w * 0.82))
    box_h = int(round(h * 0.68))

    x1 = x + (w - box_w) // 2
    y1 = y + (h - box_h) // 2
    x2 = x1 + box_w
    y2 = y1 + box_h

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (35, 35, 35),
        -1,
    )

    border = max(
        4,
        int(round(
            min(box_w, box_h) * 0.05
        )),
    )

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (235, 235, 235),
        border,
    )

    label = f"{float(amount_bb):g} BB"

    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 5
    scale = 2.0

    while scale >= 0.5:
        (tw, th), baseline = cv2.getTextSize(
            label,
            font,
            scale,
            thickness,
        )

        if (
            tw <= box_w - 20
            and th + baseline <= box_h - 12
        ):
            break

        scale -= 0.05

    (tw, th), baseline = cv2.getTextSize(
        label,
        font,
        scale,
        thickness,
    )

    tx = x1 + (box_w - tw) // 2

    ty = (
        y1
        + (box_h + th - baseline) // 2
    )

    cv2.putText(
        image,
        label,
        (tx, ty),
        font,
        scale,
        (250, 250, 250),
        thickness,
        cv2.LINE_AA,
    )


def _active_names(state):
    return {
        player.name
        for player in state.players
        if not player.folded
    }


def _previous_state_commitments(
    *,
    hand,
    state,
):
    """
    Derive visible current-street commitments using only simulator truth.

    This is generator-side state used solely to draw physical bet markers.
    """
    target = int(state.sequence)

    commitments = {
        player.name: 0.0
        for player in hand.players
    }

    current_street = None

    # Recompile locally from authoritative history. Nothing produced here
    # crosses into production except pixels.
    actions = list(hand.actions)

    sequence = 1

    for action in actions:
        if action.action == "ANTE":
            sequence += 1
            if sequence > target:
                break
            continue

        if action.action in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }:
            sequence += 1

            if sequence > target:
                break

            commitments[
                action.actor
            ] += float(
                action.amount or 0.0
            )

            current_street = "PREFLOP"
            continue

        # HOLE_CARDS state.
        if (
            current_street == "PREFLOP"
            and sequence == 11
        ):
            sequence += 1

            if sequence > target:
                break

        if action.street != current_street:
            current_street = (
                action.street
            )

            commitments = {
                player.name: 0.0
                for player in hand.players
            }

            # Street boundary state.
            sequence += 1

            if sequence > target:
                break

        sequence += 1

        if sequence > target:
            break

        if action.action in {
            "CALL",
            "BET",
            "RAISE",
        }:
            commitments[
                action.actor
            ] += float(
                action.amount or 0.0
            )

    return commitments


def _neutralize_rect(
    image,
    rect,
):
    """
    Generator-side stale-evidence removal.

    Replace a controlled ROI with nearby physical background sampled
    from the same authentic master-backed frame. This is not semantic
    evidence; it merely guarantees that pixels belonging to the
    master's original hand cannot survive into a controlled state.
    """
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    ih, iw = image.shape[:2]

    # Prefer a narrow strip immediately above the ROI.
    sample_h = max(
        4,
        min(
            20,
            h // 5,
        ),
    )

    sy1 = max(
        0,
        y - sample_h,
    )
    sy2 = y

    if sy2 <= sy1:
        sy1 = min(
            ih,
            y + h,
        )
        sy2 = min(
            ih,
            sy1 + sample_h,
        )

    sx1 = max(0, x)
    sx2 = min(iw, x + w)

    sample = image[
        sy1:sy2,
        sx1:sx2,
    ]

    if sample.size == 0:
        fill = np.array(
            FELT,
            dtype=np.uint8,
        )
    else:
        fill = np.median(
            sample.reshape(-1, 3),
            axis=0,
        ).astype(np.uint8)

    image[
        y:y+h,
        x:x+w,
    ] = fill


def _neutralize_nested_rects(
    image,
    value,
):
    if isinstance(value, dict):
        if {
            "x",
            "y",
            "width",
            "height",
        }.issubset(value):
            _neutralize_rect(
                image,
                value,
            )
            return

        for child in value.values():
            _neutralize_nested_rects(
                image,
                child,
            )

    elif isinstance(value, list):
        for child in value:
            _neutralize_nested_rects(
                image,
                child,
            )


def _claim_and_clear_dynamic_lanes(
    frame,
):
    """
    Remove all stale master-hand evidence before installing the
    controlled state's dynamic evidence.

    Player identity/stack lanes are installed separately by
    render_master_player().
    """
    image = frame.image
    geometry = frame.geometry

    # Hole cards.
    for seat, regions in (
        geometry["hole_cards"].items()
    ):
        _neutralize_nested_rects(
            image,
            regions,
        )
        frame.claim_hole_cards(
            seat
        )

    # Dealer zones.
    for seat, zones in (
        geometry[
            "dealer_button_zones"
        ].items()
    ):
        _neutralize_nested_rects(
            image,
            zones,
        )
        frame.claim_dealer(
            seat
        )

    # Bet regions.
    for seat, rect in (
        geometry["bet_regions"].items()
    ):
        _neutralize_rect(
            image,
            rect,
        )
        frame.claim_bet(
            seat
        )

    # Board.
    for slot, rect in (
        geometry["board"].items()
    ):
        _neutralize_rect(
            image,
            rect,
        )
        frame.claim_board(
            slot
        )

    # Pot.
    pot = geometry["pot_region"]

    if (
        isinstance(pot, dict)
        and "x" not in pot
    ):
        pot = (
            pot.get("main_pot")
            or next(iter(
                pot.values()
            ))
        )

    _neutralize_rect(
        image,
        pot,
    )
    frame.claim_pot()



OPPONENT_CARD_PRIMITIVES = (
    ROOT
    / "runtime/pixel_lab/primitives/"
      "opponent_cards"
)


WINNER_PRIMITIVES = (
    ROOT
    / "runtime/pixel_lab/primitives/winner"
)


def _inverse_sensor_rect(
    rect,
    *,
    sensor_size=(934, 696),
    native_size=(3456, 2168),
):
    """
    Native footprint whose full-frame resize lands exactly
    on one canonical production detector ROI.
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


def _render_opponent_card_primitives(
    image,
    *,
    seat,
):
    """
    Install isolated authentic ACR opponent-card primitives.

    No captured table frame or donor hand is read here.
    Primitive placement is derived from the canonical production
    detector ROI so canonical_sensor_frame() round-trips the
    evidence into exactly the region production measures.
    """
    # Production's canonical detector geometry is the historical
    # 934x696 geometry contract.
    canonical_geometry = json.loads(
        (
            ROOT
            / "config/geometry.json"
        ).read_text()
    )

    regions = canonical_geometry[
        "hole_cards"
    ][seat]

    for card_name in (
        "card_1",
        "card_2",
    ):
        primitive_path = (
            OPPONENT_CARD_PRIMITIVES
            / f"{seat}_{card_name}.png"
        )

        primitive = cv2.imread(
            str(primitive_path)
        )

        assert primitive is not None, (
            primitive_path
        )

        target = _inverse_sensor_rect(
            regions[card_name]
        )

        x = int(target["x"])
        y = int(target["y"])
        w = int(target["width"])
        h = int(target["height"])

        if primitive.shape[:2] != (
            h,
            w,
        ):
            primitive = cv2.resize(
                primitive,
                (w, h),
                interpolation=cv2.INTER_CUBIC,
            )

        image[
            y:y + h,
            x:x + w,
        ] = primitive

    return image


def _render_winner_primitive(
    image,
    *,
    seat,
):
    """
    Install an authentic ACR WINNER treatment into the physical
    production detector footprint.

    Pixel Lab owns this rendering primitive. Production receives
    only the resulting pixels.
    """
    from src.vision.winner_detector import (
        winner_roi_for_seat,
    )

    # Every supported seat requires its own independently
    # validated authentic ACR WINNER primitive. Never extrapolate
    # one seat's pixels to another seat.
    primitive_names = {
        "hero":
            "hero_winner_canonical.png",
        "seat_upper_left":
            "seat_upper_left_winner_canonical.png",
    }

    primitive_name = primitive_names.get(
        seat
    )

    if primitive_name is None:
        return image

    path = (
        WINNER_PRIMITIVES
        / primitive_name
    )

    primitive = cv2.imread(
        str(path)
    )

    assert primitive is not None, path

    target = _inverse_sensor_rect(
        winner_roi_for_seat(
            seat
        )
    )

    x = int(target["x"])
    y = int(target["y"])
    w = int(target["width"])
    h = int(target["height"])

    primitive = cv2.resize(
        primitive,
        (w, h),
        interpolation=cv2.INTER_CUBIC,
    )

    image[
        y:y + h,
        x:x + w,
    ] = primitive

    return image


def render_simulation_state(
    *,
    hand,
    state,
):
    """
    Render one complete simulator state.

    Poker state comes only from ACR simulation truth.
    All physical placement comes only from production geometry.
    """
    frame = MasterFrame()
    image = frame.image
    geometry = frame.geometry
    atlas = build_atlas(image)

    # Every dynamic production-sensitive lane starts neutralized and
    # explicitly owned. State-specific evidence is installed below.
    _claim_and_clear_dynamic_lanes(
        frame
    )

    seat_map = map_acr_seats(
        hand
    )

    state_players = {
        player.name: player
        for player in state.players
    }

    active = _active_names(
        state
    )

    for player in hand.players:
        seat = seat_map[
            int(player.seat_number)
        ]

        sim_player = state_players[
            player.name
        ]

        render_master_player(
            frame,
            seat=seat,
            name=player.name,
            stack_bb=sim_player.stack_bb,
            atlas=atlas,
        )

        # Opponent cards are a physical signal.
        #
        # Dynamic card lanes begin neutralized. Install isolated
        # authentic card primitives only while the opponent remains
        # live. A fold therefore produces a physical True -> False
        # transition without exposing simulator truth to production.
        if (
            seat != "hero"
            and not sim_player.folded
            and not sim_player.sitting_out
        ):
            _render_opponent_card_primitives(
                image,
                seat=seat,
            )

    dealer_seat = seat_map[
        int(state.button_seat)
    ]

    _draw_dealer_button(
        image,
        seat=dealer_seat,
        geometry=geometry,
    )

    # Hero cards become physically visible at HOLE_CARDS and remain until
    # Hero folds. The simulator knows this; production does not.
    hero_state = state_players[
        hand.hero_name
    ]

    if (
        state.sequence >= 12
        and not hero_state.folded
    ):
        # Use isolated authentic ACR Hero-card crops. These are card
        # primitives only, not captured table frames. Resize each directly
        # into the exact maximized-native Hero ROI consumed by production.
        _draw_hero_cards(
            image,
            cards=state.hero_cards,
            geometry=geometry,
        )

    if state.board:
        _draw_board(
            image,
            board=state.board,
            geometry=geometry,
        )

    _draw_pot(
        image,
        pot_bb=state.pot_bb,
        geometry=geometry,
    )

    commitments = (
        _previous_state_commitments(
            hand=hand,
            state=state,
        )
    )

    for name, chips in (
        commitments.items()
    ):
        if chips <= 0:
            continue

        source_player = next(
            player
            for player in hand.players
            if player.name == name
        )

        seat = seat_map[
            int(
                source_player.seat_number
            )
        ]

        _draw_bet_marker(
            image,
            seat=seat,
            amount_bb=(
                float(chips)
                / float(hand.big_blind)
            ),
            geometry=geometry,
        )

    # No generated observer frame may cross the isolation wall unless
    # all 46 production-sensitive lanes have explicit ownership.
    # Terminal physical evidence.
    #
    # Private simulation state decides whether the authentic visual
    # treatment exists. Production sees only the resulting pixels.
    if (
        state.cause_action == "WINNER"
        and state.winner
    ):
        winner_player = next(
            (
                player
                for player in hand.players
                if player.name
                == state.winner
            ),
            None,
        )

        if winner_player is not None:
            winner_seat = seat_map[
                int(
                    winner_player.seat_number
                )
            ]

            _render_winner_primitive(
                image,
                seat=winner_seat,
            )

    return frame.emit()
