import cv2
import numpy as np


def _crop(img, rect):
    x, y, w, h = map(int, [rect["x"], rect["y"], rect["width"], rect["height"]])
    return img[y:y+h, x:x+w]


def bet_region_signal(frame, rect):
    crop = _crop(frame, rect)
    if crop.size == 0:
        return {
            "bright_ratio": 0.0,
            "edge_density": 0.0,
            "occupied": False,
        }

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    bright_ratio = float((gray > 150).mean())

    edges = cv2.Canny(gray, 80, 160)
    edge_density = float((edges > 0).mean())

    occupied = bright_ratio > 0.035 or edge_density > 0.055

    return {
        "bright_ratio": bright_ratio,
        "edge_density": edge_density,
        "occupied": occupied,
    }


def bet_region_occupancy(frame, geometry):
    return {
        seat: bet_region_signal(frame, rect)
        for seat, rect in geometry.get("bet_regions", {}).items()
    }


def occupied_bet_regions(frame, geometry):
    details = bet_region_occupancy(frame, geometry)
    return [seat for seat, info in details.items() if info.get("occupied")]
