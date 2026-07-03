from src.events.utils import region_changed

def pot_changed(previous, current, geometry):
    """
    Returns True if any pot region changed.
    """

    for rect in geometry["pot_region"].values():
        if region_changed(previous, current, rect):
            return True

    return False
