from pathlib import Path
import json
import time
import hashlib
import subprocess
from datetime import datetime

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = ROOT / "config/geometry.json"
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
LIVE_JSON = ROOT / "runtime/live/live_hand_state.json"
LIVE_TXT = ROOT / "runtime/live/live_hand_state.txt"
CHANGE_LOG = ROOT / "runtime/live/change_log.txt"
DEBUG_DIR = ROOT / "runtime/debug_regions"


def load_geometry():
    return json.loads(GEOMETRY_PATH.read_text())


def latest_capture():
    files = sorted(CAPTURE_DIR.glob("acr_table_*.png"))
    if not files:
        raise FileNotFoundError("No acr_table_*.png capture found")
    return files[-1]


def capture_table():
    subprocess.run(["python3", str(CAPTURE_SCRIPT)], cwd=str(ROOT), check=True)
    return latest_capture()



def region_difference(a, b):
    if a is None or b is None:
        return 100.0
    if a.shape != b.shape:
        return 100.0
    diff = cv2.absdiff(a, b)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    changed = np.count_nonzero(gray > 15)
    return changed / gray.size * 100.0

def image_hash(img):
    return hashlib.md5(img.tobytes()).hexdigest()


def crop_region(img, r):
    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])
    return img[y:y+h, x:x+w]


def build_snapshot(image_path, frame_no):
    g = load_geometry()
    img = cv2.imread(str(image_path))

    if img is None:
        raise FileNotFoundError(image_path)

    tw = int(g["table_size"]["width"])
    th = int(g["table_size"]["height"])
    img = cv2.resize(img, (tw, th), interpolation=cv2.INTER_AREA)

    snapshot = {
        "frame": frame_no,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "image": str(image_path),
        "regions": {}
    }

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    for group, regions in g.items():
        if group == "table_size" or not isinstance(regions, dict):
            continue

        snapshot["regions"][group] = {}

        for name, r in regions.items():
            if not isinstance(r, dict):
                continue
            if not all(k in r for k in ("x", "y", "width", "height")):
                continue

            crop = crop_region(img, r)
            h = image_hash(crop)
            frame_dir = DEBUG_DIR / f"frame_{frame_no:06d}"
            frame_dir.mkdir(parents=True, exist_ok=True)
            crop_path = frame_dir / f"{group}__{name}.png"
            cv2.imwrite(str(crop_path), crop)

            snapshot["regions"][group][name] = {
                "hash": h,
                "image": crop,
                "crop": str(crop_path),
                "x": r["x"],
                "y": r["y"],
                "width": r["width"],
                "height": r["height"]
            }

    return snapshot



def flatten_images(snapshot):
    flat = {}
    important_groups = {
        "hero_cards",
        "board",
        "pot_region",
        "bet_regions",
        "stack_regions",
        "action_buttons",
    }

    for group, regions in snapshot["regions"].items():
        if group not in important_groups:
            continue
        for name, data in regions.items():
            flat[f"{group}.{name}"] = data["image"]

    return flat

def append_change_log(frame_no, timestamp, previous, current):
    if previous is None:
        CHANGE_LOG.write_text(f"Frame {frame_no} {timestamp}\nINITIAL SNAPSHOT\n\n")
        return

    changes = []
    for key, value in current.items():
        diff = region_difference(previous.get(key), value)
        if diff > 3.0:
            changes.append(f"{key} ({diff:.1f}%)")

    if not changes:
        return

    with CHANGE_LOG.open("a") as f:
        f.write(f"Frame {frame_no} {timestamp}\n")
        messages = []
        for key in changes:
            label = key.split(" (")[0]
            if label.startswith("board."):
                messages.append(f"board changed: {label}")
            elif label.startswith("hero_cards."):
                messages.append(f"hero cards changed: {label}")
            elif label.startswith("pot_region."):
                messages.append("pot changed")
            elif label.startswith("bet_regions."):
                messages.append(f"bet area changed: {label}")
            elif label.startswith("stack_regions."):
                messages.append(f"stack changed: {label}")
            elif label.startswith("action_buttons."):
                messages.append("action buttons changed")
            else:
                messages.append(f"changed: {key}")

        for message in sorted(set(messages)):
            f.write(f"  {message}\n")
        f.write("\n")


def write_live_files(snapshot):
    LIVE_JSON.parent.mkdir(parents=True, exist_ok=True)

    json_snapshot = json.loads(json.dumps(snapshot, default=lambda _o: "<image_array>"))
    for group in json_snapshot.get("regions", {}).values():
        for item in group.values():
            item.pop("image", None)

    LIVE_JSON.write_text(json.dumps(json_snapshot, indent=2) + "\n")

    lines = []
    lines.append(f"Frame: {snapshot['frame']}")
    lines.append(f"Time: {snapshot['timestamp']}")
    lines.append(f"Image: {snapshot['image']}")
    lines.append("")
    lines.append("Observed Regions:")
    lines.append("")

    for group, regions in snapshot["regions"].items():
        lines.append(group)
        for name, data in regions.items():
            lines.append(f"  {name}: {data['hash'][:12]} crop={data['crop']}")
        lines.append("")

    LIVE_TXT.write_text("\n".join(lines))


def main():
    print("Live hand recorder started.")
    print("ACR table must be visible and unobstructed.")
    print("Writing:")
    print(f"  {LIVE_JSON}")
    print(f"  {LIVE_TXT}")
    print("Press Ctrl+C to stop.")

    last_full_hash = None
    last_region_images = None
    frame_no = 0
    CHANGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    CHANGE_LOG.write_text("")

    while True:
        image_path = capture_table()
        img = cv2.imread(str(image_path))
        full_hash = image_hash(img)

        if full_hash != last_full_hash:
            frame_no += 1
            snapshot = build_snapshot(image_path, frame_no)
            current_region_hashes = flatten_images(snapshot)
            append_change_log(frame_no, snapshot["timestamp"], last_region_images, current_region_hashes)
            write_live_files(snapshot)
            print(f"Frame {frame_no}: change recorded")
            last_region_images = current_region_hashes
            last_full_hash = full_hash
        else:
            print("No change")

        time.sleep(1.0)


if __name__ == "__main__":
    main()
