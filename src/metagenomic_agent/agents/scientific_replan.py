"""Scientific replan — Critic/PI findings drive DAG redesign (not just resource self-heal).

Closes the Development.docx loop: plan → execute → evaluate → replan.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def should_scientific_replan(state: dict[str, Any]) -> bool:
    """True when findings imply redesign (tools/pipeline), not only memory/threads."""
    critic = state.get("critic") or {}
    pi = (state.get("artifacts") or {}).get("pi_review") or {}
    blob = " ".join(
        list(critic.get("recommendations") or [])
        + list(critic.get("warnings") or [])
        + list(pi.get("findings") or [])
    ).lower()
    keys = (
        "metaphlan",
        "classification",
        "taxonomy",
        "assembly",
        "mag",
        "binning",
        "ancom",
        "maaslin",
        "deseq",
        "batch",
        "permanova",
        "diversity",
        "host",
        "contamination",
        "workflow",
        "replan",
        "redesign",
    )
    return any(k in blob for k in keys)


def apply_scientific_replan(state: dict[str, Any]) -> dict[str, Any]:
    """Patch DAG + config from Critic/PI findings, reset nodes to pending, refresh planner artifact."""
    from metagenomic_agent.agents import planner_agent

    arts = dict(state.get("artifacts") or {})
    cfg = dict(state.get("config") or {})
    dag = deepcopy(list(state.get("dag") or []))
    critic = state.get("critic") or {}
    pi = arts.get("pi_review") or {}
    findings = list(critic.get("recommendations") or []) + list(pi.get("findings") or [])
    blob = " ".join(findings).lower()

    patches: list[str] = []
    pipe = dict(cfg.get("pipeline") or {})

    if any(k in blob for k in ("metaphlan", "classification", "taxonomy")):
        for node in dag:
            if node.get("agent") == "taxonomy":
                tools = list(node.get("tools") or [])
                if "metaphlan" not in tools:
                    tools.append("metaphlan")
                    patches.append("taxonomy:+metaphlan")
                node["tools"] = tools
                node.setdefault("params", {})["tools"] = tools

    if any(k in blob for k in ("assembly", "mag", "binning", "checkm")):
        pipe["enable_assembly"] = True
        patches.append("pipeline.enable_assembly=true")
        if not any(n.get("agent") == "assembly" for n in dag):
            dag.append(
                {
                    "id": "assembly_binning",
                    "agent": "assembly",
                    "tools": ["megahit", "metabat2", "maxbin2", "checkm2"],
                    "params": {"assembler": "megahit"},
                    "depends_on": ["quality_control"],
                    "status": "pending",
                }
            )
            patches.append("dag:+assembly_binning")
        for node in dag:
            if node.get("agent") == "assembly":
                node["status"] = "pending"
                binners = list(node.get("params", {}).get("binners") or pipe.get("binners") or [])
                if "vamb" not in binners and "vamb" in blob:
                    binners.append("vamb")
                    node.setdefault("params", {})["binners"] = binners
                    patches.append("assembly:+vamb")

    if any(k in blob for k in ("host", "contamination")):
        pipe["enable_host_filter"] = True
        patches.append("pipeline.enable_host_filter=true")

    if any(k in blob for k in ("ancom", "maaslin", "deseq", "composition", "batch")):
        stats = dict(cfg.get("statistics") or {})
        stats["prefer_compositional"] = True
        if "batch" in blob:
            stats["check_batch_effect"] = True
        cfg["statistics"] = stats
        patches.append("statistics:compositional_reasoning")

    if any(k in blob for k in ("long-read", "long read", "nanopore", "pacbio", "flye")):
        for node in dag:
            if node.get("agent") == "assembly":
                node.setdefault("params", {})["assembler"] = "flye"
                patches.append("assembly:assembler=flye")

    cfg["pipeline"] = pipe
    for node in dag:
        if node.get("status") != "skipped":
            node["status"] = "pending"

    count = int(arts.get("scientific_replan_count") or 0) + 1
    arts["scientific_replan_count"] = count
    arts["scientific_replan"] = {
        "count": count,
        "findings": findings[:12],
        "patches": patches,
    }
    arts["errors"] = []

    planned = planner_agent.run({**state, "dag": dag, "config": cfg, "artifacts": arts})
    arts = {**arts, **(planned.get("artifacts") or {})}

    return {
        "dag": dag,
        "config": cfg,
        "artifacts": arts,
        "pi_replan": False,
        "messages": state.get("messages", [])
        + [
            f"Scientific replan #{count}: {', '.join(patches) or 'refresh DAG'}",
            f"Replan drivers: {'; '.join(findings[:3]) or 'PI/Critic'}",
        ],
    }
