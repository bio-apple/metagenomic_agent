"""Context memory: persist paths, metadata, and intermediate artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ContextMemory:
    def __init__(self, workdir: str | Path):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.path = self.workdir / "context.json"
        self._data: dict[str, Any] = {
            "samples": [],
            "artifacts": {},
            "history": [],
            "dag": [],
        }
        if self.path.exists():
            self._data = json.loads(self.path.read_text())

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if key in {"artifacts"} and isinstance(value, dict):
                self._data.setdefault("artifacts", {}).update(value)
            else:
                self._data[key] = value
        self.flush()

    def append_history(self, event: str) -> None:
        self._data.setdefault("history", []).append(event)
        self.flush()

    def flush(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))

    @property
    def data(self) -> dict[str, Any]:
        return self._data
