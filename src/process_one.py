import sys
from pathlib import Path

from state_builder import build_state, write_outputs


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 src/process_one.py /path/to/screenshot.png")
        raise SystemExit(1)
    image_path = Path(sys.argv[1]).expanduser().resolve()
    if not image_path.exists():
        print(f"Image not found: {image_path}")
        raise SystemExit(1)
    project_root = Path(__file__).resolve().parents[1]
    state = build_state(image_path, project_root)
    latest_json, latest_txt = write_outputs(state, project_root)
    print(f"Processed: {image_path.name}")
    print(f"Wrote {latest_json}")
    print(f"Wrote {latest_txt}")

if __name__ == "__main__":
    main()
