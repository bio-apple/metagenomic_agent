"""Intelligent taxonomy tool routing: long-read → gLM, short-read → classic / dual-path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.skills.bandit import EpsilonGreedyBandit


LONG_READ_BP = 5000


def detect_read_features(samples: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [int(s.get("read_length_est") or 150) for s in samples]
    avg = sum(lengths) / len(lengths) if lengths else 150
    return {
        "avg_read_length": avg,
        "max_read_length": max(lengths) if lengths else 150,
        "is_long_read": avg >= LONG_READ_BP or (max(lengths) if lengths else 0) >= LONG_READ_BP,
        "n_samples": len(samples),
    }


def route_taxonomy_tools(
    samples: list[dict[str, Any]],
    config: dict[str, Any],
    requested: list[str] | None = None,
    outdir: str | Path | None = None,
) -> dict[str, Any]:
    """Return selected tools + routing rationale."""
    features = detect_read_features(samples)
    cfg = config.get("routing", {}) or {}
    dual = bool(cfg.get("dual_path", True))
    enable_glm = bool(cfg.get("enable_glm", True))
    epsilon = float(cfg.get("epsilon", 0.15))

    bandit_path = Path(outdir or ".") / "context" / "tool_bandit.json"
    bandit = EpsilonGreedyBandit.load(bandit_path, epsilon=epsilon)

    short_pool = list(requested or cfg.get("short_read_tools") or ["kraken2", "metaphlan"])
    long_pool = list(cfg.get("long_read_tools") or ["microcafe", "microrag"])

    if features["is_long_read"] and enable_glm:
        primary = bandit.select(long_pool)
        tools = [primary]
        strategy = "long_read_glm"
        if dual and "kraken2" not in tools:
            # optional classic companion for fusion
            tools.append(bandit.select(["kraken2", "metaphlan"]))
            strategy = "long_read_glm_dual"
    else:
        primary = bandit.select(short_pool)
        tools = [primary]
        strategy = "short_read_classic"
        if dual:
            for t in short_pool:
                if t not in tools:
                    tools.append(t)
                    break
            if enable_glm and cfg.get("short_read_glm_assist", False):
                tools.append("microrag")
                strategy = "short_read_dual_plus_glm"

    return {
        "tools": list(dict.fromkeys(tools)),
        "strategy": strategy,
        "features": features,
        "bandit": bandit.to_dict(),
        "bandit_path": str(bandit_path),
    }
