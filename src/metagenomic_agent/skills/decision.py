"""Tool registry decision helpers — memory/resource-aware skill selection."""

from __future__ import annotations

from typing import Any

from metagenomic_agent.skills.registry import SKILLS, get_skill, list_skills


def decide_taxonomy_tools(context: dict[str, Any]) -> list[str]:
    """
    Heuristic auto-decision:
    - low memory → kraken2
    - high accuracy / small cohort → metaphlan
    - large cohort → kraken2 (+ optional bracken implied)
    - long reads → microcafe
    """
    memory_gb = float(context.get("memory_gb") or 32)
    n_samples = int(context.get("n_samples") or 1)
    read_length = float(context.get("read_length") or 150)
    prefer_accuracy = bool(context.get("prefer_accuracy", False))

    if read_length >= 5000:
        return ["microcafe"]
    if memory_gb < 16:
        return ["kraken2"]
    if prefer_accuracy and n_samples <= 40:
        return ["metaphlan"]
    if n_samples >= 100:
        return ["kraken2"]
    return ["kraken2", "metaphlan"]


def describe_registry() -> list[dict[str, Any]]:
    rows = []
    for name in list_skills():
        sk = get_skill(name)
        assert sk is not None
        rows.append(
            {
                "name": sk.name,
                "description": sk.description,
                "tags": sk.tags,
                "input": sk.input_contract.__dict__ if hasattr(sk.input_contract, "__dict__") else {},
            }
        )
    return rows


__all__ = ["SKILLS", "decide_taxonomy_tools", "describe_registry", "get_skill", "list_skills"]
