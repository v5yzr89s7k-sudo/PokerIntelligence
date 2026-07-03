from src.events.utils import region_changed

def board_changed(previous, current, geometry):
    """
    Returns True if any board card region changed.
    Uses a higher threshold because board area has animation/noise.
    """

    for rect in geometry["board"].values():
        if region_changed(previous, current, rect, threshold=60.0):
            return True

    return False
