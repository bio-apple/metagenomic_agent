"""Tool registry decision helpers — domain KB + resource-aware selection."""

from __future__ import annotations

from typing import Any

from metagenomic_agent.knowledge.domain_kb import recommend_tools
from metagenomic_agent.skills.registry import SKILLS, get_skill, list_skills


def decide_taxonomy_tools(context: dict[str, Any]) -> list[str]:
    """Combine domain KB recommendations with resource heuristics."""
    query = str(context.get("query") or "")
    memory_gb = float(context.get("memory_gb") or 32)
    n_samples = int(context.get("n_samples") or 1)
    read_length = float(context.get("read_length") or 150)
    prefer_accuracy = bool(context.get("prefer_accuracy", False))

    domain_recs = [t["tool"] for t in recommend_tools(query, context)]
    executable = {"kraken2", "metaphlan", "microcafe", "microrag"}
    picked = [t for t in domain_recs if t in executable]

    if read_length >= 5000:
        return ["microcafe"]
    if memory_gb < 16:
        return ["kraken2"]
    if prefer_accuracy and n_samples <= 40:
        return list(dict.fromkeys(["metaphlan"] + picked)) or ["metaphlan"]
    if n_samples >= 100:
        return ["kraken2"]
    if picked:
        return list(dict.fromkeys(picked))[:3]
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
