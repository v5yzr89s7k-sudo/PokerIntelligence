import cv2


def crop(img, rect):
    x, y, w, h = map(int, [rect["x"], rect["y"], rect["width"], rect["height"]])
    return img[y:y+h, x:x+w]


def card_present(card_crop):
    gray = cv2.cvtColor(card_crop, cv2.COLOR_BGR2GRAY)
    return (gray > 145).mean() > 0.08


def count_board_cards(frame, geometry):
    count = 0
    for rect in geometry.get("board", {}).values():
        if card_present(crop(frame, rect)):
            count += 1
    return count


def hero_cards_visible(frame, geometry):
    hero = geometry.get("hero_cards") or geometry.get("hole_cards", {}).get("hero", {})
    if not hero:
        return False

    seen = 0
    for rect in hero.values():
        if card_present(crop(frame, rect)):
            seen += 1

    return seen >= 2
