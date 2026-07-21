"""Lightweight resource / progress logging helpers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class ProgressEvent:
    step: str
    message: str
    ts: float


class Monitor:
    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    def log(self, step: str, message: str) -> None:
        self.events.append(ProgressEvent(step=step, message=message, ts=time.time()))

    def snapshot(self) -> dict:
        return {
            "pid": os.getpid(),
            "cpus": os.cpu_count(),
            "events": [e.__dict__ for e in self.events[-50:]],
        }
