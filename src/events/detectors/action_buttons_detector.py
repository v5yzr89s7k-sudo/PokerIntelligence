from src.events.utils import region_changed

def action_buttons_changed(previous, current, geometry):
    """
    Returns True if any hero action-button region changed.
    """

    for rect in geometry["action_buttons"].values():
        if region_changed(previous, current, rect):
            return True

    return False

def action_buttons_visible(frame, geometry):
    """
    Returns True when the hero Fold / Call-Check / Raise-Bet button area is visibly active.
    """
    import cv2

    visible = 0
    for rect in geometry["action_buttons"].values():
        x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
        crop = frame[y:y+h, x:x+w]
        if crop.size == 0:
            continue

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Active ACR buttons are bright enough compared with inactive felt/background.
        if (gray > 90).mean() > 0.25:
            visible += 1

    return visible >= 1
