from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "runtime/card_templates"

SUIT_CODE = {
    "heart": "h",
    "diamond": "d",
    "club": "c",
    "spade": "s",
}

def prep(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.threshold(gray, 145, 255, cv2.THRESH_BINARY)[1]

def load_templates(folder):
    templates = {}
    for p in sorted(folder.glob("*.png")):
        img = cv2.imread(str(p))
        if img is not None:
            templates[p.stem] = prep(img)
    return templates

def best_match(img, templates):
    img = prep(img)
    best_name = None
    best_score = -999

    for name, tmpl in templates.items():
        resized = cv2.resize(img, (tmpl.shape[1], tmpl.shape[0]), interpolation=cv2.INTER_CUBIC)
        score = cv2.matchTemplate(resized, tmpl, cv2.TM_CCOEFF_NORMED)[0][0]
        if score > best_score:
            best_name = name
            best_score = score

    return best_name, round(float(best_score), 3)

def read_card(card_crop):
    rank_roi = card_crop[0:32, 0:28]
    suit_roi = card_crop[28:58, 0:30]

    rank, rank_score = best_match(rank_roi, load_templates(TEMPLATES / "ranks"))
    suit, suit_score = best_match(suit_roi, load_templates(TEMPLATES / "suits"))

    return {
        "rank": rank,
        "suit": suit,
        "card": f"{rank}{SUIT_CODE.get(suit, '?')}",
        "rank_score": rank_score,
        "suit_score": suit_score,
    }
