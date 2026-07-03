from pathlib import Path
import base64
import json
import subprocess
import cv2
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT = ROOT / "runtime/api/latest_vision_state.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

client = OpenAI(timeout=45.0)

PROMPT = """
You are reading a screenshot from America's Cardroom (ACR).

Rules:

1. Hero ALWAYS sits at the bottom center.
2. Hero hole cards are ALWAYS the two cards at the bottom center. Read rank and suit separately. Carefully distinguish clubs from spades.
3. Read hero cards FIRST.
4. Then determine:
   - street
   - board cards
   - dealer button
   - stacks (BB)
   - visible bets
5. If something is unreadable, return "".
6. Never invent cards.
7. Return RAW JSON ONLY.
8. Do NOT wrap the JSON in markdown.

Schema:

{
  "hero_cards": ["",""],
  "board": [],
  "street": "",
  "pot": "",
  "dealer_button_seat": "",
  "players": [
    {
      "seat":"",
      "name":"",
      "stack_bb":""
    }
  ],
  "visible_bets": [],
  "confidence": 0.0
}
"""

def latest_capture():
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True)
    return sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]

def image_data_url(path):
    img = cv2.imread(str(path))
    img = cv2.resize(img, (934, 696))
    tmp = ROOT / "runtime/api/api_frame.jpg"
    cv2.imwrite(str(tmp), img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    b64 = base64.b64encode(tmp.read_bytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def main():
    image_path = latest_capture()

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": PROMPT},
                {"type": "input_image", "image_url": image_data_url(image_path)}
            ]
        }],
    )

    text = response.output_text.strip()
    print(text)

    if text.startswith("```"):
        text = text.split("```json")[-1].split("```")[0].strip()

    try:
        data = json.loads(text)
        OUT.write_text(json.dumps(data, indent=2))
        print(f"Saved {OUT}")
    except Exception:
        OUT.write_text(json.dumps({"raw": text}, indent=2))
        print(f"Saved raw response to {OUT}")

if __name__ == "__main__":
    main()
