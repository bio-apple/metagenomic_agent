"""Explicit workflow DAG export for LangGraph / Snakemake / Nextflow handoff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CANONICAL_STAGES = [
    "QC",
    "Host Removal",
    "Taxonomy",
    "Assembly",
    "Binning",
    "MAG QC",
    "Annotation",
    "Differential Analysis",
    "Visualization",
]


def _agent_to_stage(agent: str) -> str:
    a = (agent or "").lower()
    if "qc" in a:
        return "QC"
    if "tax" in a:
        return "Taxonomy"
    if "assembl" in a or "bin" in a:
        return "Assembly"
    if "function" in a:
        return "Annotation"
    if "stat" in a:
        return "Differential Analysis"
    if "viz" in a or "visual" in a:
        return "Visualization"
    return agent or "unknown"


def export_workflow_dag(state: dict[str, Any]) -> dict[str, Any]:
    """Write a portable DAG JSON separating planner output from agent runtime."""
    outdir = Path(state["outdir"]) / "workflow"
    outdir.mkdir(parents=True, exist_ok=True)

    nodes = []
    edges = []
    for n in state.get("dag") or []:
        nid = n.get("id") or n.get("name")
        stage = _agent_to_stage(str(n.get("agent", "")))
        nodes.append(
            {
                "id": nid,
                "stage": stage,
                "agent": n.get("agent"),
                "tools": n.get("tools") or [],
                "params": n.get("params") or {},
                "status": n.get("status", "pending"),
            }
        )
        for dep in n.get("depends_on") or []:
            edges.append({"from": dep, "to": nid})

    # Canonical stage outline for documentation / external engines
    stages = []
    for i, name in enumerate(CANONICAL_STAGES):
        stages.append({"order": i + 1, "name": name, "enabled": any(x["stage"] == name or name in x["stage"] for x in nodes) or name in {"QC", "Taxonomy", "Differential Analysis", "Visualization"}})

    payload = {
        "engine": (state.get("config") or {}).get("execution", {}).get("engine", "langgraph"),
        "canonical_stages": stages,
        "nodes": nodes,
        "edges": edges,
        "query": state.get("user_query"),
        "run_id": state.get("run_id"),
    }
    path = outdir / "dag.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Mermaid for humans
    mmd = ["flowchart TD"]
    for n in nodes:
        mmd.append(f'  {n["id"]}["{n["stage"]}\\n{n["id"]}"]')
    for e in edges:
        mmd.append(f'  {e["from"]} --> {e["to"]}')
    (outdir / "dag.mmd").write_text("\n".join(mmd) + "\n", encoding="utf-8")

    return {"path": str(path), "mermaid": str(outdir / "dag.mmd"), "n_nodes": len(nodes), "n_edges": len(edges)}
