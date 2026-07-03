from src.events.utils import region_changed

def dealer_changed(previous, current, geometry):
    """
    Returns True if any dealer-button zone changed.
    """

    for rect in geometry["dealer_button_zones"].values():
        if region_changed(previous, current, rect):
            return True

    return False
