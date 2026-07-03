from src.events.utils import region_changed

def stack_changed(previous, current, geometry):
    """
    Returns a list of seats whose stack region changed.
    """

    changed = []

    for seat, rect in geometry["stack_regions"].items():
        if region_changed(previous, current, rect):
            changed.append(seat)

    return changed
