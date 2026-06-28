import subprocess
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
WINDOW_CAPTURES_DIR = RUNTIME_DIR / "window_captures"


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


def find_acr_table_windows(processes: list[str]) -> list[str]:
    """
    ACR on macOS appears as Electron.
    The reliable signal is the table window title, not the process name.
    """
    table_keywords = ["hold'em", "holdem", "no limit", "table", "ante", "gtd"]
    exclude_keywords = ["lobby"]

    candidates = []
    for process in processes:
        if process.lower() != "electron":
            continue
        windows = list_windows_for_process(process)
        for window in windows:
            lower = window.lower()
            if any(k in lower for k in table_keywords) and not any(x in lower for x in exclude_keywords):
                candidates.append(f"{process} | {window}")
    return candidates


def capture_fullscreen_to_runtime() -> Path:
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out = WINDOW_CAPTURES_DIR / f"fullscreen_{ts}.png"
    subprocess.run(["screencapture", "-x", str(out)], check=True)
    return out


def main() -> None:
    print("Poker Intelligence v0.5 window detection smoke test")

    processes = list_visible_processes()
    print("\nVisible processes:")
    for p in processes:
        print(f"- {p}")

    print("\nWindows by process:")
    for p in processes:
        windows = list_windows_for_process(p)
        if windows:
            print(f"\n[{p}]")
            for w in windows:
                print(f"- {w}")

    candidates = find_acr_table_windows(processes)
    print("\nACR table window candidates:")
    if candidates:
        for c in candidates:
            print(f"- {c}")
    else:
        print("[NONE FOUND]")

    shot = capture_fullscreen_to_runtime()
    print(f"\nSaved fullscreen smoke capture: {shot}")


if __name__ == "__main__":
    main()
