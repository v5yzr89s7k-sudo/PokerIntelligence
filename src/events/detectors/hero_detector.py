from src.events.utils import region_changed

def hero_changed(previous, current, geometry):
    """
    Returns True if either hero card region changed.
    """

    for rect in geometry["hero_cards"].values():
        if region_changed(previous, current, rect):
            return True

    return False
