import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from state_builder import build_state, write_outputs
from ocr_utils import load_config

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}

class ScreenshotHandler(FileSystemEventHandler):
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.seen = set()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in IMAGE_EXTS:
            return
        if path in self.seen:
            return
        self.seen.add(path)
        # Allow macOS to finish writing the file.
        time.sleep(0.4)
        try:
            print(f"Detected screenshot: {path.name}")
            state = build_state(path, self.project_root)
            latest_json, latest_txt = write_outputs(state, self.project_root)
            print(f"Wrote {latest_json}")
            print(f"Wrote {latest_txt}")
        except Exception as e:
            print(f"ERROR processing {path}: {e}")


def main():
    project_root = Path(__file__).resolve().parents[1]
    config = load_config(project_root)
    watch_dir = project_root / config.get("screenshot_folder", "screenshots")
    watch_dir.mkdir(parents=True, exist_ok=True)
    (project_root / config.get("output_folder", "output")).mkdir(parents=True, exist_ok=True)

    print("Poker Intelligence screenshot watcher v0.3")
    print(f"Watching: {watch_dir}")
    print("Drop/save screenshots into that folder.")
    print("Press Ctrl+C to stop.")

    handler = ScreenshotHandler(project_root)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
