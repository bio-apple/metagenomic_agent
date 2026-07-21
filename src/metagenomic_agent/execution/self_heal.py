"""Self-healing heuristics for bioinformatics tool failures."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


# Classification → recovery actions (ordered preference)
HEURISTICS: dict[str, list[str]] = {
    "oom": ["reduce_threads", "reduce_memory", "downgrade_assembler"],
    "timeout": ["reduce_threads", "skip_optional_step"],
    "logic": ["downgrade_assembler", "switch_taxonomy_tool", "loosen_qc"],
    "resource": ["reduce_threads", "reduce_memory"],
    "missing_binary": ["switch_to_container", "switch_to_mock_fallback"],
    "missing_library": ["switch_to_container", "pin_platform_amd64"],
    "arch_mismatch": ["pin_platform_amd64", "switch_to_container"],
}


def classify_from_errors(errors: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for err in errors:
        classified = (err.get("classified") or "").lower()
        msg = (err.get("error") or err.get("stderr") or "").lower()
        rc = err.get("returncode")
        if rc == 137 or classified == "oom" or "out of memory" in msg:
            actions.extend(HEURISTICS["oom"])
        elif classified == "timeout" or "timed out" in msg:
            actions.extend(HEURISTICS["timeout"])
        elif classified in {"missing_binary", "missing_library", "arch_mismatch"}:
            actions.extend(HEURISTICS.get(classified, HEURISTICS["missing_binary"]))
        elif "spades" in msg or "metaspades" in (err.get("node") or "").lower():
            actions.append("downgrade_assembler")
        else:
            actions.extend(HEURISTICS.get(classified, HEURISTICS["logic"]))
    return list(dict.fromkeys(actions))


def apply_self_heal(
    dag: list[dict[str, Any]], actions: list[str], config: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Adjust DAG params and runtime config for the next retry — never dump raw stderr to users."""
    new_dag = deepcopy(dag)
    cfg_patch: dict[str, Any] = {}
    linux = dict((config or {}).get("linux") or {})
    docker = dict((config or {}).get("docker") or {})
    sandbox = dict((config or {}).get("sandbox") or {})

    if "reduce_threads" in actions:
        threads = int(docker.get("threads") or linux.get("threads") or 8)
        new_threads = max(2, threads // 2)
        cfg_patch.setdefault("docker", {})["threads"] = new_threads
        cfg_patch.setdefault("linux", {})["threads"] = new_threads
    if "reduce_memory" in actions:
        mem = int(linux.get("memory_gb", 32))
        cfg_patch.setdefault("linux", {})["memory_gb"] = max(8, mem // 2)

    if "switch_to_container" in actions:
        # Prefer Docker; fall back to apptainer on HPC
        cfg_patch["mode"] = "docker"
        cfg_patch.setdefault("sandbox", {})["backend"] = "docker"
        cfg_patch.setdefault("sandbox", {})["prefer_container"] = True
    if "pin_platform_amd64" in actions:
        cfg_patch.setdefault("sandbox", {})["platform"] = "linux/amd64"
        cfg_patch.setdefault("docker", {})["platform"] = "linux/amd64"
    if "switch_to_mock_fallback" in actions and (config or {}).get("sandbox", {}).get("allow_mock_fallback", True):
        # Last resort for CI / demo — keep pipeline moving with mock tool outputs
        cfg_patch["mode"] = "mock"
        cfg_patch.setdefault("sandbox", {})["backend"] = "mock"

    for node in new_dag:
        node["status"] = "pending"
        agent = node.get("agent", "")
        params = node.setdefault("params", {})
        if "downgrade_assembler" in actions and agent == "assembly":
            params["assembler"] = "megahit"
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
        if "switch_to_container" in actions:
            params["prefer_container"] = True

    # Preserve existing sandbox keys when patching
    if "sandbox" in cfg_patch and sandbox:
        merged = {**sandbox, **cfg_patch["sandbox"]}
        cfg_patch["sandbox"] = merged

    return new_dag, cfg_patch


def deep_merge_config(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge_config(out[k], v)
        else:
            out[k] = v
    return out


def summarize_heal_for_user(actions: list[str], errors: list[dict[str, Any]]) -> str:
    """Human-readable recovery summary — no raw stderr dump."""
    if not actions and not errors:
        return "无自愈动作"
    parts = [f"已计划自愈动作: {', '.join(actions) or 'none'}"]
    classes = sorted({(e.get('classified') or 'unknown') for e in errors})
    if classes:
        parts.append(f"错误类别: {', '.join(classes)}")
    friendly = [e.get("user_message") for e in errors if e.get("user_message")]
    if friendly:
        parts.append("说明: " + friendly[0])
    return "；".join(parts)
