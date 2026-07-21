"""Context memory: project profile + paths, metadata, and intermediate artifacts."""

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
            "project": {},
            "samples": [],
            "artifacts": {},
            "pipeline_summary": {},
            "history": [],
            "dag": [],
            "run_seed": None,
        }
        if self.path.exists():
            loaded = json.loads(self.path.read_text())
            self._data.update(loaded)

    def set_project_profile(self, profile: dict[str, Any]) -> None:
        self._data["project"] = {**(self._data.get("project") or {}), **profile}
        self.flush()

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if key in {"artifacts"} and isinstance(value, dict):
                self._data.setdefault("artifacts", {}).update(value)
            elif key == "project" and isinstance(value, dict):
                self._data["project"] = {**(self._data.get("project") or {}), **value}
            elif key == "pipeline_summary" and isinstance(value, dict):
                self._data["pipeline_summary"] = value
            else:
                self._data[key] = value
        self.flush()

    def llm_safe_view(self) -> dict[str, Any]:
        """Return a context payload without raw sequence paths' file contents."""
        return {
            "project": self.project,
            "pipeline_summary": self._data.get("pipeline_summary")
            or (self._data.get("artifacts") or {}).get("pipeline_summary")
            or {},
            "run_seed": self._data.get("run_seed"),
            "dag": self._data.get("dag") or [],
            "history_tail": (self._data.get("history") or [])[-20:],
        }

    def append_history(self, event: str) -> None:
        self._data.setdefault("history", []).append(event)
        self.flush()

    def flush(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @property
    def project(self) -> dict[str, Any]:
        return dict(self._data.get("project") or {})
