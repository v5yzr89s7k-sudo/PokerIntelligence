import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
WINDOW_CAPTURES_DIR = RUNTIME_DIR / "window_captures"


@dataclass
class WindowInfo:
    process: str
    title: str
    x: int
    y: int
    w: int
    h: int


def ensure_dirs() -> None:
    WINDOW_CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stderr.strip():
        print("AppleScript stderr:", result.stderr.strip())
    return result.stdout.strip()


def list_visible_processes() -> list[str]:
    script = 'tell application "System Events" to get name of every process whose visible is true'
    out = run_osascript(script)
    return [p.strip() for p in out.split(",") if p.strip()]


def list_windows_for_process(process_name: str) -> list[str]:
    script = f'''
    tell application "System Events"
        tell process "{process_name}"
            set output to ""
            repeat with w in windows
                try
                    set winPos to position of w
                    set winSize to size of w
                    set output to output & name of w & " | " & item 1 of winPos & "," & item 2 of winPos & " | " & item 1 of winSize & "," & item 2 of winSize & linefeed
                end try
            end repeat
            return output
        end tell
    end tell
    '''
    out = run_osascript(script)
    return [line.strip() for line in out.splitlines() if line.strip()]


def parse_window_line(process: str, line: str) -> Optional[WindowInfo]:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 3:
        return None

    title, pos, size = parts
    pos_match = re.match(r"(-?\d+),(-?\d+)", pos)
    size_match = re.match(r"(\d+),(\d+)", size)

    if not pos_match or not size_match:
        return None

    return WindowInfo(
        process=process,
        title=title,
        x=int(pos_match.group(1)),
        y=int(pos_match.group(2)),
        w=int(size_match.group(1)),
        h=int(size_match.group(2)),
    )


def find_acr_table_window() -> Optional[WindowInfo]:
    table_keywords = ["hold'em", "holdem", "no limit", "table", "ante", "gtd"]
    exclude_keywords = ["lobby"]

    for process in list_visible_processes():
        if process.lower() != "electron":
            continue

        for line in list_windows_for_process(process):
            info = parse_window_line(process, line)
            if not info:
                continue

            lower = info.title.lower()
            if any(k in lower for k in table_keywords) and not any(x in lower for x in exclude_keywords):
                return info

    return None


def capture_fullscreen(path: Path) -> Path:
    subprocess.run(["screencapture", "-x", str(path)], check=True)
    return path


def capture_window_crop(window: WindowInfo) -> Path:
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out = WINDOW_CAPTURES_DIR / f"acr_table_{ts}.png"

    # macOS screencapture region format: -R x,y,w,h
    region = f"{window.x},{window.y},{window.w},{window.h}"
    subprocess.run(["screencapture", "-x", "-R", region, str(out)], check=True)
    return out


def main() -> None:
    print("Poker Intelligence v0.5 ACR table window crop smoke test")

    window = find_acr_table_window()
    if not window:
        print("ACR table window not found.")
        return

    print("ACR table found:")
    print(f"process={window.process}")
    print(f"title={window.title}")
    print(f"x={window.x} y={window.y} w={window.w} h={window.h}")

    out = capture_window_crop(window)
    print(f"Saved ACR table crop: {out}")


if __name__ == "__main__":
    main()
