from pathlib import Path
from time import perf_counter
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.vision.window_capture import (
    list_visible_processes,
    find_acr_table_window,
    capture_window_crop,
)

print("Profiling window capture pipeline")
print("---------------------------------")

t0 = perf_counter()
procs = list_visible_processes()
t1 = perf_counter()

window = find_acr_table_window()
t2 = perf_counter()

if window is None:
    raise SystemExit("ACR table window not found")

capture_window_crop(window)
t3 = perf_counter()

print(f"Visible processes : {(t1-t0)*1000:.1f} ms")
print(f"Find table window : {(t2-t1)*1000:.1f} ms")
print(f"Screen capture    : {(t3-t2)*1000:.1f} ms")
print(f"TOTAL             : {(t3-t0)*1000:.1f} ms")
