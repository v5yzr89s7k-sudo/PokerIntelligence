from pathlib import Path
from time import perf_counter
import base64, json, os, subprocess, cv2, sys
from openai import OpenAI

PROCESS_T0 = perf_counter()


def profile(stage, started_at, **extra):
    elapsed_ms = (perf_counter() - started_at) * 1000.0
    fields = " ".join(f"{key}={value}" for key, value in extra.items())
    suffix = f" {fields}" if fields else ""

    print(
        f"[BOARD_READER_PROFILE] {stage}={elapsed_ms:.1f}ms{suffix}",
        file=sys.stderr,
        flush=True,
    )

    return elapsed_ms

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT = ROOT / "runtime/api/latest_board.json"
GEOMETRY = ROOT / "config/geometry.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

geometry = json.loads(GEOMETRY.read_text())
board_api_crop = geometry["board_api_crop"]

client_t0 = perf_counter()
client = OpenAI(timeout=45.0)
profile("client_init", client_t0)

PROMPT = """
Read ONLY the board/community cards from this ACR screenshot.

The image is an enlarged crop of the board area.
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
    prepare_t0 = perf_counter()

    t0 = perf_counter()
    img = cv2.imread(str(path))
    if img is None:
        raise RuntimeError(f"could not read image: {path}")
    profile("image_read", t0, file=path.name)

    t0 = perf_counter()
    img = cv2.resize(img, (934, 696))
    profile("table_resize", t0)

    x = int(board_api_crop["x"])
    y = int(board_api_crop["y"])
    width = int(board_api_crop["width"])
    height = int(board_api_crop["height"])

    t0 = perf_counter()
    board = img[y:y + height, x:x + width]
    board = cv2.resize(
        board,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC,
    )
    profile(
        "board_crop_resize",
        t0,
        width=board.shape[1],
        height=board.shape[0],
    )

    board_path = ROOT / "runtime/api/board_crop_enlarged.jpg"

    t0 = perf_counter()
    ok = cv2.imwrite(
        str(board_path),
        board,
        [int(cv2.IMWRITE_JPEG_QUALITY), 90],
    )
    if not ok:
        raise RuntimeError(f"could not write image: {board_path}")
    profile("board_jpeg_write", t0, bytes=board_path.stat().st_size)

    profile("prepare_images_total", prepare_t0)
    return board_path

if len(sys.argv) > 1:
    latest = Path(sys.argv[1]).expanduser().resolve()
else:
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True)
    latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]
prepare_t0 = perf_counter()
board_crop = prepare_images(latest)
profile("prepare_call_total", prepare_t0)

crop_url_t0 = perf_counter()
board_crop_url = data_url(board_crop)
profile("crop_data_url_total", crop_url_t0)

image_mode = "expanded_crop"

request_content = [
    {"type": "input_text", "text": PROMPT},
    {"type": "input_image", "image_url": board_crop_url},
]

print(
    f"[BOARD_READER_PROFILE] image_mode={image_mode} "
    f"image_count={sum(1 for item in request_content if item['type'] == 'input_image')}",
    file=sys.stderr,
    flush=True,
)

api_t0 = perf_counter()
response = client.responses.create(
    model="gpt-4.1-mini",
    input=[{
        "role": "user",
        "content": request_content,
    }],
)
profile("api_request", api_t0)

text = response.output_text.strip()
print(text)

if text.startswith("```"):
    text = text.split("```json")[-1].split("```")[0].strip()

parse_t0 = perf_counter()
data = json.loads(text)
profile("json_parse", parse_t0)

write_t0 = perf_counter()
OUT.write_text(json.dumps(data, indent=2))
profile("result_write", write_t0)

profile("process_total", PROCESS_T0)
print(f"Saved {OUT}")
