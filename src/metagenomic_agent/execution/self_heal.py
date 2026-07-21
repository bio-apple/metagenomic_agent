"""Self-healing heuristics for bioinformatics tool failures.

Loop: capture classified errors → summarize logs → adjust validated params → retry.
Agent never rewrites free-form shell; it patches YAML/JSON params + DAG.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


# Classification → recovery actions (ordered preference)
HEURISTICS: dict[str, list[str]] = {
    # OOM: first raise memory ceiling (under-provisioned jobs), then reduce parallelism
    "oom": ["increase_memory", "reduce_threads", "downgrade_assembler"],
    "timeout": ["increase_timeout", "reduce_threads", "skip_optional_step"],
    "logic": ["downgrade_assembler", "switch_taxonomy_tool", "loosen_qc"],
    "resource": ["reduce_threads", "increase_memory"],
    "missing_binary": ["switch_to_container", "switch_to_mock_fallback"],
    "missing_library": ["switch_to_container", "pin_platform_amd64"],
    "arch_mismatch": ["pin_platform_amd64", "switch_to_container"],
    "missing_file": ["fix_paths", "skip_optional_step"],
    "missing_db": ["fix_db_path", "switch_taxonomy_tool"],
}


def summarize_error_logs(errors: list[dict[str, Any]], *, max_lines: int = 8) -> str:
    """Compact log digest for the Agent — never dump full stderr stacks."""
    if not errors:
        return "no errors"
    chunks: list[str] = []
    for err in errors[:6]:
        node = err.get("node") or err.get("tool") or "unknown"
        classified = err.get("classified") or "unknown"
        rc = err.get("returncode")
        raw = err.get("stderr") or err.get("error") or err.get("user_message") or ""
        lines = [ln.strip() for ln in str(raw).splitlines() if ln.strip()]
        # Prefer last informative lines
        digest_lines = lines[-3:] if lines else []
        digest = " | ".join(digest_lines)[:240]
        chunks.append(f"[{node}] class={classified} rc={rc}: {digest or '(no stderr)'}")
    text = "\n".join(chunks[:max_lines])
    return text


def classify_from_errors(errors: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for err in errors:
        classified = (err.get("classified") or "").lower()
        msg = (err.get("error") or err.get("stderr") or err.get("user_message") or "").lower()
        rc = err.get("returncode")
        if rc == 137 or classified == "oom" or "out of memory" in msg or "cannot allocate memory" in msg:
            actions.extend(HEURISTICS["oom"])
        elif classified == "timeout" or "timed out" in msg:
            actions.extend(HEURISTICS["timeout"])
        elif classified == "missing_db" or "database" in msg and (
            "not found" in msg or "index" in msg or "does not exist" in msg
        ):
            actions.extend(HEURISTICS["missing_db"])
        elif classified == "missing_file" or (
            "no such file" in msg and "database" not in msg and "bin/" not in msg
        ):
            actions.extend(HEURISTICS["missing_file"])
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
    paths = dict((config or {}).get("paths") or {})

    if "increase_memory" in actions:
        mem = int(linux.get("memory_gb", 32))
        # Cap at 512 GB to avoid runaway; double each heal step
        cfg_patch.setdefault("linux", {})["memory_gb"] = min(512, max(mem * 2, mem + 16))
    if "reduce_threads" in actions:
        threads = int(docker.get("threads") or linux.get("threads") or 8)
        new_threads = max(2, threads // 2)
        cfg_patch.setdefault("docker", {})["threads"] = new_threads
        cfg_patch.setdefault("linux", {})["threads"] = new_threads
    if "reduce_memory" in actions and "increase_memory" not in actions:
        mem = int(linux.get("memory_gb", 32))
        cfg_patch.setdefault("linux", {})["memory_gb"] = max(8, mem // 2)
    if "increase_timeout" in actions:
        cfg_patch.setdefault("execution", {})["timeout_s"] = int(
            ((config or {}).get("execution") or {}).get("timeout_s") or 3600
        ) * 2

    if "switch_to_container" in actions:
        cfg_patch["mode"] = "docker"
        cfg_patch.setdefault("sandbox", {})["backend"] = "docker"
        cfg_patch.setdefault("sandbox", {})["prefer_container"] = True
    if "pin_platform_amd64" in actions:
        cfg_patch.setdefault("sandbox", {})["platform"] = "linux/amd64"
        cfg_patch.setdefault("docker", {})["platform"] = "linux/amd64"
    if "switch_to_mock_fallback" in actions and (config or {}).get("sandbox", {}).get("allow_mock_fallback", True):
        cfg_patch["mode"] = "mock"
        cfg_patch.setdefault("sandbox", {})["backend"] = "mock"

    if "fix_db_path" in actions:
        # Surface empty DB paths for HITL / next retry; clear broken placeholders
        for key in ("kraken2_db", "metaphlan_db", "gtdb", "diamond_db"):
            val = str(paths.get(key) or "")
            if not val or val.startswith("<") or "not_found" in val.lower():
                cfg_patch.setdefault("paths", {})[key] = paths.get(key) or ""
                cfg_patch.setdefault("hitl_hints", []).append(f"verify paths.{key}")

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
        if "increase_memory" in actions:
            params["memory_gb"] = cfg_patch.get("linux", {}).get("memory_gb") or params.get("memory_gb")
        if "switch_to_container" in actions:
            params["prefer_container"] = True
        if "fix_paths" in actions:
            # Force re-resolve relative outputs from outdir on retry
            params["rebind_paths"] = True

    if "sandbox" in cfg_patch and sandbox:
        merged = {**sandbox, **cfg_patch["sandbox"]}
        cfg_patch["sandbox"] = merged

    return new_dag, cfg_patch


def deep_merge_config(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if k == "hitl_hints":
            out[k] = list(dict.fromkeys(list(out.get(k) or []) + list(v or [])))
            continue
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
    classes = sorted({(e.get("classified") or "unknown") for e in errors})
    if classes:
        parts.append(f"错误类别: {', '.join(classes)}")
    friendly = [e.get("user_message") for e in errors if e.get("user_message")]
    if friendly:
        parts.append("说明: " + friendly[0])
    digest = summarize_error_logs(errors)
    if digest and digest != "no errors":
        # One-line pointer; full digest stored in artifacts
        first = digest.splitlines()[0]
        parts.append(f"日志摘要: {first}")
    return "；".join(parts)


def patch_workflow_params_on_heal(
    params: dict[str, Any], cfg_patch: dict[str, Any], actions: list[str]
) -> dict[str, Any]:
    """Rewrite engine params.yaml content after a heal cycle (structured, not shell)."""
    out = deepcopy(params)
    linux = cfg_patch.get("linux") or {}
    docker = cfg_patch.get("docker") or {}
    if "threads" in linux or "threads" in docker:
        out["threads"] = int(docker.get("threads") or linux.get("threads") or out.get("threads") or 8)
    if "memory_gb" in linux:
        out["memory_gb"] = int(linux["memory_gb"])
    out["heal_actions"] = list(actions)
    out["heal_generation"] = int(out.get("heal_generation") or 0) + 1
    # Propagate into tool_calls params
    for tc in out.get("tool_calls") or []:
        p = tc.setdefault("params", {})
        if "threads" in out:
            p["threads"] = out["threads"]
        if "memory_gb" in out:
            p["memory_gb"] = out["memory_gb"]
        if "downgrade_assembler" in actions and tc.get("tool") in {"metaspades", "spades"}:
            tc["tool"] = "megahit"
            p["tool"] = "megahit"
    return out
