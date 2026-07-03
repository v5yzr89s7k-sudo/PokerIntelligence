import cv2
import numpy as np

def region_changed(previous, current, rect, threshold=18.0):
    x = rect["x"]
    y = rect["y"]
    w = rect["width"]
    h = rect["height"]

    a = previous[y:y+h, x:x+w]
    b = current[y:y+h, x:x+w]

    if a.shape != b.shape:
        return True

    diff = cv2.absdiff(a, b)
    return float(np.mean(diff)) > threshold
