
from pathlib import Path
from unittest.mock import patch
import src.v017.run_live_observer as live
from src.v017.pixel_lab.observer_runner import run

root = Path(
    "runtime/debug/v018_native_qq_confirmation/native20_run_1"
).resolve()
root.mkdir(parents=True, exist_ok=True)

original_record = live.record_publication

def isolated_record(publication, timestamp):
    return original_record(
        publication,
        timestamp,
        path=root / "progression.jsonl",
    )

with patch.object(
    live, "CURRENT_HAND", root / "current_hand.txt"
), patch.object(
    live, "LATENCY_TRACE", root / "latency.jsonl"
), patch.object(
    live, "record_publication", isolated_record
):
    result = run(
        observer_input=Path(
            "runtime/pixel_lab/generator_work/real_acr_hand_2826874674/run_a"
        ),
        publish_live_product=False,
        publication_dir=root / "publications",
                 identity_fixture=Path(
    "src/v017/validation/native20/identity_fixture.json"
),
    )

print("FINAL_STREET=", result["observer"].hand.street)
print(
    "FINAL_ACTIONS=",
    len(result["observer"].hand.semantic_actions())
)
