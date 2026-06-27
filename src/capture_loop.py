import subprocess
import time
from pathlib import Path
from datetime import datetime

from state_builder import build_state, write_outputs
from ocr_utils import load_config
from live_state_machine import LiveHandStateMachine, HandPhase


def capture_fullscreen(path: Path):
    # -x = no camera shutter sound. Fullscreen capture.
    subprocess.run(["screencapture", "-x", str(path)], check=True)


def infer_board_count(state: dict) -> int:
    board = state.get("board") or state.get("community_cards") or []
    if isinstance(board, list):
        return len([c for c in board if c])
    return 0


def hero_cards_present(state: dict) -> bool:
    cards = state.get("hero_cards")
    if not cards:
        return False
    if isinstance(cards, list):
        return len([c for c in cards if c]) >= 2
    return False


def action_buttons_visible(state: dict) -> bool:
    buttons = state.get("action_buttons") or []
    if not isinstance(buttons, list):
        return False
    useful = [b for b in buttons if isinstance(b, str) and b.strip()]
    return len(useful) > 0


def main():
    project_root = Path(__file__).resolve().parents[1]
    config = load_config(project_root)

    runtime_dir = project_root / "runtime"
    frame_dir = runtime_dir / "current_hand_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    interval = float(config.get("capture_interval_seconds", 1.0))

    machine = LiveHandStateMachine()

    print("Poker Intelligence auto-capture loop v0.4")
    print("Mode: fullscreen periodic capture + live hand state machine")
    print(f"Interval: {interval}s")
    print("This only reads the screen. It does not click or interact with ACR.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            out = frame_dir / f"frame_{ts}.png"

            try:
                capture_fullscreen(out)
                state = build_state(out, project_root)
                write_outputs(state, project_root)

                has_hero_cards = hero_cards_present(state)
                board_count = infer_board_count(state)
                hero_decision = action_buttons_visible(state)
                buttons = state.get("action_buttons") or []

                if machine.state.phase == HandPhase.WAITING_FOR_HAND and has_hero_cards:
                    machine.start_hand(hero_cards_seen=True, dealer_seat=None)

                if machine.state.phase != HandPhase.WAITING_FOR_HAND:
                    machine.update_board_count(board_count)
                    machine.set_hero_decision_visible(hero_decision, buttons)

                print(
                    f"Captured {out.name} | "
                    f"phase={machine.state.phase.value} "
                    f"cards={state.get('hero_cards')} "
                    f"stack={state.get('hero_stack_bb')} "
                    f"pot={state.get('pot_bb')} "
                    f"board_count={board_count} "
                    f"actions={state.get('action_buttons')}"
                )

            except Exception as e:
                print(f"ERROR: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
