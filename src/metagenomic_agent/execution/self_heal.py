"""Self-healing heuristics for bioinformatics tool failures."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


# Exit / classification → recovery actions
HEURISTICS: dict[str, list[str]] = {
    "oom": ["reduce_threads", "reduce_memory", "downgrade_assembler"],
    "timeout": ["reduce_threads", "skip_optional_step"],
    "logic": ["downgrade_assembler", "switch_taxonomy_tool", "loosen_qc"],
    "resource": ["reduce_threads", "reduce_memory"],
    "missing_binary": ["switch_to_mock_fallback"],
}


def classify_from_errors(errors: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for err in errors:
        classified = (err.get("classified") or "").lower()
        msg = (err.get("error") or "").lower()
        rc = err.get("returncode")
        if rc == 137 or classified == "oom" or "out of memory" in msg:
            actions.extend(HEURISTICS["oom"])
        elif classified == "timeout" or "timed out" in msg:
            actions.extend(HEURISTICS["timeout"])
        elif classified == "missing_binary":
            actions.extend(HEURISTICS["missing_binary"])
        elif "spades" in msg or "metaspades" in (err.get("node") or "").lower():
            actions.append("downgrade_assembler")
        else:
            actions.extend(HEURISTICS.get(classified, HEURISTICS["logic"]))
    return list(dict.fromkeys(actions))


def apply_self_heal(dag: list[dict[str, Any]], actions: list[str], config: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Adjust DAG params and runtime config for the next retry."""
    new_dag = deepcopy(dag)
    cfg_patch: dict[str, Any] = {}
    linux = dict((config or {}).get("linux") or {})
    docker = dict((config or {}).get("docker") or {})

    if "reduce_threads" in actions:
        threads = int(docker.get("threads") or linux.get("threads") or 8)
        new_threads = max(2, threads // 2)
        cfg_patch.setdefault("docker", {})["threads"] = new_threads
        cfg_patch.setdefault("linux", {})["threads"] = new_threads
    if "reduce_memory" in actions:
        mem = int(linux.get("memory_gb", 32))
        cfg_patch.setdefault("linux", {})["memory_gb"] = max(8, mem // 2)

    for node in new_dag:
        node["status"] = "pending"
        agent = node.get("agent", "")
        params = node.setdefault("params", {})
        if "downgrade_assembler" in actions and agent == "assembly":
            params["assembler"] = "megahit"  # metaSPAdes → MEGAHIT
            tools = [t for t in (node.get("tools") or []) if t != "metaspades"]
            if "megahit" not in tools:
                tools.insert(0, "megahit")
            node["tools"] = tools
        if "switch_taxonomy_tool" in actions and agent == "taxonomy":
            tools = list(node.get("tools") or [])
            if "metaphlan" not in tools:
                tools.append("metaphlan")
            node["tools"] = tools
            params["tools"] = tools
        if "loosen_qc" in actions and agent in {"qc", "qc_host"}:
            params["qualified_quality_phred"] = 15
        if "reduce_threads" in actions:
            params["threads"] = cfg_patch.get("docker", {}).get("threads") or params.get("threads")

    return new_dag, cfg_patch


def deep_merge_config(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge_config(out[k], v)
        else:
            out[k] = v
    return out
