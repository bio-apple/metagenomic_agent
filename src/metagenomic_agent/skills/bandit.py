"""Epsilon-greedy tool bandit — adaptive skill selection from historical performance."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolProfile:
    name: str
    trials: int = 0
    successes: int = 0
    quality_sum: float = 0.0
    match_sum: float = 0.0

    @property
    def quality_score(self) -> float:
        return self.quality_sum / self.trials if self.trials else 0.5

    @property
    def match_ratio(self) -> float:
        return self.match_sum / self.trials if self.trials else 0.5

    @property
    def score(self) -> float:
        # Combined exploitation score
        return 0.6 * self.quality_score + 0.4 * self.match_ratio


@dataclass
class EpsilonGreedyBandit:
    epsilon: float = 0.15
    profiles: dict[str, ToolProfile] = field(default_factory=dict)
    path: Path | None = None

    def ensure(self, name: str) -> ToolProfile:
        if name not in self.profiles:
            self.profiles[name] = ToolProfile(name=name)
        return self.profiles[name]

    def select(self, candidates: list[str], rng: random.Random | None = None) -> str:
        rng = rng or random.Random()
        if not candidates:
            raise ValueError("No candidates")
        for c in candidates:
            self.ensure(c)
        if rng.random() < self.epsilon:
            return rng.choice(candidates)  # explore
        return max(candidates, key=lambda c: self.ensure(c).score)

    def update(self, name: str, *, success: bool, quality: float = 0.0, match: float = 0.0) -> None:
        p = self.ensure(name)
        p.trials += 1
        if success:
            p.successes += 1
        p.quality_sum += quality
        p.match_sum += match
        self.save()

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            n: {
                "trials": p.trials,
                "successes": p.successes,
                "quality_sum": p.quality_sum,
                "match_sum": p.match_sum,
            }
            for n, p in self.profiles.items()
        }
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, epsilon: float = 0.15) -> EpsilonGreedyBandit:
        bandit = cls(epsilon=epsilon, path=path)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            for n, d in raw.items():
                bandit.profiles[n] = ToolProfile(name=n, **d)
        return bandit

    def to_dict(self) -> dict[str, Any]:
        return {
            n: {
                "trials": p.trials,
                "quality_score": round(p.quality_score, 4),
                "match_ratio": round(p.match_ratio, 4),
                "score": round(p.score, 4),
            }
            for n, p in self.profiles.items()
        }
