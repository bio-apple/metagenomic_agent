"""Error classification and DAG parameter recovery."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _has_action(actions: list[str], prefix: str) -> bool:
    return any(a == prefix or a.startswith(prefix + ":") for a in actions)


def plan_recovery(state: dict[str, Any], technical: dict[str, Any], biological: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    for sid, info in technical.get("samples", {}).items():
        if info.get("host_fraction", 0) > state.get("config", {}).get("validation", {}).get("max_host_fraction", 0.95):
            actions.append(f"relax_host_filter:{sid}")
        if info.get("read_retention", 1) < state.get("config", {}).get("validation", {}).get("min_read_retention", 0.3):
            actions.append(f"loosen_qc:{sid}")
        if not info.get("abundance_ok", True):
            actions.append("switch_taxonomy_tool")
    for sid, info in technical.get("mags", {}).items():
        if not info.get("ok", True):
            actions.append("downgrade_assembler")
    if not biological.get("ok", True):
        actions.append("lower_kraken_confidence")
    if state.get("artifacts", {}).get("errors"):
        actions.append("retry_failed_nodes")
    return list(dict.fromkeys(actions))


def apply_recovery(dag: list[dict[str, Any]], actions: list[str]) -> list[dict[str, Any]]:
    new_dag = deepcopy(dag)
    failed_ids = {n["id"] for n in dag if n.get("status") == "failed"}
    for node in new_dag:
        # Only reset failed nodes if retry_failed_nodes; otherwise reset all pending/done for param updates
        if "retry_failed_nodes" in actions:
            if node["id"] in failed_ids or node.get("status") == "failed":
                node["status"] = "pending"
        else:
            node["status"] = "pending"

        if node["agent"] == "taxonomy":
            if _has_action(actions, "lower_kraken_confidence"):
                node.setdefault("params", {})["confidence"] = max(
                    0.0, float(node.get("params", {}).get("confidence", 0.05)) - 0.02
                )
            if _has_action(actions, "switch_taxonomy_tool"):
                tools = list(node.get("tools") or [])
                if "metaphlan" not in tools:
                    tools.append("metaphlan")
                node["tools"] = tools
                node.setdefault("params", {})["tools"] = tools
        if node["agent"] in {"qc_host", "qc"} and _has_action(actions, "loosen_qc"):
            node.setdefault("params", {})["qualified_quality_phred"] = 15
        if node["agent"] == "assembly" and _has_action(actions, "downgrade_assembler"):
            node.setdefault("params", {})["assembler"] = "megahit"
    return new_dag
