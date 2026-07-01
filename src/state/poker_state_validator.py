class PokerStateValidator:
    STREET_ORDER = {"PREFLOP": 0, "FLOP": 1, "TURN": 2, "RIVER": 3}

    def __init__(self):
        self.stable = {
            "street": None,
            "board_count": 0,
            "hero_cards_present": [],
            "pot": {},
            "stacks": {},
            "bets": {},
        }

    def validate_street(self, street):
        old = self.stable["street"]
        if old is None:
            self.stable["street"] = street
            return street, True

        if street == "PREFLOP" and old in {"FLOP", "TURN", "RIVER"}:
            self.stable["street"] = street
            self.stable["board_count"] = 0
            self.stable["hero_cards_present"] = []
            self.stable["bets"] = {}
            return street, True

        if self.STREET_ORDER.get(street, -1) >= self.STREET_ORDER.get(old, -1):
            if street != old:
                self.stable["street"] = street
                return street, True
            return old, False

        return old, False

    def validate_board_count(self, count):
        old = self.stable["board_count"]

        if old == count:
            return old, False

        allowed = (
            (old == 0 and count in {0, 3}) or
            (old == 3 and count in {3, 4}) or
            (old == 4 and count in {4, 5}) or
            (old == 5 and count == 0)
        )

        if allowed:
            self.stable["board_count"] = count
            return count, True

        return old, False

    def validate_hero_cards(self, cards):
        old = self.stable["hero_cards_present"]

        if len(cards) == 1:
            return old, False

        if cards != old:
            self.stable["hero_cards_present"] = cards
            return cards, True

        return old, False

    def validate_pot(self, pot):
        old = self.stable["pot"]

        clean = {}
        for name, value in pot.items():
            try:
                v = float(value)
            except Exception:
                continue

            # Reject OCR garbage / empty pot reads like 00.
            if 0.1 <= v <= 300:
                clean[name] = value

        if not clean:
            return old, False

        if clean != old:
            self.stable["pot"] = clean
            return clean, True

        return old, False

    def _valid_stack_change(self, old_value, new_value):
        try:
            old = float(old_value)
            new = float(new_value)
        except Exception:
            return False

        diff = abs(new - old)

        if diff == 0:
            return False

        if diff < 0.25:
            return False

        if new < 0.25 or new > 300:
            return False

        if diff > 20:
            return False

        return True

    def validate_stacks(self, stacks):
        stable = dict(self.stable["stacks"])
        changed = {}

        for seat, value in stacks.items():
            old = stable.get(seat)

            if old is None:
                try:
                    v = float(value)
                except Exception:
                    continue

                # BB-display sanity filter.
                # Reject OCR garbage like 19875 when stacks should be shown in BB.
                if 0.25 <= v <= 300:
                    stable[seat] = value
                    changed[seat] = ("NEW", value)
                continue

            if self._valid_stack_change(old, value):
                stable[seat] = value
                changed[seat] = (old, value)

        self.stable["stacks"] = stable
        return stable, changed

    def validate_bets(self, bets):
        old = self.stable["bets"]

        clean = {}
        for seat, value in bets.items():
            try:
                v = float(value)
            except Exception:
                continue

            # Visible bet amounts are in BB. Reject OCR garbage like 632/635/0.
            if 0.25 <= v <= 100:
                clean[seat] = value

        if clean != old:
            self.stable["bets"] = clean
            return clean, True

        return old, False

    def _street_from_board_count(self, count):
        if count >= 5:
            return "RIVER"
        if count == 4:
            return "TURN"
        if count == 3:
            return "FLOP"
        return "PREFLOP"

    def validate(self, raw):
        stable_board_count, board_changed = self.validate_board_count(raw["board_count"])
        derived_street = self._street_from_board_count(stable_board_count)
        stable_street, street_changed = self.validate_street(derived_street)
        stable_hero_cards, hero_cards_changed = self.validate_hero_cards(raw["hero_cards_present"])
        stable_pot, pot_changed = self.validate_pot(raw["pot"])
        stable_stacks, stack_changes = self.validate_stacks(raw["stacks"])
        stable_bets, bets_changed = self.validate_bets(raw["bets"])

        stable = {
            **raw,
            "street": stable_street,
            "board_count": stable_board_count,
            "hero_cards_present": stable_hero_cards,
            "pot": stable_pot,
            "stacks": stable_stacks,
            "bets": stable_bets,
        }

        changes = {
            "street_changed": street_changed,
            "board_changed": board_changed,
            "hero_cards_changed": hero_cards_changed,
            "pot_changed": pot_changed,
            "bets_changed": bets_changed,
            "stack_changes": stack_changes,
        }

        return stable, changes
