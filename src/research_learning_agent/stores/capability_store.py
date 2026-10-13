"""Persistent storage for learner capability profiles."""
from __future__ import annotations

import json
from pathlib import Path

from research_learning_agent.programming_schemas import CapabilityProfile


DATA_DIR = Path("data")
DEFAULT_PATH = DATA_DIR / "capability_profiles.json"


class CapabilityStore:
    """Loads/saves CapabilityProfile objects keyed by user_id."""

    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = path
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def load(self, user_id: str = "default") -> CapabilityProfile | None:
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        profiles = data if isinstance(data, dict) else {}
        raw = profiles.get(user_id)
        if raw is None:
            return None
        return CapabilityProfile.model_validate(raw)

    def save(self, profile: CapabilityProfile) -> None:
        data: dict = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        if not isinstance(data, dict):
            data = {}
        data[profile.user_id] = profile.model_dump()
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
