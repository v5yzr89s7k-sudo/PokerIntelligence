from pathlib import Path
import base64, json, subprocess, cv2, sys
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT = ROOT / "runtime/api/latest_board.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

client = OpenAI(timeout=45.0)

PROMPT = """
Read ONLY the board/community cards from this ACR screenshot.

The second image is an enlarged crop of the board area.
Return RAW JSON ONLY:
{"board":[],"street":"","confidence":0.0}

Use ASCII card notation only: Ah, Ad, Ac, As, Td, 7s.
Board should contain 0, 3, 4, or 5 cards.
Use [] if no board cards are visible.
Do not guess.
"""

def data_url(path):
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def prepare_images(path):
    img = cv2.imread(str(path))
    img = cv2.resize(img, (934, 696))

    table = ROOT / "runtime/api/table_frame.jpg"
    cv2.imwrite(str(table), img, [int(cv2.IMWRITE_JPEG_QUALITY), 65])

    board = img[245:360, 300:640]
    board = cv2.resize(board, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    board_path = ROOT / "runtime/api/board_crop_enlarged.jpg"
    cv2.imwrite(str(board_path), board, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

    return table, board_path

if len(sys.argv) > 1:
    latest = Path(sys.argv[1]).expanduser().resolve()
else:
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True)
    latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]
table, board_crop = prepare_images(latest)

response = client.responses.create(
    model="gpt-4.1-mini",
    input=[{
        "role": "user",
        "content": [
            {"type": "input_text", "text": PROMPT},
            {"type": "input_image", "image_url": data_url(table)},
            {"type": "input_image", "image_url": data_url(board_crop)}
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
