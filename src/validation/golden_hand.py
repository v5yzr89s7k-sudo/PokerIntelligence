from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import json


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_HANDS_ROOT = ROOT / "runtime" / "golden_hands"


class GoldenHandError(RuntimeError):
    """Raised when a golden-hand fixture is missing or invalid."""


@dataclass(frozen=True)
class GoldenHand:
    root: Path
    name: str
    metadata_path: Path
    frames_dir: Path
    expected_path: Path
    events_path: Path

    @classmethod
    def load(cls, root: Path) -> "GoldenHand":
        root = Path(root).resolve()

        if not root.exists():
            raise GoldenHandError(
                f"golden hand does not exist: {root}"
            )

        if not root.is_dir():
            raise GoldenHandError(
                f"golden hand path is not a directory: {root}"
            )

        metadata_path = root / "metadata.json"
        frames_dir = root / "frames"
        expected_path = root / "expected_current_hand.txt"
        events_path = root / "api_events.jsonl"

        missing = []

        if not metadata_path.is_file():
            missing.append("metadata.json")

        if not expected_path.is_file():
            missing.append("expected_current_hand.txt")

        if not events_path.is_file():
            missing.append("api_events.jsonl")

        if missing:
            raise GoldenHandError(
                f"{root.name}: missing required fixture component(s): "
                + ", ".join(missing)
            )

        hand = cls(
            root=root,
            name=root.name,
            metadata_path=metadata_path,
            frames_dir=frames_dir,
            expected_path=expected_path,
            events_path=events_path,
        )

        # Force validation of fixture metadata at load time.
        hand.metadata()

        return hand

    def metadata(self) -> Dict[str, Any]:
        try:
            data = json.loads(
                self.metadata_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise GoldenHandError(
                f"{self.name}: invalid metadata.json: {exc}"
            ) from exc
        except OSError as exc:
            raise GoldenHandError(
                f"{self.name}: could not read metadata.json: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise GoldenHandError(
                f"{self.name}: metadata.json must contain a JSON object"
            )

        return data

    def event_schema_compatibility(self) -> Dict[str, Any]:
        """
        Classify whether this fixture's recorded evidence schema can
        exercise the current chronology-aware state machine literally.

        Event replay remains evidence-preserving: incompatible legacy
        fixtures are classified here rather than rewritten or augmented.
        """
        metadata = self.metadata()

        try:
            format_version = int(
                metadata.get("format_version", 0)
                or 0
            )
        except (TypeError, ValueError):
            format_version = 0

        event_types = []

        try:
            lines = self.events_path.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError as exc:
            raise GoldenHandError(
                f"{self.name}: could not read api_events.jsonl: {exc}"
            ) from exc

        for line in lines:
            if not line.strip():
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GoldenHandError(
                    f"{self.name}: invalid api event JSON: {exc}"
                ) from exc

            if not isinstance(event, dict):
                raise GoldenHandError(
                    f"{self.name}: api event must be a JSON object"
                )

            event_types.append(
                event.get("type")
            )

        has_inferred_action = (
            "inferred_action"
            in event_types
        )

        has_chronology_transport = any(
            event_type in {
                "actor_observed",
                "physical_actor_completed",
            }
            for event_type in event_types
        )

        # Version 1 predates explicit chronology transport.
        #
        # A v1 fixture that never relies on inferred_action remains
        # replay-compatible: there is no missing quantitative-action
        # chronology to reconstruct.
        #
        # A v1 fixture that DOES contain inferred_action but lacks all
        # chronology transport cannot prove the action ordering required
        # by the current state machine. Do not synthesize that evidence.
        legacy_quantitative_only = (
            format_version == 1
            and has_inferred_action
            and not has_chronology_transport
        )

        if legacy_quantitative_only:
            return {
                "compatible": False,
                "classification": "legacy",
                "reason": (
                    "format v1 quantitative actions lack "
                    "chronology transport"
                ),
                "format_version": format_version,
            }

        return {
            "compatible": True,
            "classification": "current",
            "reason": None,
            "format_version": format_version,
        }


    def frames(self) -> List[Path]:
        """
        Return optional recorded perception frames.

        Canonical event-stream validation does not require frames.
        They may be retained locally for future perception validation.
        """
        if not self.frames_dir.is_dir():
            return []

        return sorted(
            path
            for path in self.frames_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
            }
        )

    def api_events(self) -> str:
        try:
            return self.events_path.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise GoldenHandError(
                f"{self.name}: could not read api_events.jsonl: {exc}"
            ) from exc


    def expected_current_hand(self) -> str:
        try:
            return self.expected_path.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise GoldenHandError(
                f"{self.name}: could not read "
                f"expected_current_hand.txt: {exc}"
            ) from exc


def discover_golden_hands(
    root: Path = GOLDEN_HANDS_ROOT,
) -> List[GoldenHand]:
    root = Path(root)

    if not root.exists():
        return []

    if not root.is_dir():
        raise GoldenHandError(
            f"golden-hands root is not a directory: {root}"
        )

    hand_dirs = sorted(
        path
        for path in root.iterdir()
        if path.is_dir()
        and path.name.startswith("hand_")
    )

    return [
        GoldenHand.load(path)
        for path in hand_dirs
    ]
