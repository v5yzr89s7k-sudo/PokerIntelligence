import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_FILE = PROJECT_ROOT / "config" / "geometry.json"


def load_geometry():
    with open(GEOMETRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    geometry = load_geometry()

    print("Loaded geometry")
    print("Table size:", geometry["table_size"])
    print("Keys:", list(geometry.keys()))
