from pathlib import Path
import base64, json, subprocess, cv2, sys
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT = ROOT / "runtime/api/latest_table_snapshot.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

client = OpenAI(timeout=45.0)

PROMPT = """
Read ONLY the current table snapshot from this ACR poker screenshot.

Return RAW JSON ONLY:
{
  "hero_position":"",
  "dealer_button_seat":"",
  "players":[
    {
      "seat":"",
      "name":"",
      "stack_text":"",
      "stack_bb":null,
      "is_hero":false,
      "is_active":true
    }
  ],
  "confidence":0.0
}

Rules:
- Hero is always the bottom-center player only.
- Do NOT label the bottom-left player as hero.
- The hero seat is directly above the Fold/Call/Raise buttons at the bottom center.
- Identify occupied seats only.
- Use seat labels exactly:
  seat_top,
  seat_upper_right,
  seat_mid_right,
  seat_lower_right,
  hero,
  seat_lower_left,
  seat_mid_left,
  seat_upper_left
- hero_position should be BTN, SB, BB, UTG, HJ, CO, or unknown if uncertain.
- dealer_button_seat should use the same seat labels or "" if uncertain.
- stack_text should preserve what is visible, for example "42.5 BB" or "12,340".
- stack_bb should be a number only if clear, otherwise null.
- Do not read board cards.
- Do not read hero cards.
- Do not infer hidden information.
- Do not guess names or stacks. Use "" or null when uncertain.
"""

def data_url(path):
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def prepare_images(path):
    img = cv2.imread(str(path))
    img = cv2.resize(img, (934, 696))

    table = ROOT / "runtime/api/table_snapshot_full.jpg"
    cv2.imwrite(str(table), img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])

    # Large table crop focused on seats/stacks/names.
    table_crop = img[45:630, 20:915]
    table_crop = cv2.resize(table_crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    crop_path = ROOT / "runtime/api/table_snapshot_crop.jpg"
    cv2.imwrite(str(crop_path), table_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

    return table, crop_path

if len(sys.argv) > 1:
    latest = Path(sys.argv[1]).expanduser().resolve()
else:
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True)
    latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]
table, crop = prepare_images(latest)

response = client.responses.create(
    model="gpt-4.1-mini",
    input=[{
        "role": "user",
        "content": [
            {"type": "input_text", "text": PROMPT},
            {"type": "input_image", "image_url": data_url(table)},
            {"type": "input_image", "image_url": data_url(crop)}
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
