"""Self-healing heuristics for bioinformatics tool failures.

Loop: capture classified errors → summarize logs → adjust validated params → retry.
Agent never rewrites free-form shell; it patches YAML/JSON params + DAG.

Risk tiers (see docs/SELF_HEAL.md):
  low/medium — typically auto-applied (resource / platform fixes)
  high — can change biological conclusions; require HITL unless explicitly approved
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Classification → recovery actions (ordered preference)
# Note: OOM does NOT auto-downgrade assembler — only assembly-node OOM/spades errors do.
HEURISTICS: dict[str, list[str]] = {
    "oom": ["increase_memory", "reduce_threads"],
    "timeout": ["increase_timeout", "reduce_threads"],
    "logic": ["switch_taxonomy_tool"],
    "resource": ["reduce_threads", "increase_memory"],
    "missing_binary": ["switch_to_container", "switch_to_mock_fallback"],
    "missing_library": ["switch_to_container", "pin_platform_amd64"],
    "arch_mismatch": ["pin_platform_amd64", "switch_to_container"],
    "missing_file": ["fix_paths"],
    "missing_db": ["fix_db_path", "switch_taxonomy_tool"],
}

# Actions that can silently alter biological conclusions or fabricate success
HIGH_RISK_ACTIONS: frozenset[str] = frozenset(
    {
        "switch_to_mock_fallback",
        "loosen_qc",
        "lower_kraken_confidence",
        "downgrade_assembler",
    }
)

MEDIUM_RISK_ACTIONS: frozenset[str] = frozenset(
    {
        "increase_memory",
        "reduce_threads",
        "reduce_memory",
        "increase_timeout",
        "switch_to_container",
        "pin_platform_amd64",
        "switch_taxonomy_tool",
        "fix_paths",
        "fix_db_path",
        "retry_failed_nodes",
    }
)

# Critic text must match these (avoid bare "quality" false triggers)
CRITIC_HEAL_KEYWORDS: tuple[str, ...] = (
    "metaphlan",
    "fastp",
    "phred",
    "q30",
    "assembler",
    "megahit",
    "metaspades",
    "memory",
    "oom",
    "out of memory",
    "contract",
)


def action_risk(action: str) -> str:
    base = action.split(":", 1)[0]
    if base in HIGH_RISK_ACTIONS or action.startswith("loosen_qc"):
        return "high"
    if base in MEDIUM_RISK_ACTIONS or action.startswith("relax_host_filter"):
        return "medium"
    return "low"


def partition_actions(actions: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"high": [], "medium": [], "low": []}
    for a in actions:
        out[action_risk(a)].append(a)
    return out


def _node_blob(err: dict[str, Any]) -> str:
    return " ".join(
        str(x or "")
        for x in (err.get("node"), err.get("tool"), err.get("agent"), err.get("stage"))
    ).lower()


def _is_assembly_related(err: dict[str, Any]) -> bool:
    blob = _node_blob(err)
    msg = (err.get("error") or err.get("stderr") or err.get("user_message") or "").lower()
    return any(
        k in blob or k in msg for k in ("assembly", "spades", "metaspades", "megahit", "binning")
    )


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
        digest_lines = lines[-3:] if lines else []
        digest = " | ".join(digest_lines)[:240]
        chunks.append(f"[{node}] class={classified} rc={rc}: {digest or '(no stderr)'}")
    return "\n".join(chunks[:max_lines])


def classify_from_errors(errors: list[dict[str, Any]]) -> list[str]:
    """Map classified tool errors → heal actions (node-scoped to reduce false corrections)."""
    actions: list[str] = []
    for err in errors:
        classified = (err.get("classified") or "").lower()
        msg = (err.get("error") or err.get("stderr") or err.get("user_message") or "").lower()
        rc = err.get("returncode")
        assemblyish = _is_assembly_related(err)

        if rc == 137 or classified == "oom" or "out of memory" in msg or "cannot allocate memory" in msg:
            actions.extend(HEURISTICS["oom"])
            if assemblyish:
                actions.append("downgrade_assembler")
        elif classified == "timeout" or "timed out" in msg:
            actions.extend(HEURISTICS["timeout"])
        elif classified == "missing_db" or (
            "database" in msg and ("not found" in msg or "index" in msg or "does not exist" in msg)
        ):
            actions.extend(HEURISTICS["missing_db"])
        elif classified == "missing_file" or (
            "no such file" in msg and "database" not in msg and "bin/" not in msg
        ):
            actions.extend(HEURISTICS["missing_file"])
        elif classified in {"missing_binary", "missing_library", "arch_mismatch"}:
            actions.extend(HEURISTICS.get(classified, HEURISTICS["missing_binary"]))
        elif assemblyish and ("spades" in msg or "metaspades" in _node_blob(err)):
            actions.append("downgrade_assembler")
            actions.append("increase_memory")
        else:
            # Generic logic: prefer taxonomy switch over silent QC loosen / assembler downgrade
            actions.extend(HEURISTICS.get(classified, HEURISTICS["logic"]))
    return list(dict.fromkeys(actions))


def critic_suggests_heal(recommendations: list[str] | None) -> bool:
    recs = " ".join(recommendations or []).lower()
    return any(k in recs for k in CRITIC_HEAL_KEYWORDS)


def collect_heal_actions(state: dict[str, Any]) -> list[str]:
    """Propose heal actions from errors + validation recovery + critic/PI hints (no side effects)."""
    from metagenomic_agent.validators.recovery import plan_recovery

    actions: list[str] = []
    errors = list((state.get("artifacts") or {}).get("errors") or [])
    actions.extend(classify_from_errors(errors))
    validation = state.get("validation") or {}
    if validation and not validation.get("passed"):
        actions.extend(
            plan_recovery(
                state, validation.get("technical") or {}, validation.get("biological") or {}
            )
        )
        actions.extend(validation.get("recovery_actions") or [])
    critic = state.get("critic") or {}
    recs = " ".join(critic.get("recommendations") or []).lower()
    if "metaphlan" in recs or "glm" in recs or "microcafe" in recs:
        actions.append("switch_taxonomy_tool")
    if "fastp" in recs or "phred" in recs or "q30" in recs:
        actions.append("loosen_qc")
    if "assembler" in recs or "megahit" in recs or "metaspades" in recs:
        actions.append("downgrade_assembler")
    if state.get("pi_replan"):
        actions.append("switch_taxonomy_tool")
        # PI replan used to force loosen_qc — high FP; keep taxonomy switch only
    return list(dict.fromkeys(actions))


def filter_actions_for_policy(
    actions: list[str],
    *,
    approve_high_risk: bool = False,
    approved_actions: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return (applied, withheld_high_risk). High-risk dropped unless approved."""
    approved = set(approved_actions or [])
    applied: list[str] = []
    withheld: list[str] = []
    for a in actions:
        if action_risk(a) != "high":
            applied.append(a)
            continue
        if approve_high_risk or a in approved or a.split(":", 1)[0] in approved:
            applied.append(a)
        else:
            withheld.append(a)
    return list(dict.fromkeys(applied)), list(dict.fromkeys(withheld))


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
        cfg_patch.setdefault("execution", {})["timeout_s"] = (
            int(((config or {}).get("execution") or {}).get("timeout_s") or 3600) * 2
        )

    if "switch_to_container" in actions:
        cfg_patch["mode"] = "docker"
        cfg_patch.setdefault("sandbox", {})["backend"] = "docker"
        cfg_patch.setdefault("sandbox", {})["prefer_container"] = True
    if "pin_platform_amd64" in actions:
        cfg_patch.setdefault("sandbox", {})["platform"] = "linux/amd64"
        cfg_patch.setdefault("docker", {})["platform"] = "linux/amd64"
    if "switch_to_mock_fallback" in actions and (config or {}).get("sandbox", {}).get(
        "allow_mock_fallback", True
    ):
        cfg_patch["mode"] = "mock"
        cfg_patch.setdefault("sandbox", {})["backend"] = "mock"

    if "fix_db_path" in actions:
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
            params["memory_gb"] = cfg_patch.get("linux", {}).get("memory_gb") or params.get(
                "memory_gb"
            )
        if "switch_to_container" in actions:
            params["prefer_container"] = True
        if "fix_paths" in actions:
            params["rebind_paths"] = True

    if "sandbox" in cfg_patch and sandbox:
        cfg_patch["sandbox"] = {**sandbox, **cfg_patch["sandbox"]}

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
        return "No self-heal actions"
    parts = [f"Planned self-heal actions: {', '.join(actions) or 'none'}"]
    classes = sorted({(e.get("classified") or "unknown") for e in errors})
    if classes:
        parts.append(f"Error classes: {', '.join(classes)}")
    friendly = [e.get("user_message") for e in errors if e.get("user_message")]
    if friendly:
        parts.append("Note: " + friendly[0])
    digest = summarize_error_logs(errors)
    if digest and digest != "no errors":
        first = digest.splitlines()[0]
        parts.append(f"Log summary: {first}")
    return "; ".join(parts)


def patch_workflow_params_on_heal(
    params: dict[str, Any], cfg_patch: dict[str, Any], actions: list[str]
) -> dict[str, Any]:
    """Rewrite engine params.yaml content after a heal cycle (structured, not shell)."""
    out = deepcopy(params)
    linux = cfg_patch.get("linux") or {}
    docker = cfg_patch.get("docker") or {}
    if "threads" in linux or "threads" in docker:
        out["threads"] = int(
            docker.get("threads") or linux.get("threads") or out.get("threads") or 8
        )
    if "memory_gb" in linux:
        out["memory_gb"] = int(linux["memory_gb"])
    out["heal_actions"] = list(actions)
    out["heal_generation"] = int(out.get("heal_generation") or 0) + 1
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
