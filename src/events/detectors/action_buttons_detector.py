from src.events.utils import region_changed

def action_buttons_changed(previous, current, geometry):
    """
    Returns True if any hero action-button region changed.
    """

    for rect in geometry["action_buttons"].values():
        if region_changed(previous, current, rect):
            return True

    return False
