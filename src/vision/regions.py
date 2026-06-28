import json
from pathlib import Path
from typing import Dict, Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGIONS_PATH = PROJECT_ROOT / "config" / "regions.json"


def load_regions(path: Path = REGIONS_PATH) -> Dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_regions(regions: Dict[str, Any], path: Path = REGIONS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(regions, indent=2, sort_keys=True), encoding="utf-8")


def add_region(name: str, x: int, y: int, w: int, h: int) -> Dict[str, Any]:
    regions = load_regions()
    regions[name] = {
        "x": int(x),
        "y": int(y),
        "w": int(w),
        "h": int(h)
    }
    save_regions(regions)
    return regions
