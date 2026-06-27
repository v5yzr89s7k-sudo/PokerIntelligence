from pathlib import Path
from datetime import datetime
import json
import re
from typing import Dict, Any

from ocr_utils import (
    load_config,
    ocr_regions,
    extract_first_bb,
    detect_break_state,
    parse_blinds_antes,
    parse_players_left,
    parse_pot_bb,
)

CARD_TOKEN_RE = re.compile(r"\b([AKQJT2-9])\s*([cdhsCDHS♣♦♥♠])\b")

SUIT_MAP = {
    "c": "c", "C": "c", "♣": "c",
    "d": "d", "D": "d", "♦": "d",
    "h": "h", "H": "h", "♥": "h",
    "s": "s", "S": "s", "♠": "s",
}


def guess_cards_from_text(text: str):
    if not text:
        return None
    tokens = []
    for rank, suit in CARD_TOKEN_RE.findall(text):
        tokens.append(rank.upper() + SUIT_MAP.get(suit, suit.lower()))
    return tokens if len(tokens) >= 2 else None


def infer_action_buttons(text: str):
    t = (text or "").lower()
    buttons = []
    for word in ["fold", "call", "check", "raise", "bet", "all-in", "all in"]:
        if word in t:
            buttons.append(word.upper().replace("ALL IN", "ALL-IN"))
    return sorted(set(buttons))


def build_state(image_path: Path, project_root: Path) -> Dict[str, Any]:
    config = load_config(project_root)
    output_dir = project_root / config.get("output_folder", "output")
    debug_dir = project_root / config.get("debug_crop_folder", "output/debug_crops")
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)

    region_ocr = ocr_regions(image_path, config, debug_dir)
    from PIL import Image
    img = Image.open(image_path)

    header = region_ocr.get("tournament_header", "")
    hero_area = region_ocr.get("hero_area", "")
    hero_cards_area = region_ocr.get("hero_cards", "")
    hero_stack_area = region_ocr.get("hero_stack", "")
    action_text = region_ocr.get("action_buttons", "")
    pot_text = region_ocr.get("pot_area", "")

    break_state = detect_break_state(region_ocr)
    cards = guess_cards_from_text(hero_cards_area) or guess_cards_from_text(hero_area)
    hero_stack = extract_first_bb(hero_stack_area) or extract_first_bb(hero_area)
    blinds = parse_blinds_antes(header)
    players_left = parse_players_left(header)
    pot_bb = parse_pot_bb(pot_text)
    actions = infer_action_buttons(action_text)

    confidence = {
        "hero_cards": 0.85 if cards else 0.0,
        "hero_stack": 0.8 if hero_stack is not None else 0.0,
        "dealer_button": 0.0,
        "position": 0.0,
        "action": 0.75 if actions else 0.25,
        "pot": 0.75 if pot_bb is not None else 0.0,
        "blinds": 0.75 if blinds else 0.0,
        "break_state": 0.95 if break_state else 0.5,
    }
    confidence["overall"] = round(sum(confidence.values()) / len(confidence), 3)

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "screenshot": str(image_path),
        "image_width": img.width,
        "image_height": img.height,
        "is_break": break_state,
        "hero_cards": cards[:2] if cards else None,
        "hero_stack_bb": hero_stack,
        "blinds": blinds,
        "players_left": players_left,
        "pot_bb": pot_bb,
        "action_buttons": actions,
        "region_ocr": region_ocr,
        "vision_confidence": confidence,
        "notes": [
            "v0.3 uses screenshots only for live state.",
            "ACR hand history should update the permanent database after hand completion.",
            "Dealer/position detection is not implemented yet; next calibration target."
        ]
    }


def write_outputs(state: Dict[str, Any], project_root: Path):
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    latest_json = output_dir / "latest_state.json"
    latest_txt = output_dir / "latest_hand.txt"
    session_log = output_dir / "session_log.jsonl"

    latest_json.write_text(json.dumps(state, indent=2), encoding="utf-8")

    lines = []
    lines.append("POKER INTELLIGENCE - LATEST LIVE STATE")
    lines.append("=" * 52)
    lines.append(f"Time: {state['timestamp']}")
    lines.append(f"Screenshot: {state['screenshot']}")
    lines.append(f"Image: {state['image_width']}x{state['image_height']}")
    lines.append("")
    lines.append(f"Break state: {state['is_break']}")
    lines.append(f"Hero cards: {state['hero_cards'] or 'UNKNOWN'}")
    lines.append(f"Hero stack BB: {state['hero_stack_bb']}")
    lines.append(f"Blinds: {state['blinds']}")
    lines.append(f"Players left: {state['players_left']}")
    lines.append(f"Pot BB: {state['pot_bb']}")
    lines.append(f"Action buttons: {state['action_buttons']}")
    lines.append("")
    lines.append("Vision confidence:")
    for k, v in state["vision_confidence"].items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Region OCR:")
    for k, v in state["region_ocr"].items():
        lines.append(f"\n[{k}]\n{v or '(empty)'}")

    latest_txt.write_text("\n".join(lines), encoding="utf-8")
    with session_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(state) + "\n")

    return latest_json, latest_txt
