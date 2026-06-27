# PokerIntelligence v0.3

Local Mac proof-of-concept for ACR table reading.

## What v0.3 does

- Watches a screenshot folder.
- Can also take periodic screenshots automatically using macOS `screencapture`.
- Runs OCR on ACR-specific screen regions.
- Writes:
  - `output/latest_state.json`
  - `output/latest_hand.txt`
  - `output/session_log.jsonl`
  - debug crops in `output/debug_crops/`

## Run watcher only

```bash
cd ~/Projects/PokerIntelligence
python3 src/screenshot_watcher.py
```

## Run automatic capture + processing

```bash
cd ~/Projects/PokerIntelligence
python3 src/capture_loop.py
```

Stop with Ctrl+C.

## Important

This is screen reading and logging only. It does not click buttons, type into ACR, or interact with gameplay.

## Calibration workflow

1. Run `python3 src/capture_loop.py`.
2. Let it capture an active ACR hand.
3. Open `output/debug_crops`.
4. Inspect whether each crop captures the intended area.
5. Adjust `regions_relative` in `config.json` if needed.
