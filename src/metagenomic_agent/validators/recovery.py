"""Error classification and DAG parameter recovery."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def plan_recovery(state: dict[str, Any], technical: dict[str, Any], biological: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    for sid, info in technical.get("samples", {}).items():
        if info.get("host_fraction", 0) > state.get("config", {}).get("validation", {}).get("max_host_fraction", 0.95):
            actions.append(f"relax_host_filter:{sid}")
        if info.get("read_retention", 1) < state.get("config", {}).get("validation", {}).get("min_read_retention", 0.3):
            actions.append(f"loosen_qc:{sid}")
        if not info.get("abundance_ok", True):
            actions.append("switch_taxonomy_tool")
    if not biological.get("ok", True):
        actions.append("lower_kraken_confidence")
    if state.get("artifacts", {}).get("errors"):
        actions.append("retry_failed_nodes")
    return list(dict.fromkeys(actions))


def apply_recovery(dag: list[dict[str, Any]], actions: list[str]) -> list[dict[str, Any]]:
    new_dag = deepcopy(dag)
    for node in new_dag:
        node["status"] = "pending"
        if node["agent"] == "taxonomy":
            if "lower_kraken_confidence" in actions:
                node.setdefault("params", {})["confidence"] = max(
                    0.0, float(node.get("params", {}).get("confidence", 0.05)) - 0.02
                )
            if "switch_taxonomy_tool" in actions:
                tools = list(node.get("tools") or [])
                if "kraken2" in tools and "metaphlan" not in tools:
                    tools.append("metaphlan")
                node["tools"] = tools
                node.setdefault("params", {})["tools"] = tools
        if node["agent"] == "qc_host" and "loosen_qc" in actions:
            node.setdefault("params", {})["qualified_quality_phred"] = 15
        if "retry_failed_nodes" in actions and node.get("status") == "failed":
            node["status"] = "pending"
    return new_dag
