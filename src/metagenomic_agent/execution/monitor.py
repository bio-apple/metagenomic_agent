"""Structured event monitor — JSONL observability for agent runs."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProgressEvent:
    step: str
    message: str
    ts: float
    level: str = "info"
    data: dict[str, Any] = field(default_factory=dict)


class Monitor:
    def __init__(self, outdir: str | Path | None = None, run_id: str | None = None) -> None:
        self.events: list[ProgressEvent] = []
        self.run_id = run_id or str(int(time.time()))
        self.outdir = Path(outdir) if outdir else None
        self._jsonl: Path | None = None
        if self.outdir:
            self.outdir.mkdir(parents=True, exist_ok=True)
            self._jsonl = self.outdir / "events.jsonl"

    def log(self, step: str, message: str, level: str = "info", **data: Any) -> None:
        event = ProgressEvent(step=step, message=message, ts=time.time(), level=level, data=data)
        self.events.append(event)
        if self._jsonl:
            record = {"run_id": self.run_id, **asdict(event)}
            with self._jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pid": os.getpid(),
            "cpus": os.cpu_count(),
            "n_events": len(self.events),
            "events": [asdict(e) for e in self.events[-100:]],
            "jsonl": str(self._jsonl) if self._jsonl else None,
        }
