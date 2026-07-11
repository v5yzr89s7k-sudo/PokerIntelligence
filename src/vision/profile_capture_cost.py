from pathlib import Path
import subprocess
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"

samples = 20
times = []

for i in range(samples):
    t0 = perf_counter()
    subprocess.run(
        ["python3", str(CAPTURE_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    ms = (perf_counter() - t0) * 1000.0
    times.append(ms)
    print(f"{i:02d}: capture_ms={ms:.1f}")

print()
print(f"min={min(times):.1f} ms")
print(f"max={max(times):.1f} ms")
print(f"avg={sum(times)/len(times):.1f} ms")
