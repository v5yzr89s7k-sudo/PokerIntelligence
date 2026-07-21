def validate_unique_player_identities(players):
    """
    Reject a snapshot that assigns the same named player to multiple seats.

    Empty names are ignored because OCR may legitimately fail to read a
    player name. This function never fills, copies, or substitutes players.
    """
    seen_names = {}
    duplicates = []

    for player in players or []:
        if not isinstance(player, dict):
            continue

        seat = str(player.get("seat") or "").strip()
        name = str(player.get("name") or "").strip()

        if not seat or not name:
            continue

        prior_seat = seen_names.get(name)

        if prior_seat is not None and prior_seat != seat:
            duplicates.append({
                "name": name,
                "first_seat": prior_seat,
                "duplicate_seat": seat,
            })
        else:
            seen_names[name] = seat

    if duplicates:
        raise RuntimeError(
            "snapshot contains duplicated player identity across seats: "
            f"{duplicates}"
        )

    return True
