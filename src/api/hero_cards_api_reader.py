from pathlib import Path
import base64, json, subprocess, cv2, sys
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT = ROOT / "runtime/api/latest_hero_cards.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

client = OpenAI(timeout=45.0)

PROMPT = """
Read ONLY the hero hole cards from this ACR screenshot.

Hero ALWAYS sits bottom center.
The second image is an enlarged crop of ONLY the two hero cards. Use it to verify suits.

Return RAW JSON ONLY:
{"hero_cards":["",""],"confidence":0.0}

Use ASCII only: Ah, Ad, Ac, As, Td, 7s.
Read rank and suit separately.
Carefully distinguish hearts from diamonds.
Carefully distinguish clubs from spades.
Do not guess. Use "" if uncertain.
"""

def data_url(path):
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def prepare_images(path):
    img = cv2.imread(str(path))
    img = cv2.resize(img, (934, 696))

    table = ROOT / "runtime/api/table_frame.jpg"
    cv2.imwrite(str(table), img, [int(cv2.IMWRITE_JPEG_QUALITY), 65])

    geometry = json.load(open(ROOT / "config/geometry.json"))
    hero_cards = geometry.get("hero_cards") or geometry.get("hole_cards", {}).get("hero", {})

    xs = [r["x"] for r in hero_cards.values()]
    ys = [r["y"] for r in hero_cards.values()]
    x2s = [r["x"] + r["width"] for r in hero_cards.values()]
    y2s = [r["y"] + r["height"] for r in hero_cards.values()]

    pad = 12
    x1 = max(0, int(min(xs) - pad))
    y1 = max(0, int(min(ys) - pad))
    x2 = min(img.shape[1], int(max(x2s) + pad))
    y2 = min(img.shape[0], int(max(y2s) + pad))

    hero = img[y1:y2, x1:x2]
    hero = cv2.resize(hero, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    hero_path = ROOT / "runtime/api/hero_crop_enlarged.jpg"
    cv2.imwrite(str(hero_path), hero, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

    return table, hero_path

if len(sys.argv) > 1:
    latest = Path(sys.argv[1]).expanduser().resolve()
else:
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True)
    latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]
table, hero_crop = prepare_images(latest)

response = client.responses.create(
    model="gpt-4.1-mini",
    input=[{
        "role": "user",
        "content": [
            {"type": "input_text", "text": PROMPT},
            {"type": "input_image", "image_url": data_url(table)},
            {"type": "input_image", "image_url": data_url(hero_crop)}
        ]
    }],
)

text = response.output_text.strip()
print(text)

if text.startswith("```"):
    text = text.split("```json")[-1].split("```")[0].strip()

data = json.loads(text)
OUT.write_text(json.dumps(data, indent=2))
print(f"Saved {OUT}")
