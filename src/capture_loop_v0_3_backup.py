import subprocess
import time
from pathlib import Path
from datetime import datetime

from state_builder import build_state, write_outputs
from ocr_utils import load_config


def cleanup_old_screenshots(folder: Path, keep: int):
    files = sorted([p for p in folder.glob("auto_*.png")], key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[keep:]:
        try:
            p.unlink()
        except OSError:
            pass


def capture_fullscreen(path: Path):
    # -x = no camera shutter sound. Fullscreen capture.
    subprocess.run(["screencapture", "-x", str(path)], check=True)


def main():
    project_root = Path(__file__).resolve().parents[1]
    config = load_config(project_root)
    screenshot_dir = project_root / config.get("screenshot_folder", "screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    interval = float(config.get("capture_interval_seconds", 1.0))
    keep = int(config.get("max_screenshots_to_keep", 200))

    print("Poker Intelligence auto-capture loop v0.3")
    print("Mode: fullscreen periodic capture")
    print(f"Interval: {interval}s")
    print("This only reads the screen. It does not click or interact with ACR.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            out = screenshot_dir / f"auto_{ts}.png"
            try:
                capture_fullscreen(out)
                state = build_state(out, project_root)
                latest_json, latest_txt = write_outputs(state, project_root)
                print(f"Captured/processed {out.name} | cards={state.get('hero_cards')} stack={state.get('hero_stack_bb')} pot={state.get('pot_bb')} actions={state.get('action_buttons')}")
                cleanup_old_screenshots(screenshot_dir, keep)
            except Exception as e:
                print(f"ERROR: {e}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    main()
