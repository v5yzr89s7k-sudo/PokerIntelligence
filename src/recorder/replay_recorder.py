from pathlib import Path
import subprocess
import shutil
import time

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT = ROOT / "runtime/replay"

OUT.mkdir(parents=True, exist_ok=True)

# Clear previous replay frames
for f in OUT.glob("frame_*.png"):
    f.unlink()

print("=" * 60)
print("Poker Intelligence Replay Recorder")
print("=" * 60)
print()
print("Starting capture...")
print("Press Ctrl+C when replay is finished.")
print()

frame = 1

try:
    while True:
        subprocess.run(
            ["python3", str(CAPTURE_SCRIPT)],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]

        shutil.copy2(
            latest,
            OUT / f"frame_{frame:04d}.png"
        )

        if frame % 10 == 0:
            print(f"Captured {frame} frames")

        frame += 1

        time.sleep(0.15)

except KeyboardInterrupt:
    print()
    print("=" * 60)
    print(f"Finished.")
    print(f"Captured {frame-1} frames.")
    print(f"Saved to: {OUT}")
    print("=" * 60)
