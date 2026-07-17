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
        f"[HERO_READER_PROFILE] {stage}={elapsed_ms:.1f}ms{suffix}",
        file=sys.stderr,
        flush=True,
    )
    return elapsed_ms

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
OUT = ROOT / "runtime/api/latest_hero_cards.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

client_t0 = perf_counter()
client = OpenAI(timeout=45.0)
profile("client_init", client_t0)

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
    t0 = perf_counter()
    raw = path.read_bytes()
    read_ms = (perf_counter() - t0) * 1000.0

    encode_t0 = perf_counter()
    b64 = base64.b64encode(raw).decode("utf-8")
    encode_ms = (perf_counter() - encode_t0) * 1000.0

    print(
        f"[HERO_READER_PROFILE] data_url "
        f"file={path.name} bytes={len(raw)} "
        f"read={read_ms:.1f}ms encode={encode_ms:.1f}ms",
        file=sys.stderr,
        flush=True,
    )

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

    table = ROOT / "runtime/api/table_frame.jpg"

    t0 = perf_counter()
    ok = cv2.imwrite(
        str(table),
        img,
        [int(cv2.IMWRITE_JPEG_QUALITY), 65],
    )
    if not ok:
        raise RuntimeError(f"could not write image: {table}")
    profile("table_jpeg_write", t0, bytes=table.stat().st_size)

    t0 = perf_counter()
    with open(ROOT / "config/geometry.json") as f:
        geometry = json.load(f)
    profile("geometry_load", t0)
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

    t0 = perf_counter()
    hero = img[y1:y2, x1:x2]
    hero = cv2.resize(
        hero,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC,
    )
    profile(
        "hero_crop_resize",
        t0,
        width=hero.shape[1],
        height=hero.shape[0],
    )

    hero_path = ROOT / "runtime/api/hero_crop_enlarged.jpg"

    t0 = perf_counter()
    ok = cv2.imwrite(
        str(hero_path),
        hero,
        [int(cv2.IMWRITE_JPEG_QUALITY), 90],
    )
    if not ok:
        raise RuntimeError(f"could not write image: {hero_path}")
    profile("hero_jpeg_write", t0, bytes=hero_path.stat().st_size)

    profile("prepare_images_total", prepare_t0)
    return table, hero_path

selection_t0 = perf_counter()

if len(sys.argv) > 1:
    latest = Path(sys.argv[1]).expanduser().resolve()
else:
    capture_t0 = perf_counter()
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True)
    profile("capture_subprocess", capture_t0)
    latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]

profile("frame_selection", selection_t0, file=latest.name)

prepare_t0 = perf_counter()
table, hero_crop = prepare_images(latest)
profile("prepare_call_total", prepare_t0)

table_url_t0 = perf_counter()
table_url = data_url(table)
profile("table_data_url_total", table_url_t0)

crop_url_t0 = perf_counter()
hero_crop_url = data_url(hero_crop)
profile("crop_data_url_total", crop_url_t0)

image_mode = os.environ.get("HERO_IMAGE_MODE", "both").strip().lower()

if image_mode == "crop":
    request_content = [
        {"type": "input_text", "text": PROMPT},
        {"type": "input_image", "image_url": hero_crop_url},
    ]
elif image_mode == "both":
    request_content = [
        {"type": "input_text", "text": PROMPT},
        {"type": "input_image", "image_url": table_url},
        {"type": "input_image", "image_url": hero_crop_url},
    ]
else:
    raise ValueError(
        f"unsupported HERO_IMAGE_MODE={image_mode!r}; "
        f"expected 'both' or 'crop'"
    )

print(
    f"[HERO_READER_PROFILE] image_mode={image_mode} "
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

extract_t0 = perf_counter()
text = response.output_text.strip()
profile("response_text_extract", extract_t0, chars=len(text))

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
