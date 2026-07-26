from src.events.utils import region_changed

def dealer_changed(previous, current, geometry):
    """Detect changes in any configured dealer-button zone.

    Supports both legacy single-zone geometry and the newer
    multiple-zones-per-seat geometry.
    """
    for zone_value in geometry["dealer_button_zones"].values():
        zones = zone_value if isinstance(zone_value, list) else [zone_value]

        for rect in zones:
            if region_changed(previous, current, rect):
                return True

    return False
